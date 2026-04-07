"""
Query module for CCMAS.

This module provides the main query loop and related utilities
for managing conversations between users, assistants, and tools.
"""

from ccmas.query.loop import (
    QueryConfig,
    QueryLoop,
    QueryResult,
    QueryState,
    query,
)
from ccmas.query.message_builder import (
    MessageBuilder,
    build_messages,
    build_system_prompt,
)
from ccmas.query.tool_executor import (
    StreamingToolExecutor,
    ToolExecutor,
    execute_tool,
    execute_tools,
)

__all__ = [
    # Loop
    "query",
    "QueryLoop",
    "QueryConfig",
    "QueryResult",
    "QueryState",
    # Message Builder
    "MessageBuilder",
    "build_messages",
    "build_system_prompt",
    # Tool Executor
    "ToolExecutor",
    "StreamingToolExecutor",
    "execute_tool",
    "execute_tools",
]
