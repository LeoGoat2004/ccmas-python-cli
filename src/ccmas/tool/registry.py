"""
Tool registry for managing and retrieving tools.

This module provides a central registry for all tools in the CCMAS system.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ccmas.tool.base import Tool
from ccmas.types.tool import ToolDefinition


class ToolRegistry:
    """
    Central registry for managing tools.

    Provides methods to register, retrieve, and manage tools.
    """

    _instance: Optional[ToolRegistry] = None
    _tools: Dict[str, Tool]

    def __new__(cls) -> ToolRegistry:
        """Singleton pattern for global tool registry."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance

    def register(self, tool: Tool) -> None:
        """
        Register a tool.

        Args:
            tool: The tool instance to register
        """
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> Optional[Tool]:
        """
        Unregister a tool.

        Args:
            name: The name of the tool to unregister

        Returns:
            The unregistered tool, or None if not found
        """
        return self._tools.pop(name, None)

    def get(self, name: str) -> Optional[Tool]:
        """
        Get a tool by name.

        Args:
            name: The name of the tool

        Returns:
            The tool instance, or None if not found
        """
        return self._tools.get(name)

    def get_all(self) -> List[Tool]:
        """
        Get all registered tools.

        Returns:
            List of all tool instances
        """
        return list(self._tools.values())

    def get_all_definitions(self) -> List[ToolDefinition]:
        """
        Get definitions for all registered tools.

        Returns:
            List of ToolDefinition instances
        """
        return [tool.get_definition() for tool in self._tools.values()]

    def has(self, name: str) -> bool:
        """
        Check if a tool is registered.

        Args:
            name: The name of the tool

        Returns:
            True if the tool is registered, False otherwise
        """
        return name in self._tools

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()

    def __len__(self) -> int:
        """Get the number of registered tools."""
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools


# Global registry instance
_global_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """
    Get the global tool registry.

    Returns:
        The global ToolRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


def register_tool(tool: Tool) -> None:
    """
    Register a tool in the global registry.

    Args:
        tool: The tool instance to register
    """
    get_registry().register(tool)


def get_tool(name: str) -> Optional[Tool]:
    """
    Get a tool from the global registry.

    Args:
        name: The name of the tool

    Returns:
        The tool instance, or None if not found
    """
    return get_registry().get(name)


def get_all_tools() -> List[Tool]:
    """
    Get all tools from the global registry.

    Returns:
        List of all tool instances
    """
    return get_registry().get_all()


def get_all_tool_definitions() -> List[ToolDefinition]:
    """
    Get definitions for all tools in the global registry.

    Returns:
        List of ToolDefinition instances
    """
    return get_registry().get_all_definitions()
