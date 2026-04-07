"""
Permission mode definitions.

This module defines permission modes and results for the permission system,
supporting various permission handling strategies.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class PermissionMode(str, Enum):
    """
    Permission mode enumeration.

    Defines how permissions are handled in the system.

    Modes:
        default: Standard permission handling with user prompts
        acceptEdits: Automatically accept edit operations
        bypassPermissions: Skip all permission checks (dangerous)
        bubble: Bubble permission requests to parent agent
        plan: Permission mode for planning operations
        auto: Automatic permission handling based on context
    """

    DEFAULT = "default"
    ACCEPT_EDITS = "acceptEdits"
    BYPASS_PERMISSIONS = "bypassPermissions"
    BUBBLE = "bubble"
    PLAN = "plan"
    AUTO = "auto"

    @classmethod
    def from_string(cls, value: str) -> "PermissionMode":
        """
        Create PermissionMode from string value.

        Args:
            value: String representation of the mode

        Returns:
            PermissionMode instance

        Raises:
            ValueError: If the value is not a valid mode
        """
        normalized = value.strip().lower()
        mode_map = {
            "default": cls.DEFAULT,
            "acceptedits": cls.ACCEPT_EDITS,
            "accept_edits": cls.ACCEPT_EDITS,
            "bypasspermissions": cls.BYPASS_PERMISSIONS,
            "bypass_permissions": cls.BYPASS_PERMISSIONS,
            "bypass": cls.BYPASS_PERMISSIONS,
            "bubble": cls.BUBBLE,
            "plan": cls.PLAN,
            "auto": cls.AUTO,
        }
        if normalized not in mode_map:
            raise ValueError(
                f"Invalid permission mode: {value}. "
                f"Valid modes: {', '.join(m.value for m in cls)}"
            )
        return mode_map[normalized]

    def is_bypass(self) -> bool:
        """Check if this mode bypasses permission checks."""
        return self == PermissionMode.BYPASS_PERMISSIONS

    def is_auto_accept(self) -> bool:
        """Check if this mode auto-accepts edits."""
        return self == PermissionMode.ACCEPT_EDITS

    def requires_prompt(self) -> bool:
        """Check if this mode requires user prompts."""
        return self in (
            PermissionMode.DEFAULT,
            PermissionMode.PLAN,
        )


class PermissionAction(str, Enum):
    """
    Permission action enumeration.

    Defines the possible actions that can be taken for a permission request.
    """

    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"
    BUBBLE = "bubble"


class PermissionResult(BaseModel):
    """
    Permission result.

    Represents the result of a permission check or request.
    """

    action: PermissionAction = Field(
        ..., description="The action to take for this permission"
    )
    allowed: bool = Field(
        ..., description="Whether the action is allowed"
    )
    reason: Optional[str] = Field(
        default=None, description="Reason for the permission decision"
    )
    mode: PermissionMode = Field(
        default=PermissionMode.DEFAULT, description="The permission mode used"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata about the permission"
    )

    @property
    def is_allowed(self) -> bool:
        """Check if permission is allowed."""
        return self.allowed

    @property
    def is_denied(self) -> bool:
        """Check if permission is denied."""
        return not self.allowed

    @property
    def needs_user_input(self) -> bool:
        """Check if user input is needed."""
        return self.action == PermissionAction.ASK

    @property
    def should_bubble(self) -> bool:
        """Check if permission should bubble to parent."""
        return self.action == PermissionAction.BUBBLE

    @classmethod
    def allow(
        cls,
        reason: Optional[str] = None,
        mode: PermissionMode = PermissionMode.DEFAULT,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "PermissionResult":
        """
        Create an allow result.

        Args:
            reason: Reason for allowing
            mode: Permission mode used
            metadata: Additional metadata

        Returns:
            PermissionResult with allow action
        """
        return cls(
            action=PermissionAction.ALLOW,
            allowed=True,
            reason=reason,
            mode=mode,
            metadata=metadata or {},
        )

    @classmethod
    def deny(
        cls,
        reason: Optional[str] = None,
        mode: PermissionMode = PermissionMode.DEFAULT,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "PermissionResult":
        """
        Create a deny result.

        Args:
            reason: Reason for denying
            mode: Permission mode used
            metadata: Additional metadata

        Returns:
            PermissionResult with deny action
        """
        return cls(
            action=PermissionAction.DENY,
            allowed=False,
            reason=reason,
            mode=mode,
            metadata=metadata or {},
        )

    @classmethod
    def ask(
        cls,
        reason: Optional[str] = None,
        mode: PermissionMode = PermissionMode.DEFAULT,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "PermissionResult":
        """
        Create an ask result (requires user input).

        Args:
            reason: Reason for asking
            mode: Permission mode used
            metadata: Additional metadata

        Returns:
            PermissionResult with ask action
        """
        return cls(
            action=PermissionAction.ASK,
            allowed=False,
            reason=reason,
            mode=mode,
            metadata=metadata or {},
        )

    @classmethod
    def bubble(
        cls,
        reason: Optional[str] = None,
        mode: PermissionMode = PermissionMode.BUBBLE,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "PermissionResult":
        """
        Create a bubble result (escalate to parent agent).

        Args:
            reason: Reason for bubbling
            mode: Permission mode used
            metadata: Additional metadata

        Returns:
            PermissionResult with bubble action
        """
        return cls(
            action=PermissionAction.BUBBLE,
            allowed=False,
            reason=reason,
            mode=mode,
            metadata=metadata or {},
        )


class PermissionContext(BaseModel):
    """
    Permission context.

    Provides context for permission decisions.
    """

    mode: PermissionMode = Field(
        default=PermissionMode.DEFAULT, description="Current permission mode"
    )
    agent_id: Optional[str] = Field(
        default=None, description="Agent ID making the request"
    )
    session_id: Optional[str] = Field(
        default=None, description="Session ID for the request"
    )
    parent_context: Optional["PermissionContext"] = Field(
        default=None, description="Parent permission context for bubbling"
    )
    allowed_tools: set = Field(
        default_factory=set, description="Set of allowed tool names"
    )
    denied_tools: set = Field(
        default_factory=set, description="Set of denied tool names"
    )
    allowed_paths: set = Field(
        default_factory=set, description="Set of allowed file paths"
    )
    denied_paths: set = Field(
        default_factory=set, description="Set of denied file paths"
    )

    class Config:
        """Pydantic config."""

        use_enum_values = False
        # Allow arbitrary field types for set fields
        arbitrary_types_allowed = True

    def is_tool_allowed(self, tool_name: str) -> Optional[bool]:
        """
        Check if a tool is explicitly allowed or denied.

        Args:
            tool_name: Name of the tool

        Returns:
            True if allowed, False if denied, None if not specified
        """
        if tool_name in self.denied_tools:
            return False
        if tool_name in self.allowed_tools:
            return True
        return None

    def is_path_allowed(self, path: str) -> Optional[bool]:
        """
        Check if a path is explicitly allowed or denied.

        Args:
            path: File path to check

        Returns:
            True if allowed, False if denied, None if not specified
        """
        if path in self.denied_paths:
            return False
        if path in self.allowed_paths:
            return True
        return None

    def with_mode(self, mode: PermissionMode) -> "PermissionContext":
        """
        Create a new context with a different mode.

        Args:
            mode: New permission mode

        Returns:
            New PermissionContext with the specified mode
        """
        return PermissionContext(
            mode=mode,
            agent_id=self.agent_id,
            session_id=self.session_id,
            parent_context=self.parent_context,
            allowed_tools=self.allowed_tools.copy(),
            denied_tools=self.denied_tools.copy(),
            allowed_paths=self.allowed_paths.copy(),
            denied_paths=self.denied_paths.copy(),
        )
