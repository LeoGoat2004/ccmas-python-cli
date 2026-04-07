"""
Permission checker logic.

This module provides permission checking functionality for tools and file operations,
implementing the core permission validation logic.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

from pydantic import BaseModel, Field

from ccmas.permission.mode import (
    PermissionAction,
    PermissionContext,
    PermissionMode,
    PermissionResult,
)


class PermissionRule(BaseModel):
    """
    Permission rule definition.

    Defines a single permission rule for tools or file operations.
    """

    name: str = Field(..., description="Rule name for identification")
    pattern: str = Field(..., description="Pattern to match (glob for files, name for tools)")
    action: PermissionAction = Field(..., description="Action to take when matched")
    reason: Optional[str] = Field(default=None, description="Reason for this rule")
    priority: int = Field(default=0, description="Rule priority (higher = more important)")

    class Config:
        """Pydantic config."""

        use_enum_values = True


class PermissionChecker:
    """
    Permission checker for validating tool and file operations.

    Provides centralized permission checking logic with support for
    different permission modes and rule-based access control.
    """

    def __init__(
        self,
        context: Optional[PermissionContext] = None,
        rules: Optional[List[PermissionRule]] = None,
        custom_checkers: Optional[Dict[str, Callable]] = None,
    ):
        """
        Initialize the permission checker.

        Args:
            context: Permission context for decisions
            rules: List of permission rules
            custom_checkers: Custom permission checkers by tool name
        """
        self.context = context or PermissionContext()
        self.rules = rules or []
        self.custom_checkers = custom_checkers or {}
        self._tool_cache: Dict[str, PermissionResult] = {}
        self._path_cache: Dict[str, PermissionResult] = {}

    def set_context(self, context: PermissionContext) -> None:
        """
        Set the permission context.

        Args:
            context: New permission context
        """
        self.context = context
        self._tool_cache.clear()
        self._path_cache.clear()

    def add_rule(self, rule: PermissionRule) -> None:
        """
        Add a permission rule.

        Args:
            rule: Permission rule to add
        """
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
        self._tool_cache.clear()
        self._path_cache.clear()

    def remove_rule(self, name: str) -> Optional[PermissionRule]:
        """
        Remove a permission rule by name.

        Args:
            name: Name of the rule to remove

        Returns:
            Removed rule or None if not found
        """
        for i, rule in enumerate(self.rules):
            if rule.name == name:
                removed = self.rules.pop(i)
                self._tool_cache.clear()
                self._path_cache.clear()
                return removed
        return None

    def check_tool_permission(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[PermissionContext] = None,
    ) -> PermissionResult:
        """
        Check permission for a tool operation.

        Args:
            tool_name: Name of the tool to check
            arguments: Tool arguments (for context-aware decisions)
            context: Optional override context

        Returns:
            PermissionResult indicating the permission decision
        """
        ctx = context or self.context

        # Check cache
        cache_key = f"{tool_name}:{ctx.mode.value}"
        if cache_key in self._tool_cache:
            return self._tool_cache[cache_key]

        # Bypass mode - allow everything
        if ctx.mode.is_bypass():
            result = PermissionResult.allow(
                reason="Bypass mode enabled",
                mode=ctx.mode,
            )
            self._tool_cache[cache_key] = result
            return result

        # Check explicit tool permissions in context
        explicit = ctx.is_tool_allowed(tool_name)
        if explicit is not None:
            result = PermissionResult.allow(
                reason=f"Tool explicitly {'allowed' if explicit else 'denied'}",
                mode=ctx.mode,
                metadata={"explicit_permission": explicit},
            ) if explicit else PermissionResult.deny(
                reason=f"Tool explicitly denied",
                mode=ctx.mode,
                metadata={"explicit_permission": False},
            )
            self._tool_cache[cache_key] = result
            return result

        # Check custom checker
        if tool_name in self.custom_checkers:
            custom_result = self.custom_checkers[tool_name](
                tool_name, arguments, ctx
            )
            if isinstance(custom_result, PermissionResult):
                self._tool_cache[cache_key] = custom_result
                return custom_result

        # Check rules
        for rule in self.rules:
            if self._match_pattern(tool_name, rule.pattern):
                result = PermissionResult(
                    action=rule.action,
                    allowed=rule.action == PermissionAction.ALLOW,
                    reason=rule.reason,
                    mode=ctx.mode,
                    metadata={"rule_name": rule.name, "rule_pattern": rule.pattern},
                )
                self._tool_cache[cache_key] = result
                return result

        # Default behavior based on mode
        result = self._default_tool_result(tool_name, ctx)
        self._tool_cache[cache_key] = result
        return result

    def check_file_permission(
        self,
        file_path: str,
        operation: str = "read",
        context: Optional[PermissionContext] = None,
    ) -> PermissionResult:
        """
        Check permission for a file operation.

        Args:
            file_path: Path to the file
            operation: Operation type (read, write, delete, execute)
            context: Optional override context

        Returns:
            PermissionResult indicating the permission decision
        """
        ctx = context or self.context

        # Normalize path
        try:
            normalized_path = str(Path(file_path).resolve())
        except (OSError, ValueError):
            normalized_path = file_path

        # Check cache
        cache_key = f"{normalized_path}:{operation}:{ctx.mode.value}"
        if cache_key in self._path_cache:
            return self._path_cache[cache_key]

        # Bypass mode - allow everything
        if ctx.mode.is_bypass():
            result = PermissionResult.allow(
                reason="Bypass mode enabled",
                mode=ctx.mode,
                metadata={"operation": operation},
            )
            self._path_cache[cache_key] = result
            return result

        # Check explicit path permissions in context
        explicit = ctx.is_path_allowed(normalized_path)
        if explicit is not None:
            result = PermissionResult.allow(
                reason=f"Path explicitly {'allowed' if explicit else 'denied'}",
                mode=ctx.mode,
                metadata={"operation": operation, "explicit_permission": explicit},
            ) if explicit else PermissionResult.deny(
                reason=f"Path explicitly denied",
                mode=ctx.mode,
                metadata={"operation": operation, "explicit_permission": False},
            )
            self._path_cache[cache_key] = result
            return result

        # Check rules
        for rule in self.rules:
            if self._match_path_pattern(normalized_path, rule.pattern):
                result = PermissionResult(
                    action=rule.action,
                    allowed=rule.action == PermissionAction.ALLOW,
                    reason=rule.reason,
                    mode=ctx.mode,
                    metadata={
                        "rule_name": rule.name,
                        "rule_pattern": rule.pattern,
                        "operation": operation,
                    },
                )
                self._path_cache[cache_key] = result
                return result

        # Check for sensitive paths
        if self._is_sensitive_path(normalized_path):
            result = PermissionResult.ask(
                reason=f"Access to sensitive path requires permission: {operation}",
                mode=ctx.mode,
                metadata={"operation": operation, "sensitive": True},
            )
            self._path_cache[cache_key] = result
            return result

        # Default behavior based on mode and operation
        result = self._default_file_result(normalized_path, operation, ctx)
        self._path_cache[cache_key] = result
        return result

    def check_command_permission(
        self,
        command: str,
        arguments: Optional[List[str]] = None,
        context: Optional[PermissionContext] = None,
    ) -> PermissionResult:
        """
        Check permission for a command execution.

        Args:
            command: Command to execute
            arguments: Command arguments
            context: Optional override context

        Returns:
            PermissionResult indicating the permission decision
        """
        ctx = context or self.context

        # Bypass mode
        if ctx.mode.is_bypass():
            return PermissionResult.allow(
                reason="Bypass mode enabled",
                mode=ctx.mode,
            )

        # Check for dangerous commands
        dangerous_commands = {
            "rm", "del", "format", "fdisk", "mkfs",
            "dd", "shred", "wipe", "sudo", "su",
            "chmod", "chown", "kill", "pkill",
        }

        cmd_base = os.path.basename(command.split()[0] if command else "")
        if cmd_base.lower() in dangerous_commands:
            return PermissionResult.ask(
                reason=f"Dangerous command requires permission: {cmd_base}",
                mode=ctx.mode,
                metadata={"dangerous": True, "command": command},
            )

        # Default to ask for commands in default mode
        if ctx.mode.requires_prompt():
            return PermissionResult.ask(
                reason=f"Command execution requires permission: {command}",
                mode=ctx.mode,
                metadata={"command": command},
            )

        return PermissionResult.allow(
            reason=f"Auto-allowed by mode: {ctx.mode.value}",
            mode=ctx.mode,
        )

    def _match_pattern(self, value: str, pattern: str) -> bool:
        """
        Match a value against a pattern.

        Supports exact match and simple wildcards.

        Args:
            value: Value to match
            pattern: Pattern to match against

        Returns:
            True if matches, False otherwise
        """
        import fnmatch
        return fnmatch.fnmatch(value, pattern)

    def _match_path_pattern(self, path: str, pattern: str) -> bool:
        """
        Match a path against a pattern.

        Supports glob patterns and handles path normalization.

        Args:
            path: Path to match
            pattern: Pattern to match against

        Returns:
            True if matches, False otherwise
        """
        import fnmatch
        return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(
            path.lower(), pattern.lower()
        )

    def _is_sensitive_path(self, path: str) -> bool:
        """
        Check if a path is sensitive.

        Args:
            path: Path to check

        Returns:
            True if sensitive, False otherwise
        """
        sensitive_patterns = [
            "**/.env*",
            "**/.git/**",
            "**/.ssh/**",
            "**/id_rsa*",
            "**/id_ed25519*",
            "**/*.pem",
            "**/*.key",
            "**/credentials*",
            "**/secrets*",
            "**/password*",
            "**/.aws/**",
            "**/.config/**",
        ]

        for pattern in sensitive_patterns:
            if self._match_path_pattern(path, pattern):
                return True
        return False

    def _default_tool_result(
        self,
        tool_name: str,
        context: PermissionContext,
    ) -> PermissionResult:
        """
        Get default permission result for a tool.

        Args:
            tool_name: Tool name
            context: Permission context

        Returns:
            Default PermissionResult
        """
        # Safe tools that don't require permission
        safe_tools = {
            "search", "grep", "glob", "ls", "read",
            "think", "analyze", "plan",
        }

        if tool_name.lower() in safe_tools:
            return PermissionResult.allow(
                reason="Tool is in safe list",
                mode=context.mode,
            )

        # Edit tools in acceptEdits mode
        edit_tools = {"write", "edit", "delete", "create"}
        if tool_name.lower() in edit_tools and context.mode.is_auto_accept():
            return PermissionResult.allow(
                reason="Auto-accept edits mode",
                mode=context.mode,
            )

        # Default: ask for permission
        if context.mode.requires_prompt():
            return PermissionResult.ask(
                reason=f"Tool requires permission: {tool_name}",
                mode=context.mode,
            )

        return PermissionResult.allow(
            reason=f"Auto-allowed by mode: {context.mode.value}",
            mode=context.mode,
        )

    def _default_file_result(
        self,
        path: str,
        operation: str,
        context: PermissionContext,
    ) -> PermissionResult:
        """
        Get default permission result for a file operation.

        Args:
            path: File path
            operation: Operation type
            context: Permission context

        Returns:
            Default PermissionResult
        """
        # Read operations are generally safer
        if operation == "read":
            if context.mode.requires_prompt():
                return PermissionResult.ask(
                    reason=f"File read requires permission",
                    mode=context.mode,
                    metadata={"operation": operation},
                )
            return PermissionResult.allow(
                reason="Read operation auto-allowed",
                mode=context.mode,
                metadata={"operation": operation},
            )

        # Write operations in acceptEdits mode
        if operation in ("write", "edit", "create") and context.mode.is_auto_accept():
            return PermissionResult.allow(
                reason="Auto-accept edits mode",
                mode=context.mode,
                metadata={"operation": operation},
            )

        # Default: ask for permission
        if context.mode.requires_prompt():
            return PermissionResult.ask(
                reason=f"File {operation} requires permission",
                mode=context.mode,
                metadata={"operation": operation},
            )

        return PermissionResult.allow(
            reason=f"Auto-allowed by mode: {context.mode.value}",
            mode=context.mode,
            metadata={"operation": operation},
        )

    def clear_cache(self) -> None:
        """Clear the permission cache."""
        self._tool_cache.clear()
        self._path_cache.clear()


def create_permission_checker(
    mode: PermissionMode = PermissionMode.DEFAULT,
    rules: Optional[List[PermissionRule]] = None,
) -> PermissionChecker:
    """
    Create a permission checker with the specified mode.

    Args:
        mode: Permission mode to use
        rules: Optional list of permission rules

    Returns:
        Configured PermissionChecker instance
    """
    context = PermissionContext(mode=mode)
    return PermissionChecker(context=context, rules=rules)
