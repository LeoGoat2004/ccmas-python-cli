"""
Type definitions for CCMAS.

This module exports all type definitions for messages, agents, and tools.
"""

# Message types
from ccmas.types.message import (
    AssistantMessage,
    BaseMessage,
    ContentBlock,
    ContentBlockType,
    ImageURLContentBlock,
    Message,
    MessageConverter,
    MessageRole,
    SystemMessage,
    TextContentBlock,
    ToolCall,
    ToolMessage,
    ToolResultContentBlock,
    ToolUseContentBlock,
    UserMessage,
    create_assistant_message,
    create_tool_message,
    create_user_message,
)

# Agent types
from ccmas.types.agent import (
    AgentContext,
    AgentType,
    SubagentContext,
    TeammateAgentContext,
    consume_invoking_request_id,
    get_subagent_log_name,
    is_subagent_context,
    is_teammate_context,
)

# Tool types
from ccmas.types.tool import (
    ToolDefinition,
    ToolInput,
    ToolOutput,
    ToolPermission,
    ToolRegistry,
    ToolResult,
    ToolType,
    create_tool_definition,
    create_tool_input,
    create_tool_output,
    create_tool_result,
)

__all__ = [
    # Message types
    "MessageRole",
    "ContentBlockType",
    "TextContentBlock",
    "ImageURLContentBlock",
    "ToolCall",
    "ToolUseContentBlock",
    "ToolResultContentBlock",
    "ContentBlock",
    "BaseMessage",
    "UserMessage",
    "AssistantMessage",
    "ToolMessage",
    "SystemMessage",
    "Message",
    "MessageConverter",
    "create_user_message",
    "create_assistant_message",
    "create_tool_message",
    # Agent types
    "AgentType",
    "SubagentContext",
    "TeammateAgentContext",
    "AgentContext",
    "is_subagent_context",
    "is_teammate_context",
    "get_subagent_log_name",
    "consume_invoking_request_id",
    # Tool types
    "ToolType",
    "ToolDefinition",
    "ToolInput",
    "ToolOutput",
    "ToolResult",
    "ToolPermission",
    "ToolRegistry",
    "create_tool_definition",
    "create_tool_input",
    "create_tool_output",
    "create_tool_result",
]
