"""
OpenAI API adapter.

This module provides an adapter for the OpenAI API with
message format conversion and response parsing.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..types.message import (
    AssistantMessage,
    Message,
    MessageConverter,
    ToolCall,
)
from ..types.tool import ToolDefinition


class OpenAIAdapter:
    """
    OpenAI API adapter.

    Provides utilities for converting messages and tools
    to OpenAI API format and parsing responses.
    """

    @staticmethod
    def convert_messages(messages: List[Message]) -> List[Dict[str, Any]]:
        """
        Convert messages to OpenAI format.

        Args:
            messages: List of messages to convert

        Returns:
            List of messages in OpenAI format
        """
        return MessageConverter.to_openai_messages(messages)

    @staticmethod
    def convert_tools(tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        """
        Convert tools to OpenAI format.

        Args:
            tools: List of tool definitions

        Returns:
            List of tools in OpenAI format
        """
        return [tool.to_openai_format() for tool in tools]

    @staticmethod
    def parse_response(response: Dict[str, Any]) -> AssistantMessage:
        """
        Parse OpenAI API response.

        Args:
            response: Response from OpenAI API

        Returns:
            AssistantMessage instance
        """
        choice = response.get("choices", [{}])[0]
        message = choice.get("message", {})

        content = message.get("content")
        tool_calls = None

        if "tool_calls" in message:
            tool_calls = [
                ToolCall(
                    id=tc.get("id", ""),
                    type=tc.get("type", "function"),
                    function=tc.get("function", {}),
                )
                for tc in message["tool_calls"]
            ]

        usage = response.get("usage", {})

        return AssistantMessage(
            content=content,
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            stop_reason=choice.get("finish_reason"),
        )

    @staticmethod
    def parse_stream_chunk(chunk: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse a streaming chunk from OpenAI API.

        Args:
            chunk: Streaming chunk from OpenAI API

        Returns:
            Parsed chunk data or None if no content
        """
        choices = chunk.get("choices", [])
        if not choices:
            return None

        delta = choices[0].get("delta", {})
        finish_reason = choices[0].get("finish_reason")

        result: Dict[str, Any] = {}

        if "content" in delta:
            result["content"] = delta["content"]

        if "tool_calls" in delta:
            result["tool_calls"] = delta["tool_calls"]

        if finish_reason:
            result["finish_reason"] = finish_reason

        return result if result else None

    @staticmethod
    def build_request_params(
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Build request parameters for OpenAI API.

        Args:
            model: Model identifier
            messages: List of messages in OpenAI format
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            tools: List of tools in OpenAI format
            tool_choice: Tool choice strategy
            **kwargs: Additional parameters

        Returns:
            Dictionary of request parameters
        """
        params: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            **kwargs,
        }

        if max_tokens:
            params["max_tokens"] = max_tokens

        if tools:
            params["tools"] = tools

        if tool_choice:
            params["tool_choice"] = tool_choice

        return params

    @staticmethod
    def format_tool_result(
        tool_call_id: str,
        content: str,
        is_error: bool = False,
    ) -> Dict[str, Any]:
        """
        Format a tool result for OpenAI API.

        Args:
            tool_call_id: ID of the tool call
            content: Result content
            is_error: Whether the result is an error

        Returns:
            Tool result message in OpenAI format
        """
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        }

    @staticmethod
    def format_system_message(content: str) -> Dict[str, Any]:
        """
        Format a system message for OpenAI API.

        Args:
            content: System message content

        Returns:
            System message in OpenAI format
        """
        return {
            "role": "system",
            "content": content,
        }

    @staticmethod
    def format_user_message(
        content: str,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Format a user message for OpenAI API.

        Args:
            content: User message content
            name: Optional user name

        Returns:
            User message in OpenAI format
        """
        message: Dict[str, Any] = {
            "role": "user",
            "content": content,
        }

        if name:
            message["name"] = name

        return message

    @staticmethod
    def format_assistant_message(
        content: Optional[str] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Format an assistant message for OpenAI API.

        Args:
            content: Assistant message content
            tool_calls: Optional tool calls
            name: Optional assistant name

        Returns:
            Assistant message in OpenAI format
        """
        message: Dict[str, Any] = {
            "role": "assistant",
        }

        if content:
            message["content"] = content

        if tool_calls:
            message["tool_calls"] = tool_calls

        if name:
            message["name"] = name

        return message
