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
    getRetryDelay,
    is_api_retryable_error,
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
    calculate_retry_delay,
    execute_tool,
    execute_tools,
    is_retryable_error,
)

__all__ = [
    # Loop
    "query",
    "QueryLoop",
    "QueryConfig",
    "QueryResult",
    "QueryState",
    "getRetryDelay",
    "is_api_retryable_error",
    # Message Builder
    "MessageBuilder",
    "build_messages",
    "build_system_prompt",
    # Tool Executor
    "ToolExecutor",
    "StreamingToolExecutor",
    "execute_tool",
    "execute_tools",
    "is_retryable_error",
    "calculate_retry_delay",
]
