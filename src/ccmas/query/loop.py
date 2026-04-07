"""
Query main loop implementation.

This module provides the main query loop for the CCMAS system,
handling message processing, tool execution, and conversation flow.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from ccmas.llm.client import LLMClient
from ccmas.memory.state_manager import RecoveryManager, get_state_manager
from ccmas.query.token_budget import (
    BudgetTracker,
    ContinueDecision,
    StopDecision,
    TokenBudgetDecision,
    check_token_budget,
    parse_token_budget,
)
from ccmas.query.compact import (
    compact_messages,
    estimate_tokens_for_messages,
    is_compact_boundary_message,
    build_post_compact_messages,
    CompactionResult,
)
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


API_RETRY_BASE_DELAY = 1.0
API_RETRY_MAX_DELAY = 60.0
API_MAX_RETRIES = 3


def is_api_retryable_error(error: Exception) -> bool:
    """Check if an API error is retryable."""
    error_msg = str(error).lower()

    retryable_statuses = ["500", "502", "503", "504", "429", "rate limit", "timeout"]

    for status in retryable_statuses:
        if status in error_msg:
            return True

    if isinstance(error, (asyncio.TimeoutError, ConnectionError, OSError)):
        return True

    return False


def getRetryDelay(attempt: int, base_delay: float = API_RETRY_BASE_DELAY, max_delay: float = API_RETRY_MAX_DELAY) -> float:
    """Calculate exponential backoff delay with jitter for API retries.

    Args:
        attempt: Current retry attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Delay in seconds
    """
    delay = min(base_delay * (2 ** attempt), max_delay)
    jitter = delay * 0.1 * random.random()
    return delay + jitter


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
    token_budget: Optional[int] = None
    enable_recovery: bool = True
    workspace: str = "default"
    auto_save_interval: int = 10
    auto_compact_enabled: bool = True
    compact_token_threshold: int = 80000
    compact_recent_count: int = 20
    suppress_compact_follow_questions: bool = True


def check_budget_and_continue(
    tracker: BudgetTracker,
    agent_id: Optional[str],
    budget: Optional[int],
    global_turn_tokens: int,
) -> TokenBudgetDecision:
    return check_token_budget(tracker, agent_id, budget, global_turn_tokens)


def send_nudge_message(decision: ContinueDecision) -> SystemMessage:
    return SystemMessage(content=decision.nudge_message)


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

        # Budget tracking
        self.budget_tracker: Optional[BudgetTracker] = None
        self.global_turn_tokens: int = 0

        # Recovery management
        self._recovery_manager: Optional[RecoveryManager] = None
        self._checkpoint_id: Optional[str] = None
        self._turns_since_last_save: int = 0

    async def query(
        self,
        messages: List[Message],
        restore_checkpoint_id: Optional[str] = None,
    ) -> AsyncIterator[Union[Message, str]]:
        """
        Execute the query loop.

        This is the main entry point for running a query.

        Args:
            messages: Initial messages for the conversation
            restore_checkpoint_id: Optional checkpoint ID to restore from

        Yields:
            Messages and content chunks as they are generated
        """
        if restore_checkpoint_id:
            restored_state = self._restore_from_checkpoint(restore_checkpoint_id)
            if restored_state:
                self.messages = restored_state["messages"]
                self.turn_count = restored_state["turn_count"]
                self.state = restored_state["state"]
                self.global_turn_tokens = restored_state["global_turn_tokens"]
                yield SystemMessage(
                    content=f"[Recovery] Restored from checkpoint. Resuming from turn {self.turn_count}..."
                )
        else:
            self.messages = list(messages)
            self.turn_count = 0
            self.state = QueryState.RUNNING

        self.abort_signal.clear()
        self.global_turn_tokens = 0
        self._turns_since_last_save = 0

        if self.config.token_budget:
            self.budget_tracker = BudgetTracker.create()
        else:
            self.budget_tracker = None

        self.tool_executor = StreamingToolExecutor(
            max_concurrent=self.config.max_concurrent_tools,
            timeout=self.config.timeout,
        )

        if self.config.enable_recovery:
            self._recovery_manager = RecoveryManager(get_state_manager())
            self._save_checkpoint()

        try:
            while self.state == QueryState.RUNNING:
                if self.abort_signal.is_set():
                    self.state = QueryState.ABORTED
                    break

                if self.turn_count >= self.config.max_turns:
                    self.state = QueryState.MAX_TURNS_REACHED
                    break

                async for output in self._execute_turn():
                    yield output

                self.turn_count += 1
                self._turns_since_last_save += 1

                if self.budget_tracker:
                    self.global_turn_tokens = estimate_tokens_for_messages(
                        self.message_builder.build_messages(self.messages)
                    )

                if self.budget_tracker and self.config.token_budget:
                    decision = check_budget_and_continue(
                        self.budget_tracker,
                        None,
                        self.config.token_budget,
                        self.global_turn_tokens,
                    )
                    if decision.action == 'stop':
                        self.state = QueryState.COMPLETED
                        break
                    elif isinstance(decision, ContinueDecision) and decision.nudge_message:
                        yield send_nudge_message(decision)

                if (self.config.enable_recovery and
                    self._turns_since_last_save >= self.config.auto_save_interval):
                    self._save_checkpoint()
                    self._turns_since_last_save = 0

        except Exception as e:
            self.state = QueryState.ERROR
            error_msg = f"Query error: {e}"
            yield SystemMessage(content=error_msg)

        finally:
            if self.tool_executor:
                await self.tool_executor.get_remaining_results()

            if self.config.enable_recovery and self._checkpoint_id:
                self._save_checkpoint()

    def _restore_from_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Restore state from a checkpoint."""
        try:
            recovery_manager = RecoveryManager(get_state_manager())
            checkpoint = recovery_manager._state_manager.load_checkpoint(checkpoint_id)
            return recovery_manager.restore_from_checkpoint(checkpoint)
        except Exception:
            return None

    def _save_checkpoint(self) -> Optional[str]:
        """Save current state to a checkpoint."""
        if not self._recovery_manager:
            return None
        try:
            checkpoint = self._recovery_manager.save_recovery_checkpoint(
                workspace=self.config.workspace,
                messages=self.messages,
                turn_count=self.turn_count,
                state=self.state.value,
                global_turn_tokens=self.global_turn_tokens,
            )
            self._checkpoint_id = checkpoint.checkpoint_id
            return checkpoint.checkpoint_id
        except Exception:
            return None

    async def _execute_turn(self) -> AsyncIterator[Union[Message, str]]:
        """
        Execute a single turn of the query loop.

        Yields:
            Messages and content chunks for this turn
        """
        # Check if compaction is needed before API call
        if self.should_compact():
            compaction_result = self.run_compaction()
            yield SystemMessage(
                content=f"[AutoCompact] Conversation compacted. "
                        f"Pre-compact tokens: {compaction_result.pre_compact_token_count}, "
                        f"Post-compact tokens: {compaction_result.true_post_compact_token_count}"
            )

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
        Stream the assistant response with retry logic.

        Args:
            messages: Messages in OpenAI format
            system: System prompt

        Yields:
            Content chunks and messages
        """
        msg_objects = self._convert_openai_messages(messages)

        accumulated_content = []
        tool_calls: List[ToolCall] = []
        last_error: Optional[Exception] = None

        for attempt in range(API_MAX_RETRIES + 1):
            try:
                async for chunk in self.client.stream_with_tools(
                    msg_objects,
                    system=system,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                ):
                    if isinstance(chunk, str):
                        accumulated_content.append(chunk)
                        yield chunk
                    elif isinstance(chunk, ToolCall):
                        tool_calls.append(chunk)

                break

            except Exception as e:
                last_error = e
                if is_api_retryable_error(e) and attempt < API_MAX_RETRIES:
                    delay = getRetryDelay(attempt)
                    yield SystemMessage(
                        content=f"[API Retry] Attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                    continue
                yield SystemMessage(content=f"Streaming error: {e}")
                return

        content = "".join(accumulated_content) if accumulated_content else None
        assistant_msg = AssistantMessage(
            content=content,
            tool_calls=tool_calls if tool_calls else None,
        )
        self.messages.append(assistant_msg)
        yield assistant_msg

        if tool_calls:
            async for output in self._execute_tools(tool_calls):
                yield output

    async def _complete_response(
        self,
        messages: List[Dict[str, Any]],
        system: str,
    ) -> AsyncIterator[Union[Message, str]]:
        """
        Get a complete assistant response (non-streaming) with retry logic.

        Args:
            messages: Messages in OpenAI format
            system: System prompt

        Yields:
            Messages
        """
        msg_objects = self._convert_openai_messages(messages)
        last_error: Optional[Exception] = None

        for attempt in range(API_MAX_RETRIES + 1):
            try:
                assistant_msg = await self.client.complete(
                    msg_objects,
                    system=system,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
                self.messages.append(assistant_msg)
                yield assistant_msg

                if assistant_msg.tool_calls:
                    async for output in self._execute_tools(assistant_msg.tool_calls):
                        yield output
                break

            except Exception as e:
                last_error = e
                if is_api_retryable_error(e) and attempt < API_MAX_RETRIES:
                    delay = getRetryDelay(attempt)
                    yield SystemMessage(
                        content=f"[API Retry] Attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                    continue
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
                subtype = msg.get("subtype")
                compact_metadata = msg.get("compact_metadata")
                result.append(SystemMessage(
                    content=content or "",
                    subtype=subtype,
                    compact_metadata=compact_metadata,
                ))

        return result

    def abort(self) -> None:
        """Abort the query loop."""
        self.abort_signal.set()
        self.state = QueryState.ABORTED

    def should_compact(self) -> bool:
        """
        Check if conversation should be compacted.

        Returns:
            True if compaction is needed based on token count
        """
        if not self.config.auto_compact_enabled:
            return False

        if len(self.messages) < 2:
            return False

        token_count = estimate_tokens_for_messages(self.messages)
        return token_count >= self.config.compact_token_threshold

    def run_compaction(self) -> CompactionResult:
        """
        Execute the compaction process.

        Returns:
            CompactionResult containing compacted messages and metadata
        """
        def summarize_callback(prompt: str) -> str:
            result: List[str] = []
            return ""

        result = compact_messages(
            messages=self.messages,
            recent_count=self.config.compact_recent_count,
            summarize_callback=summarize_callback,
            suppress_follow_up_questions=self.config.suppress_compact_follow_questions,
        )

        compacted = build_post_compact_messages(result)
        self.messages = compacted

        return result

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
