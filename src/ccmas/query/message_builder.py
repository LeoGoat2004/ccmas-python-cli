"""
OpenAI format message builder.

This module provides utilities for building messages in OpenAI API format,
including system prompts and conversation messages.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from ccmas.types.message import (
    AssistantMessage,
    ContentBlock,
    Message,
    SystemMessage,
    ToolMessage,
    UserMessage,
)


class MessageBuilder:
    """
    Builder for OpenAI format messages.

    Provides methods to construct messages for the OpenAI API,
    including system prompts and conversation history.
    """

    def __init__(
        self,
        system_prompt: Optional[str] = None,
        user_context: Optional[Dict[str, str]] = None,
        system_context: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the message builder.

        Args:
            system_prompt: Base system prompt
            user_context: User context variables to prepend
            system_context: System context variables to append
        """
        self.system_prompt = system_prompt
        self.user_context = user_context or {}
        self.system_context = system_context or {}

    def build_system_prompt(self) -> str:
        """
        Build the complete system prompt.

        Combines the base system prompt with system context.

        Returns:
            Complete system prompt string
        """
        parts = []

        if self.system_prompt:
            parts.append(self.system_prompt)

        # Append system context
        if self.system_context:
            context_parts = []
            for key, value in self.system_context.items():
                context_parts.append(f"{key}: {value}")
            if context_parts:
                parts.append("\n\n".join(context_parts))

        return "\n\n".join(parts) if parts else ""

    def build_messages(
        self,
        messages: List[Message],
        prepend_user_context: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Build messages in OpenAI API format.

        Args:
            messages: List of Message objects
            prepend_user_context: Whether to prepend user context

        Returns:
            List of messages in OpenAI format
        """
        openai_messages: List[Dict[str, Any]] = []

        # Prepend user context if enabled
        if prepend_user_context and self.user_context:
            context_content = self._format_user_context()
            if context_content:
                openai_messages.append({
                    "role": "user",
                    "content": context_content,
                })

        # Convert messages to OpenAI format
        for msg in messages:
            openai_msg = self._convert_message(msg)
            if openai_msg:
                openai_messages.append(openai_msg)

        return openai_messages

    def _format_user_context(self) -> str:
        """
        Format user context as a string.

        Returns:
            Formatted user context string
        """
        if not self.user_context:
            return ""

        parts = []
        for key, value in self.user_context.items():
            parts.append(f"{key}: {value}")

        return "\n".join(parts)

    def _convert_message(self, msg: Message) -> Optional[Dict[str, Any]]:
        """
        Convert a Message object to OpenAI format.

        Args:
            msg: Message object to convert

        Returns:
            Message in OpenAI format, or None if conversion fails
        """
        if isinstance(msg, UserMessage):
            return self._convert_user_message(msg)
        elif isinstance(msg, AssistantMessage):
            return self._convert_assistant_message(msg)
        elif isinstance(msg, ToolMessage):
            return self._convert_tool_message(msg)
        elif isinstance(msg, SystemMessage):
            return self._convert_system_message(msg)
        else:
            return None

    def _convert_user_message(self, msg: UserMessage) -> Dict[str, Any]:
        """
        Convert a UserMessage to OpenAI format.

        Args:
            msg: UserMessage to convert

        Returns:
            Message in OpenAI format
        """
        result: Dict[str, Any] = {
            "role": "user",
        }

        # Handle content
        if isinstance(msg.content, str):
            result["content"] = msg.content
        elif isinstance(msg.content, list):
            # Convert content blocks
            result["content"] = self._convert_content_blocks(msg.content)

        if msg.name:
            result["name"] = msg.name

        return result

    def _convert_assistant_message(self, msg: AssistantMessage) -> Dict[str, Any]:
        """
        Convert an AssistantMessage to OpenAI format.

        Args:
            msg: AssistantMessage to convert

        Returns:
            Message in OpenAI format
        """
        result: Dict[str, Any] = {
            "role": "assistant",
        }

        # Handle content
        if msg.content:
            if isinstance(msg.content, str):
                result["content"] = msg.content
            elif isinstance(msg.content, list):
                # For assistant messages, extract text content
                text_parts = []
                for block in msg.content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif hasattr(block, "type") and block.type == "text":
                        text_parts.append(block.text)
                result["content"] = "\n".join(text_parts) if text_parts else None

        if msg.name:
            result["name"] = msg.name

        # Handle tool calls
        if msg.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": tc.function,
                }
                for tc in msg.tool_calls
            ]

        return result

    def _convert_tool_message(self, msg: ToolMessage) -> Dict[str, Any]:
        """
        Convert a ToolMessage to OpenAI format.

        Args:
            msg: ToolMessage to convert

        Returns:
            Message in OpenAI format
        """
        result: Dict[str, Any] = {
            "role": "tool",
            "tool_call_id": msg.tool_call_id,
        }

        # Handle content
        if isinstance(msg.content, str):
            result["content"] = msg.content
        elif isinstance(msg.content, list):
            result["content"] = self._convert_content_blocks(msg.content)

        if msg.name:
            result["name"] = msg.name

        return result

    def _convert_system_message(self, msg: SystemMessage) -> Dict[str, Any]:
        """
        Convert a SystemMessage to OpenAI format.

        Args:
            msg: SystemMessage to convert

        Returns:
            Message in OpenAI format
        """
        result: Dict[str, Any] = {
            "role": "system",
        }

        if msg.content:
            result["content"] = msg.content

        if msg.subtype:
            result["subtype"] = msg.subtype

        if hasattr(msg, "compact_metadata") and msg.compact_metadata:
            result["compact_metadata"] = msg.compact_metadata

        return result

    def _convert_content_blocks(
        self, blocks: List[ContentBlock]
    ) -> List[Dict[str, Any]]:
        """
        Convert content blocks to OpenAI format.

        Args:
            blocks: List of content blocks

        Returns:
            List of content blocks in OpenAI format
        """
        result = []
        for block in blocks:
            if isinstance(block, dict):
                result.append(block)
            elif hasattr(block, "model_dump"):
                result.append(block.model_dump())
            else:
                # Try to convert to dict
                try:
                    result.append(dict(block))
                except (TypeError, ValueError):
                    # Skip blocks that can't be converted
                    pass
        return result


def build_messages(
    messages: List[Message],
    system_prompt: Optional[str] = None,
    user_context: Optional[Dict[str, str]] = None,
    system_context: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """
    Build messages in OpenAI API format.

    Convenience function that creates a MessageBuilder and builds messages.

    Args:
        messages: List of Message objects
        system_prompt: Base system prompt
        user_context: User context variables
        system_context: System context variables

    Returns:
        List of messages in OpenAI format
    """
    builder = MessageBuilder(
        system_prompt=system_prompt,
        user_context=user_context,
        system_context=system_context,
    )
    return builder.build_messages(messages)


def build_system_prompt(
    base_prompt: str,
    system_context: Optional[Dict[str, str]] = None,
) -> str:
    """
    Build a complete system prompt.

    Convenience function that creates a MessageBuilder and builds system prompt.

    Args:
        base_prompt: Base system prompt
        system_context: System context variables

    Returns:
        Complete system prompt string
    """
    builder = MessageBuilder(
        system_prompt=base_prompt,
        system_context=system_context,
    )
    return builder.build_system_prompt()
