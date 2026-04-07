"""
Built-in tools for CCMAS.

This module exports all built-in tools that are available by default.
"""

from ccmas.tool.builtin.bash import BashTool
from ccmas.tool.builtin.read import ReadTool
from ccmas.tool.builtin.write import WriteTool

__all__ = [
    "BashTool",
    "ReadTool",
    "WriteTool",
    "get_builtin_tools",
]


def get_builtin_tools():
    """
    Get all built-in tool instances.

    Returns:
        List of built-in tool instances
    """
    return [
        BashTool(),
        ReadTool(),
        WriteTool(),
    ]


def register_builtin_tools():
    """
    Register all built-in tools in the global registry.
    """
    from ccmas.tool.registry import register_tool

    for tool in get_builtin_tools():
        register_tool(tool)
