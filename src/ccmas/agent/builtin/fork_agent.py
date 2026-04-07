"""
Fork Agent definition.

This module defines the Fork Agent, which creates a child agent that inherits
from the parent agent with specific capabilities and permissions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

from ccmas.agent.definition import (
    AgentConfig,
    AgentKind,
    ForkAgentDefinition,
    PermissionModeType,
)
from ccmas.types.message import ContentBlock, UserMessage


# Tag for identifying fork agent boilerplate in messages
FORK_BOILERPLATE_TAG = "<fork_boilerplate>"

# Fork agent system prompt
FORK_SYSTEM_PROMPT = """You are a forked agent that inherits capabilities from your parent agent.
You have access to the same tools and can perform tasks on behalf of your parent.
Complete the assigned task and report back with your results."""


def create_fork_agent_config(
    tools: List[str] = None,
    permission_mode: PermissionModeType = PermissionModeType.BUBBLE,
    model: Optional[str] = "inherit",
) -> AgentConfig:
    """
    Create configuration for a fork agent.

    Args:
        tools: List of tool names (default: all tools)
        permission_mode: Permission mode (default: bubble)
        model: Model to use (default: inherit from parent)

    Returns:
        AgentConfig for fork agent
    """
    return AgentConfig(
        model=model,
        tools=tools or ["*"],
        permission_mode=permission_mode,
        system_prompt=FORK_SYSTEM_PROMPT,
        metadata={
            "is_fork": True,
            "fork_version": "1.0.0",
        },
    )


# Fork Agent Definition
FORK_AGENT = ForkAgentDefinition(
    name="fork",
    description="Fork agent that creates a child agent inheriting from the parent. Used for spawning subagents with specific capabilities.",
    kind=AgentKind.FORK,
    config=create_fork_agent_config(),
    version="1.0.0",
    tags=["builtin", "fork", "subagent"],
    examples=[
        "fork: Explore the codebase structure",
        "fork: Implement the feature and run tests",
        "fork: Review the changes and provide feedback",
    ],
)


def build_child_message(
    parent_message: UserMessage,
    task: str,
    context: Optional[Dict[str, Any]] = None,
) -> UserMessage:
    """
    Build a child message for the forked agent.

    Creates a message that will be sent to the forked child agent,
    including the task and relevant context from the parent.

    Args:
        parent_message: The parent message that triggered the fork
        task: The task description for the child agent
        context: Additional context to pass to the child

    Returns:
        UserMessage for the child agent
    """
    # Generate unique ID for the child message
    child_id = str(uuid4())

    # Build message content
    content_parts: List[ContentBlock] = []

    # Add task as the main content
    if isinstance(parent_message.content, str):
        content_parts.append({
            "type": "text",
            "text": f"{FORK_BOILERPLATE_TAG}\nTask: {task}\n\n{parent_message.content}",
        })
    elif isinstance(parent_message.content, list):
        # Add fork boilerplate first
        content_parts.append({
            "type": "text",
            "text": f"{FORK_BOILERPLATE_TAG}\nTask: {task}",
        })
        # Add original content blocks
        content_parts.extend(parent_message.content)

    # Add context if provided
    if context:
        context_text = "\n\nContext:\n"
        for key, value in context.items():
            context_text += f"- {key}: {value}\n"
        content_parts.append({
            "type": "text",
            "text": context_text,
        })

    return UserMessage(
        content=content_parts if len(content_parts) > 1 else (
            content_parts[0]["text"] if content_parts else task
        ),
        name=f"fork_child_{child_id[:8]}",
        is_meta=False,
        metadata={
            "fork_child_id": child_id,
            "fork_parent_message_id": str(parent_message.uuid),
            "fork_task": task,
            **(context or {}),
        },
    )


def create_fork_agent_instance(
    task: str,
    tools: Optional[List[str]] = None,
    permission_mode: Optional[PermissionModeType] = None,
    model: Optional[str] = None,
    parent_context: Optional[Any] = None,
) -> ForkAgentDefinition:
    """
    Create a fork agent instance with custom configuration.

    Args:
        task: The task for the fork agent
        tools: List of tool names (default: all tools)
        permission_mode: Permission mode (default: bubble)
        model: Model to use (default: inherit)
        parent_context: Parent agent context

    Returns:
        ForkAgentDefinition instance
    """
    config = create_fork_agent_config(
        tools=tools,
        permission_mode=permission_mode or PermissionModeType.BUBBLE,
        model=model or "inherit",
    )

    return ForkAgentDefinition(
        name=f"fork_{task[:20].replace(' ', '_').lower()}",
        description=f"Fork agent for task: {task}",
        kind=AgentKind.FORK,
        config=config,
        parent_context=parent_context,
        version="1.0.0",
        tags=["fork", "subagent", task[:20]],
    )


def is_fork_message(message: UserMessage) -> bool:
    """
    Check if a message is from a fork agent.

    Args:
        message: The message to check

    Returns:
        True if the message is from a fork agent
    """
    if isinstance(message.content, str):
        return FORK_BOILERPLATE_TAG in message.content
    elif isinstance(message.content, list):
        for block in message.content:
            if isinstance(block, dict) and block.get("type") == "text":
                if FORK_BOILERPLATE_TAG in block.get("text", ""):
                    return True
    return False


def extract_fork_task(message: UserMessage) -> Optional[str]:
    """
    Extract the fork task from a message.

    Args:
        message: The message to extract from

    Returns:
        The task string or None if not found
    """
    content = ""
    if isinstance(message.content, str):
        content = message.content
    elif isinstance(message.content, list):
        for block in message.content:
            if isinstance(block, dict) and block.get("type") == "text":
                content = block.get("text", "")
                break

    if FORK_BOILERPLATE_TAG not in content:
        return None

    # Extract task from the message
    lines = content.split("\n")
    for line in lines:
        if line.startswith("Task:"):
            return line[5:].strip()

    return None
