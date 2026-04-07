"""
Agent Tool - Entry point and decision routing for Agent invocations.

This module implements the Agent tool that serves as the main entry point
for invoking agents, with decision routing for Fork/Named/Teammate/Remote agents.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
from uuid import uuid4

from ccmas.agent.definition import AgentDefinition, AgentKind
from ccmas.agent.fork_subagent import ForkResult, ForkSubagentManager, run_fork_subagent
from ccmas.agent.loader import load_agent
from ccmas.agent.run_agent import (
    AgentExecutionConfig,
    AgentExecutionResult,
    AgentExecutor,
    run_agent,
)
from ccmas.context.agent_context import SubagentContext, get_agent_context
from ccmas.llm.client import LLMClient
from ccmas.permission.checker import PermissionChecker
from ccmas.tool.base import Tool, ToolCallArgs, ToolExecutionResult
from ccmas.types.message import Message, UserMessage
from ccmas.types.tool import ToolDefinition

if TYPE_CHECKING:
    from ccmas.agent.builtin import ForkAgentDefinition


class AgentInvocationType(str, Enum):
    """
    Type of agent invocation.

    Defines how an agent should be invoked.
    """

    FORK = "fork"
    NAMED = "named"
    TEAMMATE = "teammate"
    REMOTE = "remote"


@dataclass
class AgentToolConfig:
    """
    Configuration for the Agent tool.

    Defines how the Agent tool should behave.
    """

    default_timeout_seconds: int = 300
    max_concurrent_agents: int = 5
    enable_fork: bool = True
    enable_named: bool = True
    enable_teammate: bool = True
    enable_remote: bool = False
    default_permission_mode: str = "default"


@dataclass
class AgentInvocationResult:
    """
    Result of an agent invocation.

    Contains the output and metadata from the agent execution.
    """

    success: bool
    output: str
    invocation_type: AgentInvocationType
    agent_name: str
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    tool_calls: int = 0
    iterations: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentRouter:
    """
    Router for agent invocations.

    Determines the appropriate invocation type and routes
    agent requests to the correct execution path.
    """

    def __init__(
        self,
        config: Optional[AgentToolConfig] = None,
        llm_client: Optional[LLMClient] = None,
        permission_checker: Optional[PermissionChecker] = None,
    ):
        """
        Initialize the agent router.

        Args:
            config: Agent tool configuration
            llm_client: LLM client for agent execution
            permission_checker: Permission checker instance
        """
        self.config = config or AgentToolConfig()
        self.llm_client = llm_client
        self.permission_checker = permission_checker
        self._fork_manager: Optional[ForkSubagentManager] = None

    def determine_invocation_type(
        self,
        agent_name: str,
        arguments: Dict[str, Any],
    ) -> AgentInvocationType:
        """
        Determine the type of agent invocation.

        Args:
            agent_name: The agent name
            arguments: The invocation arguments

        Returns:
            AgentInvocationType
        """
        # Check for explicit type in arguments
        explicit_type = arguments.get("type")
        if explicit_type:
            try:
                return AgentInvocationType(explicit_type.lower())
            except ValueError:
                pass

        # Check agent name patterns
        if agent_name == "fork" or agent_name.startswith("fork_"):
            return AgentInvocationType.FORK

        # Load agent definition
        agent_def = load_agent(agent_name)
        if agent_def:
            if agent_def.kind == AgentKind.FORK:
                return AgentInvocationType.FORK
            elif agent_def.kind == AgentKind.TEAMMATE:
                return AgentInvocationType.TEAMMATE
            elif agent_def.kind == AgentKind.REMOTE:
                return AgentInvocationType.REMOTE

        # Default to named agent
        return AgentInvocationType.NAMED

    def get_fork_manager(self) -> ForkSubagentManager:
        """
        Get or create the fork subagent manager.

        Returns:
            ForkSubagentManager instance
        """
        if self._fork_manager is None:
            parent_context = get_agent_context()
            self._fork_manager = ForkSubagentManager(
                parent_context=parent_context,
                max_concurrent_forks=self.config.max_concurrent_agents,
            )
        return self._fork_manager

    async def route_invocation(
        self,
        agent_name: str,
        task: str,
        messages: List[Message],
        arguments: Optional[Dict[str, Any]] = None,
    ) -> AgentInvocationResult:
        """
        Route an agent invocation to the appropriate handler.

        Args:
            agent_name: The agent name
            task: The task for the agent
            messages: The conversation messages
            arguments: Additional arguments

        Returns:
            AgentInvocationResult
        """
        arguments = arguments or {}
        invocation_type = self.determine_invocation_type(agent_name, arguments)

        if invocation_type == AgentInvocationType.FORK:
            return await self._handle_fork_invocation(
                agent_name, task, messages, arguments
            )
        elif invocation_type == AgentInvocationType.NAMED:
            return await self._handle_named_invocation(
                agent_name, task, messages, arguments
            )
        elif invocation_type == AgentInvocationType.TEAMMATE:
            return await self._handle_teammate_invocation(
                agent_name, task, messages, arguments
            )
        elif invocation_type == AgentInvocationType.REMOTE:
            return await self._handle_remote_invocation(
                agent_name, task, messages, arguments
            )
        else:
            return AgentInvocationResult(
                success=False,
                output="",
                invocation_type=invocation_type,
                agent_name=agent_name,
                error=f"Unknown invocation type: {invocation_type}",
            )

    async def _handle_fork_invocation(
        self,
        agent_name: str,
        task: str,
        messages: List[Message],
        arguments: Dict[str, Any],
    ) -> AgentInvocationResult:
        """Handle a fork agent invocation."""
        import time
        start_time = time.time()

        if not self.config.enable_fork:
            return AgentInvocationResult(
                success=False,
                output="",
                invocation_type=AgentInvocationType.FORK,
                agent_name=agent_name,
                error="Fork agents are disabled",
            )

        try:
            # Create executor for fork
            if not self.llm_client:
                raise RuntimeError("LLM client not configured")

            # Get agent definition (use fork agent or custom)
            agent_def = load_agent(agent_name)
            if not agent_def:
                # Create a fork agent on-the-fly
                from ccmas.agent.builtin import create_fork_agent_instance
                agent_def = create_fork_agent_instance(task=task)

            executor = AgentExecutor(
                agent=agent_def,
                llm_client=self.llm_client,
                permission_checker=self.permission_checker,
            )

            # Run fork subagent
            fork_manager = self.get_fork_manager()
            result = await run_fork_subagent(
                task=task,
                messages=messages,
                executor=executor,
                context=arguments,
                manager=fork_manager,
            )

            execution_time_ms = (time.time() - start_time) * 1000

            return AgentInvocationResult(
                success=result.success,
                output=result.output,
                invocation_type=AgentInvocationType.FORK,
                agent_name=agent_name,
                error=result.error,
                execution_time_ms=execution_time_ms,
                metadata=result.metadata,
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            return AgentInvocationResult(
                success=False,
                output="",
                invocation_type=AgentInvocationType.FORK,
                agent_name=agent_name,
                error=str(e),
                execution_time_ms=execution_time_ms,
            )

    async def _handle_named_invocation(
        self,
        agent_name: str,
        task: str,
        messages: List[Message],
        arguments: Dict[str, Any],
    ) -> AgentInvocationResult:
        """Handle a named agent invocation."""
        import time
        start_time = time.time()

        if not self.config.enable_named:
            return AgentInvocationResult(
                success=False,
                output="",
                invocation_type=AgentInvocationType.NAMED,
                agent_name=agent_name,
                error="Named agents are disabled",
            )

        try:
            # Load agent definition
            agent_def = load_agent(agent_name)
            if not agent_def:
                raise ValueError(f"Agent not found: {agent_name}")

            if not self.llm_client:
                raise RuntimeError("LLM client not configured")

            # Create task message
            task_message = UserMessage(content=task)
            agent_messages = messages + [task_message]

            # Run the agent
            exec_config = AgentExecutionConfig(
                max_iterations=arguments.get("max_iterations", 50),
                timeout_seconds=arguments.get("timeout_seconds", self.config.default_timeout_seconds),
            )

            parent_context = get_agent_context()
            result = await run_agent(
                agent=agent_def,
                messages=agent_messages,
                llm_client=self.llm_client,
                config=exec_config,
                permission_checker=self.permission_checker,
                parent_context=parent_context,
            )

            execution_time_ms = (time.time() - start_time) * 1000

            return AgentInvocationResult(
                success=result.success,
                output=result.message.content if result.message else "",
                invocation_type=AgentInvocationType.NAMED,
                agent_name=agent_name,
                error=result.error,
                execution_time_ms=execution_time_ms,
                tool_calls=len(result.tool_calls),
                iterations=result.iterations,
                metadata=result.metadata,
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            return AgentInvocationResult(
                success=False,
                output="",
                invocation_type=AgentInvocationType.NAMED,
                agent_name=agent_name,
                error=str(e),
                execution_time_ms=execution_time_ms,
            )

    async def _handle_teammate_invocation(
        self,
        agent_name: str,
        task: str,
        messages: List[Message],
        arguments: Dict[str, Any],
    ) -> AgentInvocationResult:
        """Handle a teammate agent invocation."""
        if not self.config.enable_teammate:
            return AgentInvocationResult(
                success=False,
                output="",
                invocation_type=AgentInvocationType.TEAMMATE,
                agent_name=agent_name,
                error="Teammate agents are disabled",
            )

        # TODO: Implement teammate agent invocation
        return AgentInvocationResult(
            success=False,
            output="",
            invocation_type=AgentInvocationType.TEAMMATE,
            agent_name=agent_name,
            error="Teammate agents not yet implemented",
        )

    async def _handle_remote_invocation(
        self,
        agent_name: str,
        task: str,
        messages: List[Message],
        arguments: Dict[str, Any],
    ) -> AgentInvocationResult:
        """Handle a remote agent invocation."""
        if not self.config.enable_remote:
            return AgentInvocationResult(
                success=False,
                output="",
                invocation_type=AgentInvocationType.REMOTE,
                agent_name=agent_name,
                error="Remote agents are disabled",
            )

        # TODO: Implement remote agent invocation
        return AgentInvocationResult(
            success=False,
            output="",
            invocation_type=AgentInvocationType.REMOTE,
            agent_name=agent_name,
            error="Remote agents not yet implemented",
        )


class AgentTool(Tool):
    """
    Agent tool for invoking agents.

    This tool serves as the main entry point for invoking agents,
    with automatic routing to the appropriate agent type.
    """

    def __init__(
        self,
        router: Optional[AgentRouter] = None,
        config: Optional[AgentToolConfig] = None,
        llm_client: Optional[LLMClient] = None,
        permission_checker: Optional[PermissionChecker] = None,
    ):
        """
        Initialize the Agent tool.

        Args:
            router: Agent router instance
            config: Agent tool configuration
            llm_client: LLM client for agent execution
            permission_checker: Permission checker instance
        """
        self._router = router
        self._config = config
        self._llm_client = llm_client
        self._permission_checker = permission_checker

    @property
    def name(self) -> str:
        """Get the tool name."""
        return "Agent"

    @property
    def description(self) -> str:
        """Get the tool description."""
        return """Invoke an agent to perform a task.

This tool allows you to invoke different types of agents:
- Fork agents: Create child agents that inherit from the parent
- Named agents: Invoke predefined agents with specific capabilities
- Teammate agents: Collaborate with swarm teammates
- Remote agents: Invoke agents on remote systems

Usage:
- To fork: agent_name="fork", task="your task description"
- To invoke named agent: agent_name="agent-name", task="your task"
- The tool automatically determines the appropriate invocation type"""

    @property
    def parameters(self) -> Dict[str, Any]:
        """Get the tool parameters schema."""
        return {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Name of the agent to invoke (e.g., 'fork', 'general-purpose', 'code-reviewer')",
                },
                "task": {
                    "type": "string",
                    "description": "The task for the agent to perform",
                },
                "type": {
                    "type": "string",
                    "enum": ["fork", "named", "teammate", "remote"],
                    "description": "Optional: explicit invocation type (auto-detected if not specified)",
                },
                "max_iterations": {
                    "type": "integer",
                    "description": "Maximum number of tool call iterations (default: 50)",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Timeout for agent execution in seconds",
                },
                "context": {
                    "type": "object",
                    "description": "Additional context to pass to the agent",
                },
            },
            "required": ["agent_name", "task"],
        }

    def _get_router(self) -> AgentRouter:
        """Get or create the agent router."""
        if self._router is None:
            self._router = AgentRouter(
                config=self._config,
                llm_client=self._llm_client,
                permission_checker=self._permission_checker,
            )
        return self._router

    async def execute(self, args: ToolCallArgs) -> ToolExecutionResult:
        """
        Execute the Agent tool.

        Args:
            args: Tool call arguments

        Returns:
            ToolExecutionResult
        """
        import time
        start_time = time.time()

        try:
            # Parse arguments
            agent_name = args.arguments.get("agent_name", "")
            task = args.arguments.get("task", "")

            if not agent_name:
                return ToolExecutionResult(
                    tool_call_id=args.tool_call_id,
                    tool_name=self.name,
                    output=self._create_error_output(
                        args.tool_call_id,
                        "agent_name is required",
                    ),
                    execution_time_ms=0,
                )

            if not task:
                return ToolExecutionResult(
                    tool_call_id=args.tool_call_id,
                    tool_name=self.name,
                    output=self._create_error_output(
                        args.tool_call_id,
                        "task is required",
                    ),
                    execution_time_ms=0,
                )

            # Get messages from context
            # In a real implementation, these would come from the conversation
            messages: List[Message] = []

            # Route and execute
            router = self._get_router()
            result = await router.route_invocation(
                agent_name=agent_name,
                task=task,
                messages=messages,
                arguments=args.arguments,
            )

            execution_time_ms = (time.time() - start_time) * 1000

            # Build output
            if result.success:
                output_content = result.output
            else:
                output_content = f"Agent execution failed: {result.error}"

            return ToolExecutionResult(
                tool_call_id=args.tool_call_id,
                tool_name=self.name,
                output=self._create_success_output(args.tool_call_id, output_content),
                execution_time_ms=execution_time_ms,
                metadata={
                    "invocation_type": result.invocation_type.value,
                    "agent_name": result.agent_name,
                    "iterations": result.iterations,
                    "tool_calls": result.tool_calls,
                    **result.metadata,
                },
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            return ToolExecutionResult(
                tool_call_id=args.tool_call_id,
                tool_name=self.name,
                output=self._create_error_output(
                    args.tool_call_id,
                    f"Agent tool error: {str(e)}",
                ),
                execution_time_ms=execution_time_ms,
            )

    def _create_success_output(self, tool_call_id: str, content: str):
        """Create a success tool output."""
        from ccmas.types.tool import ToolOutput
        return ToolOutput(
            tool_call_id=tool_call_id,
            content=content,
            is_error=False,
            status="success",
        )

    def _create_error_output(self, tool_call_id: str, error_message: str):
        """Create an error tool output."""
        from ccmas.types.tool import ToolOutput
        return ToolOutput(
            tool_call_id=tool_call_id,
            content=error_message,
            is_error=True,
            status="error",
        )


def create_agent_tool(
    llm_client: Optional[LLMClient] = None,
    permission_checker: Optional[PermissionChecker] = None,
    config: Optional[AgentToolConfig] = None,
) -> AgentTool:
    """
    Create an Agent tool instance.

    Args:
        llm_client: LLM client for agent execution
        permission_checker: Permission checker instance
        config: Agent tool configuration

    Returns:
        AgentTool instance
    """
    return AgentTool(
        llm_client=llm_client,
        permission_checker=permission_checker,
        config=config,
    )
