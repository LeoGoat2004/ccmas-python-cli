"""
LLM client implementations.

This module provides base client class and OpenAI-compatible client implementations
with support for streaming responses and tool calling.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from openai import AsyncOpenAI

from ..types.message import (
    AssistantMessage,
    Message,
    MessageConverter,
    ToolCall,
)
from ..types.tool import ToolDefinition, ToolRegistry


class LLMClient(ABC):
    """
    Base class for LLM clients.

    Defines the interface for LLM clients with support for
    streaming responses and tool calling.
    """

    def __init__(
        self,
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize LLM client.

        Args:
            model: Model identifier
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            tools: List of available tools
            **kwargs: Additional model-specific parameters
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.tool_registry = ToolRegistry()
        self.extra_params = kwargs

        if tools:
            for tool in tools:
                self.tool_registry.register(tool)

    def register_tool(self, tool: ToolDefinition) -> None:
        """
        Register a tool.

        Args:
            tool: Tool definition to register
        """
        self.tool_registry.register(tool)

    def unregister_tool(self, name: str) -> Optional[ToolDefinition]:
        """
        Unregister a tool.

        Args:
            name: Name of the tool to unregister

        Returns:
            The unregistered tool, or None if not found
        """
        return self.tool_registry.unregister(name)

    @abstractmethod
    async def complete(
        self,
        messages: List[Message],
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> AssistantMessage:
        """
        Generate a completion.

        Args:
            messages: List of messages in the conversation
            system: Optional system message
            **kwargs: Additional parameters

        Returns:
            Assistant message with the completion
        """
        pass

    @abstractmethod
    async def stream(
        self,
        messages: List[Message],
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        Generate a streaming completion.

        Args:
            messages: List of messages in the conversation
            system: Optional system message
            **kwargs: Additional parameters

        Yields:
            Chunks of the generated text
        """
        pass

    def _prepare_messages(
        self,
        messages: List[Message],
        system: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Prepare messages for API call.

        Args:
            messages: List of messages
            system: Optional system message

        Returns:
            List of messages in OpenAI format
        """
        openai_messages = []

        if system:
            openai_messages.append({"role": "system", "content": system})

        openai_messages.extend(MessageConverter.to_openai_messages(messages))

        return openai_messages

    def _prepare_tools(self) -> Optional[List[Dict[str, Any]]]:
        """
        Prepare tools for API call.

        Returns:
            List of tools in OpenAI format, or None if no tools
        """
        tools = self.tool_registry.get_all()
        return self.tool_registry.to_openai_tools() if tools else None


class OpenAIClient(LLMClient):
    """
    OpenAI API client.

    Implements the LLM client interface using the OpenAI API.
    Supports streaming responses and tool calling.
    """

    def __init__(
        self,
        model: str = "gpt-4",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize OpenAI client.

        Args:
            model: Model identifier (default: gpt-4)
            api_key: OpenAI API key (can also be set via OPENAI_API_KEY env var)
            base_url: Base URL for API (for custom endpoints)
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            tools: List of available tools
            **kwargs: Additional parameters passed to AsyncOpenAI
        """
        super().__init__(model, temperature, max_tokens, tools, **kwargs)

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            **kwargs,
        )

    async def complete(
        self,
        messages: List[Message],
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> AssistantMessage:
        """
        Generate a completion.

        Args:
            messages: List of messages in the conversation
            system: Optional system message
            **kwargs: Additional parameters

        Returns:
            Assistant message with the completion
        """
        openai_messages = self._prepare_messages(messages, system)
        tools = self._prepare_tools()

        # Merge extra params with kwargs
        params = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": self.temperature,
            **self.extra_params,
            **kwargs,
        }

        if self.max_tokens:
            params["max_tokens"] = self.max_tokens

        if tools:
            params["tools"] = tools

        response = await self.client.chat.completions.create(**params)

        # Extract response data
        choice = response.choices[0]
        content = choice.message.content
        tool_calls = None

        if choice.message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    type=tc.type,
                    function={
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                )
                for tc in choice.message.tool_calls
            ]

        return AssistantMessage(
            content=content,
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            stop_reason=choice.finish_reason,
        )

    async def stream(
        self,
        messages: List[Message],
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        Generate a streaming completion.

        Args:
            messages: List of messages in the conversation
            system: Optional system message
            **kwargs: Additional parameters

        Yields:
            Chunks of the generated text
        """
        openai_messages = self._prepare_messages(messages, system)
        tools = self._prepare_tools()

        # Merge extra params with kwargs
        params = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": self.temperature,
            "stream": True,
            **self.extra_params,
            **kwargs,
        }

        if self.max_tokens:
            params["max_tokens"] = self.max_tokens

        if tools:
            params["tools"] = tools

        stream = await self.client.chat.completions.create(**params)

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def stream_with_tools(
        self,
        messages: List[Message],
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncIterator[Union[str, ToolCall]]:
        """
        Generate a streaming completion with tool call support.

        Args:
            messages: List of messages in the conversation
            system: Optional system message
            **kwargs: Additional parameters

        Yields:
            Chunks of the generated text or tool calls
        """
        openai_messages = self._prepare_messages(messages, system)
        tools = self._prepare_tools()

        # Merge extra params with kwargs
        params = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": self.temperature,
            "stream": True,
            **self.extra_params,
            **kwargs,
        }

        if self.max_tokens:
            params["max_tokens"] = self.max_tokens

        if tools:
            params["tools"] = tools

        stream = await self.client.chat.completions.create(**params)

        # Accumulate tool calls
        tool_calls_accumulator: Dict[int, Dict[str, Any]] = {}

        async for chunk in stream:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # Yield text content
            if delta.content:
                yield delta.content

            # Handle tool calls
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index

                    if idx not in tool_calls_accumulator:
                        tool_calls_accumulator[idx] = {
                            "id": tc.id or "",
                            "type": tc.type or "function",
                            "function": {"name": "", "arguments": ""},
                        }

                    if tc.id:
                        tool_calls_accumulator[idx]["id"] = tc.id

                    if tc.function:
                        if tc.function.name:
                            tool_calls_accumulator[idx]["function"]["name"] = tc.function.name
                        if tc.function.arguments:
                            tool_calls_accumulator[idx]["function"]["arguments"] += tc.function.arguments

        # Yield completed tool calls
        for idx in sorted(tool_calls_accumulator.keys()):
            tc_data = tool_calls_accumulator[idx]
            yield ToolCall(
                id=tc_data["id"],
                type=tc_data["type"],
                function=tc_data["function"],
            )
