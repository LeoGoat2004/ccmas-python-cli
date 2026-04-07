"""
Tool module for CCMAS.

This module provides the tool system for executing operations in CCMAS.
"""

# Base classes
from ccmas.tool.base import (
    Tool,
    ToolCallArgs,
    ToolExecutionResult,
    build_tool,
)

# Registry
from ccmas.tool.registry import (
    ToolRegistry,
    get_all_tool_definitions,
    get_all_tools,
    get_registry,
    get_tool,
    register_tool,
)

# Built-in tools
from ccmas.tool.builtin import (
    BashTool,
    ReadTool,
    WriteTool,
    get_builtin_tools,
    register_builtin_tools,
)

__all__ = [
    # Base classes
    "Tool",
    "ToolCallArgs",
    "ToolExecutionResult",
    "build_tool",
    # Registry
    "ToolRegistry",
    "get_registry",
    "register_tool",
    "get_tool",
    "get_all_tools",
    "get_all_tool_definitions",
    # Built-in tools
    "BashTool",
    "ReadTool",
    "WriteTool",
    "get_builtin_tools",
    "register_builtin_tools",
]
