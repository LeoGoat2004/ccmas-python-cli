"""
Fork subagent mechanism for spawning and managing forked agents.

This module implements the fork subagent system that allows agents to
spawn child agents with specific tasks and capabilities.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import uuid4

from ccmas.agent.builtin import FORK_BOILERPLATE_TAG
from ccmas.agent.definition import AgentConfig, ForkAgentDefinition
from ccmas.context.agent_context import SubagentContext, agent_context_var
from ccmas.types.message import (
    AssistantMessage,
    Message,
    ToolResultContentBlock,
    UserMessage,
)

if TYPE_CHECKING:
    from ccmas.agent.run_agent import AgentExecutor


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
    execution, and result collection.
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
        self._fork_results: Dict[str, ForkResult] = {}
        self._fork_counter = 0

    def create_fork_agent(
        self,
        task: str,
        config: Optional[AgentConfig] = None,
    ) -> ForkAgentDefinition:
        """
        Create a fork agent definition for a task.

        Args:
            task: The task for the fork agent
            config: Optional custom configuration

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
    ) -> str:
        """
        Spawn a fork subagent.

        Args:
            task: The task for the fork agent
            messages: Messages to pass to the fork agent
            executor: The agent executor to use
            context: Additional context

        Returns:
            The fork agent ID
        """
        if len(self._active_forks) >= self.max_concurrent_forks:
            raise RuntimeError(
                f"Maximum concurrent forks reached ({self.max_concurrent_forks})"
            )

        fork_agent = self.create_fork_agent(task)
        fork_id = fork_agent.name

        # Build messages for the fork
        fork_messages = build_forked_messages(messages, task, context)

        # Store the executor
        self._active_forks[fork_id] = executor

        return fork_id

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
            # Execute the fork agent
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
            # Remove from active forks
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

    Returns:
        ForkResult with the execution results
    """
    # Get or create manager
    fork_manager = manager or ForkSubagentManager()

    # Spawn and execute the fork
    fork_id = fork_manager.spawn_fork(task, messages, executor, context)

    # Execute the fork
    result = await fork_manager.execute_fork(fork_id, executor, messages)

    return result
