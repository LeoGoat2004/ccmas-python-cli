"""
Fork subagent mechanism for spawning and managing forked agents.

This module implements the fork subagent system that allows agents to
spawn child agents with specific tasks and capabilities.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import uuid4

from ccmas.agent.builtin import FORK_BOILERPLATE_TAG
from ccmas.agent.definition import AgentConfig, ForkAgentDefinition
from ccmas.context.agent_context import SubagentContext, agent_context_var
from ccmas.teammate.tmux import TmuxWorker, TmuxMailbox
from ccmas.types.message import (
    AssistantMessage,
    Message,
    ToolResultContentBlock,
    UserMessage,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ccmas.agent.run_agent import AgentExecutor

TASK_NOTIFICATION_PATTERN = re.compile(r"<task-notification>(.*?)</task-notification>", re.DOTALL)


@dataclass
class ForkResult:
    """
    Result of a fork subagent execution.

    Contains the output and metadata from the forked agent's execution.
    """

    success: bool
    output: str
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    agent_id: Optional[str] = None
    execution_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ForkTmuxResult:
    """
    Result of a tmux-based fork subagent execution.

    Contains the output and metadata from the tmux worker's execution.
    """

    success: bool
    output: str
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    agent_id: Optional[str] = None
    execution_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    worker: Optional[TmuxWorker] = None
    mailbox: Optional[TmuxMailbox] = None


@dataclass
class PlaceholderToolResult:
    """
    Placeholder tool result for async tool execution.

    Used when a tool result is pending and will be filled in later.
    """

    tool_use_id: str
    placeholder: str = "<pending>"
    is_placeholder: bool = True


def build_forked_messages(
    parent_messages: List[Message],
    task: str,
    context: Optional[Dict[str, Any]] = None,
) -> List[Message]:
    """
    Build messages for a forked subagent.

    Creates a message history for the forked agent, including the task
    and relevant context from the parent agent.

    Args:
        parent_messages: Messages from the parent agent
        task: The task for the forked agent
        context: Additional context to pass

    Returns:
        List of messages for the forked agent
    """
    messages: List[Message] = []

    # Build the initial task message
    task_content = f"{FORK_BOILERPLATE_TAG}\n\nTask: {task}\n\n"

    # Add context if provided
    if context:
        task_content += "Context:\n"
        for key, value in context.items():
            task_content += f"- {key}: {value}\n"
        task_content += "\n"

    # Add relevant parent messages (last few for context)
    # Limit to avoid token limits
    max_parent_messages = 5
    relevant_parent = parent_messages[-max_parent_messages:] if len(parent_messages) > max_parent_messages else parent_messages

    if relevant_parent:
        task_content += "Recent context from parent agent:\n"
        for msg in relevant_parent:
            if isinstance(msg, UserMessage):
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                task_content += f"User: {content[:200]}...\n"
            elif isinstance(msg, AssistantMessage):
                content = msg.content if isinstance(msg.content, str) else str(msg.content) if msg.content else ""
                task_content += f"Assistant: {content[:200]}...\n"

    # Create the task message
    task_message = UserMessage(
        content=task_content,
        name="fork_task",
        is_meta=False,
    )
    messages.append(task_message)

    return messages


def create_placeholder_tool_result(
    tool_use_id: str,
) -> ToolResultContentBlock:
    """
    Create a placeholder tool result.

    Used when a tool result is pending and will be filled in later.

    Args:
        tool_use_id: The ID of the tool use

    Returns:
        Placeholder ToolResultContentBlock
    """
    return ToolResultContentBlock(
        type="tool_result",
        tool_use_id=tool_use_id,
        content="<pending>",
        is_error=False,
    )


def is_placeholder_result(result: Any) -> bool:
    """
    Check if a result is a placeholder.

    Args:
        result: The result to check

    Returns:
        True if the result is a placeholder
    """
    if isinstance(result, PlaceholderToolResult):
        return True
    if isinstance(result, ToolResultContentBlock):
        return result.content == "<pending>"
    if isinstance(result, dict):
        return result.get("content") == "<pending>"
    return False


class ForkSubagentManager:
    """
    Manager for fork subagents.

    Handles the lifecycle of forked agents, including spawning,
    execution, and result collection. Supports both standard and
    tmux-based fork agents.
    """

    def __init__(
        self,
        parent_context: Optional[SubagentContext] = None,
        max_concurrent_forks: int = 5,
    ):
        """
        Initialize the fork subagent manager.

        Args:
            parent_context: The parent agent's context
            max_concurrent_forks: Maximum number of concurrent fork agents
        """
        self.parent_context = parent_context
        self.max_concurrent_forks = max_concurrent_forks
        self._active_forks: Dict[str, "AgentExecutor"] = {}
        self._active_tmux_forks: Dict[str, TmuxWorker] = {}
        self._fork_results: Dict[str, ForkResult] = {}
        self._fork_tmux_results: Dict[str, ForkTmuxResult] = {}
        self._fork_counter = 0

    def create_fork_agent(
        self,
        task: str,
        config: Optional[AgentConfig] = None,
        subagent_type: Optional[str] = None,
    ) -> ForkAgentDefinition:
        """
        Create a fork agent definition for a task.

        Args:
            task: The task for the fork agent
            config: Optional custom configuration
            subagent_type: Optional subagent type ('tmux' for tmux-based fork)

        Returns:
            ForkAgentDefinition instance
        """
        self._fork_counter += 1
        fork_id = f"fork_{self._fork_counter}_{str(uuid4())[:8]}"

        fork_config = config or AgentConfig(
            model="inherit",
            tools=["*"],
            permission_mode="bubble",
        )

        if subagent_type:
            fork_config.metadata["subagent_type"] = subagent_type

        return ForkAgentDefinition(
            name=fork_id,
            description=f"Fork agent for task: {task[:50]}",
            kind="fork",
            config=fork_config,
            parent_context=self.parent_context,
        )

    def spawn_fork(
        self,
        task: str,
        messages: List[Message],
        executor: "AgentExecutor",
        context: Optional[Dict[str, Any]] = None,
        subagent_type: Optional[str] = None,
    ) -> str:
        """
        Spawn a fork subagent.

        Args:
            task: The task for the fork agent
            messages: Messages to pass to the fork agent
            executor: The agent executor to use
            context: Additional context
            subagent_type: Optional subagent type ('tmux' for tmux-based fork)

        Returns:
            The fork agent ID
        """
        if subagent_type == "tmux":
            return self.spawn_fork_tmux(task, messages, context)

        if len(self._active_forks) >= self.max_concurrent_forks:
            raise RuntimeError(
                f"Maximum concurrent forks reached ({self.max_concurrent_forks})"
            )

        fork_agent = self.create_fork_agent(task, subagent_type=subagent_type)
        fork_id = fork_agent.name

        fork_messages = build_forked_messages(messages, task, context)

        self._active_forks[fork_id] = executor

        return fork_id

    def spawn_fork_tmux(
        self,
        task: str,
        messages: List[Message],
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Spawn a tmux-based fork subagent.

        Args:
            task: The task for the fork agent
            messages: Messages to pass to the fork agent
            context: Additional context

        Returns:
            The fork agent ID
        """
        self._fork_counter += 1
        fork_id = f"tmux_fork_{self._fork_counter}_{str(uuid4())[:8]}"

        worker = TmuxWorker(
            agent_id=fork_id,
            session_name=None,
            socket_name="ccmas-fork",
        )

        self._active_tmux_forks[fork_id] = worker

        logger.info(f"Spawned tmux fork: {fork_id}")

        return fork_id

    async def execute_fork_tmux(
        self,
        fork_id: str,
        task: str,
        messages: List[Message],
        context: Optional[Dict[str, Any]] = None,
        timeout: float = 60.0,
    ) -> ForkTmuxResult:
        """
        Execute a tmux-based fork subagent.

        Args:
            fork_id: The fork agent ID
            task: The task for the fork agent
            messages: Messages for the fork agent
            context: Additional context
            timeout: Maximum execution time

        Returns:
            ForkTmuxResult with the execution results
        """
        import time
        start_time = time.time()

        worker = self._active_tmux_forks.get(fork_id)
        if not worker:
            return ForkTmuxResult(
                success=False,
                output="",
                error=f"Fork {fork_id} not found",
                agent_id=fork_id,
                execution_time_ms=0,
            )

        mailbox = TmuxMailbox(fork_id, worker)

        try:
            fork_messages = build_forked_messages(messages, task, context)
            task_content = "\n".join(
                msg.content if isinstance(msg.content, str) else str(msg.content)
                for msg in fork_messages
                if hasattr(msg, 'content')
            )

            await worker.start()

            await mailbox.put({
                "type": "task",
                "content": task_content,
                "context": context or {},
            })

            response = await mailbox.request(
                {"type": "execute"},
                timeout=timeout,
            )

            execution_time_ms = (time.time() - start_time) * 1000

            output = ""
            tool_results: List[Dict[str, Any]] = []

            if response:
                output = response.get("content", "")
                output = self._extract_content(output)

                if "<task-notification>" in output:
                    notifications = self._extract_task_notifications(output)
                    tool_results = [{"type": "notification", "content": n} for n in notifications]
                    output = self._remove_task_notifications(output)

            fork_result = ForkTmuxResult(
                success=True,
                output=output,
                tool_results=tool_results,
                agent_id=fork_id,
                execution_time_ms=execution_time_ms,
                metadata={
                    "fork_id": fork_id,
                    "message_count": len(messages),
                    "subagent_type": "tmux",
                },
                worker=worker,
                mailbox=mailbox,
            )

            self._fork_tmux_results[fork_id] = fork_result
            return fork_result

        except asyncio.TimeoutError:
            execution_time_ms = (time.time() - start_time) * 1000
            fork_result = ForkTmuxResult(
                success=False,
                output="",
                error="Execution timeout",
                agent_id=fork_id,
                execution_time_ms=execution_time_ms,
                metadata={
                    "fork_id": fork_id,
                    "error_type": "TimeoutError",
                },
                worker=worker,
                mailbox=mailbox,
            )
            self._fork_tmux_results[fork_id] = fork_result
            return fork_result

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            fork_result = ForkTmuxResult(
                success=False,
                output="",
                error=str(e),
                agent_id=fork_id,
                execution_time_ms=execution_time_ms,
                metadata={
                    "fork_id": fork_id,
                    "error_type": type(e).__name__,
                },
                worker=worker,
                mailbox=mailbox,
            )
            self._fork_tmux_results[fork_id] = fork_result
            return fork_result

        finally:
            self._active_tmux_forks.pop(fork_id, None)

    def _extract_content(self, content: str) -> str:
        """Extract clean content from response."""
        if not content:
            return ""
        try:
            import json
            data = json.loads(content)
            return data.get("content", data.get("output", content))
        except (json.JSONDecodeError, TypeError):
            return content

    def _extract_task_notifications(self, content: str) -> List[str]:
        """Extract task notifications from content."""
        matches = TASK_NOTIFICATION_PATTERN.findall(content)
        return matches

    def _remove_task_notifications(self, content: str) -> str:
        """Remove task notification tags from content."""
        return TASK_NOTIFICATION_PATTERN.sub("", content)

    async def execute_fork(
        self,
        fork_id: str,
        executor: "AgentExecutor",
        messages: List[Message],
    ) -> ForkResult:
        """
        Execute a fork subagent.

        Args:
            fork_id: The fork agent ID
            executor: The agent executor
            messages: Messages for the fork agent

        Returns:
            ForkResult with the execution results
        """
        import time
        start_time = time.time()

        try:
            result = await executor.execute(messages)

            execution_time_ms = (time.time() - start_time) * 1000

            fork_result = ForkResult(
                success=True,
                output=result.content if isinstance(result, AssistantMessage) else str(result),
                agent_id=fork_id,
                execution_time_ms=execution_time_ms,
                metadata={
                    "fork_id": fork_id,
                    "message_count": len(messages),
                },
            )

            self._fork_results[fork_id] = fork_result
            return fork_result

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000

            fork_result = ForkResult(
                success=False,
                output="",
                error=str(e),
                agent_id=fork_id,
                execution_time_ms=execution_time_ms,
                metadata={
                    "fork_id": fork_id,
                    "error_type": type(e).__name__,
                },
            )

            self._fork_results[fork_id] = fork_result
            return fork_result

        finally:
            self._active_forks.pop(fork_id, None)

    def get_fork_result(self, fork_id: str) -> Optional[ForkResult]:
        """
        Get the result of a fork execution.

        Args:
            fork_id: The fork agent ID

        Returns:
            ForkResult if available, None otherwise
        """
        return self._fork_results.get(fork_id)

    def is_fork_active(self, fork_id: str) -> bool:
        """
        Check if a fork is currently active.

        Args:
            fork_id: The fork agent ID

        Returns:
            True if the fork is active
        """
        return fork_id in self._active_forks

    def cancel_fork(self, fork_id: str) -> bool:
        """
        Cancel an active fork.

        Args:
            fork_id: The fork agent ID

        Returns:
            True if the fork was cancelled
        """
        if fork_id in self._active_forks:
            del self._active_forks[fork_id]
            return True
        return False

    def get_active_forks(self) -> List[str]:
        """
        Get IDs of all active forks.

        Returns:
            List of active fork IDs
        """
        return list(self._active_forks.keys())

    def clear_results(self) -> None:
        """Clear all stored fork results."""
        self._fork_results.clear()


async def run_fork_subagent(
    task: str,
    messages: List[Message],
    executor: "AgentExecutor",
    context: Optional[Dict[str, Any]] = None,
    manager: Optional[ForkSubagentManager] = None,
    subagent_type: Optional[str] = None,
) -> ForkResult:
    """
    Run a fork subagent for a specific task.

    This is a convenience function that creates a manager if needed
    and executes the fork agent.

    Args:
        task: The task for the fork agent
        messages: Messages to pass to the fork agent
        executor: The agent executor to use
        context: Additional context
        manager: Optional existing manager
        subagent_type: Optional subagent type ('tmux' for tmux-based fork)

    Returns:
        ForkResult with the execution results
    """
    fork_manager = manager or ForkSubagentManager()

    if subagent_type == "tmux":
        fork_id = fork_manager.spawn_fork(task, messages, executor, context, subagent_type="tmux")
        tmux_result = await fork_manager.execute_fork_tmux(fork_id, task, messages, context)

        return ForkResult(
            success=tmux_result.success,
            output=tmux_result.output,
            tool_results=tmux_result.tool_results,
            error=tmux_result.error,
            agent_id=tmux_result.agent_id,
            execution_time_ms=tmux_result.execution_time_ms,
            metadata=tmux_result.metadata,
        )

    fork_id = fork_manager.spawn_fork(task, messages, executor, context, subagent_type=subagent_type)
    result = await fork_manager.execute_fork(fork_id, executor, messages)

    return result


async def run_fork_subagent_tmux(
    task: str,
    messages: List[Message],
    context: Optional[Dict[str, Any]] = None,
    manager: Optional[ForkSubagentManager] = None,
    timeout: float = 60.0,
) -> ForkTmuxResult:
    """
    Run a tmux-based fork subagent for a specific task.

    Args:
        task: The task for the fork agent
        messages: Messages to pass to the fork agent
        context: Additional context
        manager: Optional existing manager
        timeout: Maximum execution time

    Returns:
        ForkTmuxResult with the execution results
    """
    fork_manager = manager or ForkSubagentManager()

    fork_id = fork_manager.spawn_fork(task, messages, None, context, subagent_type="tmux")
    result = await fork_manager.execute_fork_tmux(fork_id, task, messages, context, timeout)

    return result
