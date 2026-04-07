"""
Query main loop implementation.

This module provides the main query loop for the CCMAS system,
handling message processing, tool execution, and conversation flow.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional, Union
from uuid import uuid4

from ccmas.llm.client import LLMClient
from ccmas.query.message_builder import MessageBuilder
from ccmas.query.tool_executor import StreamingToolExecutor, ToolExecutor
from ccmas.types.message import (
    AssistantMessage,
    Message,
    SystemMessage,
    ToolCall,
    ToolMessage,
    UserMessage,
)


class QueryState(str, Enum):
    """Query loop state enumeration."""

    RUNNING = "running"
    COMPLETED = "completed"
    ABORTED = "aborted"
    ERROR = "error"
    MAX_TURNS_REACHED = "max_turns_reached"


@dataclass
class QueryResult:
    """
    Result of a query execution.

    Contains the final state and any output messages.
    """

    state: QueryState
    messages: List[Message] = field(default_factory=list)
    error: Optional[str] = None
    turn_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryConfig:
    """
    Configuration for query execution.

    Controls the behavior of the query loop.
    """

    max_turns: int = 100
    max_tokens: Optional[int] = None
    temperature: float = 0.7
    timeout: float = 300.0
    max_concurrent_tools: int = 10
    enable_streaming: bool = True
    abort_on_error: bool = False


class QueryLoop:
    """
    Main query loop for conversation management.

    Handles the conversation flow between user, assistant, and tools,
    managing state and execution across multiple turns.
    """

    def __init__(
        self,
        client: LLMClient,
        config: Optional[QueryConfig] = None,
        system_prompt: Optional[str] = None,
        user_context: Optional[Dict[str, str]] = None,
        system_context: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the query loop.

        Args:
            client: LLM client for generating responses
            config: Query configuration
            system_prompt: Base system prompt
            user_context: User context variables
            system_context: System context variables
        """
        self.client = client
        self.config = config or QueryConfig()
        self.message_builder = MessageBuilder(
            system_prompt=system_prompt,
            user_context=user_context,
            system_context=system_context,
        )

        # State tracking
        self.messages: List[Message] = []
        self.turn_count = 0
        self.state = QueryState.RUNNING
        self.abort_signal = asyncio.Event()

        # Tool executor
        self.tool_executor: Optional[StreamingToolExecutor] = None

    async def query(
        self,
        messages: List[Message],
    ) -> AsyncIterator[Union[Message, str]]:
        """
        Execute the query loop.

        This is the main entry point for running a query.

        Args:
            messages: Initial messages for the conversation

        Yields:
            Messages and content chunks as they are generated
        """
        self.messages = list(messages)
        self.turn_count = 0
        self.state = QueryState.RUNNING
        self.abort_signal.clear()

        # Initialize tool executor
        self.tool_executor = StreamingToolExecutor(
            max_concurrent=self.config.max_concurrent_tools,
            timeout=self.config.timeout,
        )

        try:
            while self.state == QueryState.RUNNING:
                # Check abort signal
                if self.abort_signal.is_set():
                    self.state = QueryState.ABORTED
                    break

                # Check max turns
                if self.turn_count >= self.config.max_turns:
                    self.state = QueryState.MAX_TURNS_REACHED
                    break

                # Execute one turn
                async for output in self._execute_turn():
                    yield output

                self.turn_count += 1

        except Exception as e:
            self.state = QueryState.ERROR
            error_msg = f"Query error: {e}"
            yield SystemMessage(content=error_msg)

        finally:
            # Clean up
            if self.tool_executor:
                await self.tool_executor.get_remaining_results()

    async def _execute_turn(self) -> AsyncIterator[Union[Message, str]]:
        """
        Execute a single turn of the query loop.

        Yields:
            Messages and content chunks for this turn
        """
        # Build messages for API
        openai_messages = self.message_builder.build_messages(self.messages)
        system = self.message_builder.build_system_prompt()

        # Get assistant response
        if self.config.enable_streaming:
            async for output in self._stream_response(openai_messages, system):
                yield output
        else:
            async for output in self._complete_response(openai_messages, system):
                yield output

    async def _stream_response(
        self,
        messages: List[Dict[str, Any]],
        system: str,
    ) -> AsyncIterator[Union[Message, str]]:
        """
        Stream the assistant response.

        Args:
            messages: Messages in OpenAI format
            system: System prompt

        Yields:
            Content chunks and messages
        """
        # Convert messages back to Message objects for the client
        msg_objects = self._convert_openai_messages(messages)

        # Stream response
        accumulated_content = []
        tool_calls: List[ToolCall] = []

        try:
            async for chunk in self.client.stream_with_tools(
                msg_objects,
                system=system,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            ):
                if isinstance(chunk, str):
                    # Text content
                    accumulated_content.append(chunk)
                    yield chunk
                elif isinstance(chunk, ToolCall):
                    # Tool call
                    tool_calls.append(chunk)

        except Exception as e:
            yield SystemMessage(content=f"Streaming error: {e}")
            return

        # Create assistant message
        content = "".join(accumulated_content) if accumulated_content else None
        assistant_msg = AssistantMessage(
            content=content,
            tool_calls=tool_calls if tool_calls else None,
        )
        self.messages.append(assistant_msg)
        yield assistant_msg

        # Execute tools if any
        if tool_calls:
            async for output in self._execute_tools(tool_calls):
                yield output

    async def _complete_response(
        self,
        messages: List[Dict[str, Any]],
        system: str,
    ) -> AsyncIterator[Union[Message, str]]:
        """
        Get a complete assistant response (non-streaming).

        Args:
            messages: Messages in OpenAI format
            system: System prompt

        Yields:
            Messages
        """
        # Convert messages back to Message objects
        msg_objects = self._convert_openai_messages(messages)

        # Get complete response
        try:
            assistant_msg = await self.client.complete(
                msg_objects,
                system=system,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
            self.messages.append(assistant_msg)
            yield assistant_msg

            # Execute tools if any
            if assistant_msg.tool_calls:
                async for output in self._execute_tools(assistant_msg.tool_calls):
                    yield output

        except Exception as e:
            yield SystemMessage(content=f"Completion error: {e}")

    async def _execute_tools(
        self,
        tool_calls: List[ToolCall],
    ) -> AsyncIterator[Message]:
        """
        Execute tool calls and yield results.

        Args:
            tool_calls: List of tool calls to execute

        Yields:
            Tool messages with results
        """
        if not self.tool_executor:
            return

        # Execute tools
        results = await self.tool_executor.execute_tools(
            tool_calls,
            abort_signal=self.abort_signal,
        )

        # Convert results to messages
        tool_messages = self.tool_executor.handle_tool_results(results)

        # Add to message history and yield
        for msg in tool_messages:
            self.messages.append(msg)
            yield msg

    def _convert_openai_messages(
        self,
        messages: List[Dict[str, Any]],
    ) -> List[Message]:
        """
        Convert OpenAI format messages back to Message objects.

        Args:
            messages: Messages in OpenAI format

        Returns:
            List of Message objects
        """
        result = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if role == "user":
                result.append(UserMessage(content=content or ""))
            elif role == "assistant":
                tool_calls = None
                if "tool_calls" in msg:
                    tool_calls = [
                        ToolCall(**tc) for tc in msg["tool_calls"]
                    ]
                result.append(AssistantMessage(
                    content=content,
                    tool_calls=tool_calls,
                ))
            elif role == "tool":
                result.append(ToolMessage(
                    tool_call_id=msg.get("tool_call_id", ""),
                    content=content or "",
                ))
            elif role == "system":
                result.append(SystemMessage(content=content or ""))

        return result

    def abort(self) -> None:
        """Abort the query loop."""
        self.abort_signal.set()
        self.state = QueryState.ABORTED

    def get_result(self) -> QueryResult:
        """
        Get the result of the query execution.

        Returns:
            QueryResult with final state and messages
        """
        return QueryResult(
            state=self.state,
            messages=self.messages,
            turn_count=self.turn_count,
        )


async def query(
    client: LLMClient,
    messages: List[Message],
    system_prompt: Optional[str] = None,
    user_context: Optional[Dict[str, str]] = None,
    system_context: Optional[Dict[str, str]] = None,
    config: Optional[QueryConfig] = None,
) -> AsyncIterator[Union[Message, str]]:
    """
    Execute a query with the given client and messages.

    Convenience function that creates a QueryLoop and runs it.

    Args:
        client: LLM client for generating responses
        messages: Initial messages for the conversation
        system_prompt: Base system prompt
        user_context: User context variables
        system_context: System context variables
        config: Query configuration

    Yields:
        Messages and content chunks as they are generated
    """
    loop = QueryLoop(
        client=client,
        config=config,
        system_prompt=system_prompt,
        user_context=user_context,
        system_context=system_context,
    )

    async for output in loop.query(messages):
        yield output
