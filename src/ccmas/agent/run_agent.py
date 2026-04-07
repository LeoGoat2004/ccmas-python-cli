"""
Named Agent execution environment.

This module provides the execution environment for named agents,
including the AgentExecutor class and run_agent function.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
from uuid import uuid4

from ccmas.agent.definition import AgentDefinition, AgentKind
from ccmas.context.agent_context import SubagentContext, run_with_agent_context
from ccmas.context.subagent_context import SubagentContextManager
from ccmas.llm.client import LLMClient
from ccmas.permission.bubble import BubblePermissionHandler
from ccmas.permission.checker import PermissionChecker
from ccmas.permission.mode import PermissionMode, PermissionResult
from ccmas.tool.base import Tool, ToolCallArgs, ToolExecutionResult
from ccmas.tool.registry import get_registry
from ccmas.types.message import (
    AssistantMessage,
    Message,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from ccmas.types.tool import ToolDefinition

if TYPE_CHECKING:
    from ccmas.agent.fork_subagent import ForkSubagentManager


@dataclass
class AgentExecutionConfig:
    """
    Configuration for agent execution.

    Defines parameters for how an agent should be executed.
    """

    max_iterations: int = 50
    timeout_seconds: Optional[int] = None
    enable_streaming: bool = True
    enable_permissions: bool = True
    enable_telemetry: bool = True
    stop_sequences: List[str] = field(default_factory=list)


@dataclass
class AgentExecutionResult:
    """
    Result of agent execution.

    Contains the final output and metadata from the execution.
    """

    success: bool
    message: Optional[AssistantMessage] = None
    error: Optional[str] = None
    iterations: int = 0
    total_tokens: int = 0
    execution_time_ms: float = 0.0
    tool_calls: List[ToolCall] = field(default_factory=list)
    tool_results: List[ToolExecutionResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentExecutor:
    """
    Executor for running named agents.

    Manages the execution lifecycle of an agent, including message handling,
    tool execution, and permission management.
    """

    def __init__(
        self,
        agent: AgentDefinition,
        llm_client: LLMClient,
        config: Optional[AgentExecutionConfig] = None,
        permission_checker: Optional[PermissionChecker] = None,
        fork_manager: Optional["ForkSubagentManager"] = None,
    ):
        """
        Initialize the agent executor.

        Args:
            agent: The agent definition to execute
            llm_client: The LLM client to use
            config: Execution configuration
            permission_checker: Permission checker instance
            fork_manager: Fork subagent manager
        """
        self.agent = agent
        self.llm_client = llm_client
        self.config = config or AgentExecutionConfig()
        self.permission_checker = permission_checker
        self.fork_manager = fork_manager

        # Execution state
        self._messages: List[Message] = []
        self._tool_registry = get_registry()
        self._iteration_count = 0
        self._total_tokens = 0
        self._tool_calls: List[ToolCall] = []
        self._tool_results: List[ToolExecutionResult] = []

        # Permission handling
        self._bubble_handler: Optional[BubblePermissionHandler] = None
        if agent.config.permission_mode.value == "bubble":
            self._bubble_handler = BubblePermissionHandler()

    def _get_tools_for_agent(self) -> List[ToolDefinition]:
        """
        Get the tools available to this agent.

        Returns:
            List of tool definitions
        """
        if self.agent.config.has_all_tools():
            return self._tool_registry.get_all_definitions()

        tools = []
        for tool_name in self.agent.config.get_tools_list():
            tool = self._tool_registry.get(tool_name)
            if tool:
                tools.append(tool.get_definition())

        return tools

    def _prepare_llm_client(self) -> None:
        """Prepare the LLM client with agent-specific configuration."""
        # Register tools
        tools = self._get_tools_for_agent()
        for tool_def in tools:
            self.llm_client.register_tool(tool_def)

        # Update model if specified
        if not self.agent.config.should_inherit_model():
            self.llm_client.model = self.agent.config.model

    async def _check_permission(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> PermissionResult:
        """
        Check permission for a tool call.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments

        Returns:
            PermissionResult
        """
        if not self.config.enable_permissions:
            return PermissionResult.allow(mode=PermissionMode.BYPASS_PERMISSIONS)

        if not self.permission_checker:
            return PermissionResult.allow()

        # Check with permission checker
        result = await self.permission_checker.check(
            tool_name=tool_name,
            arguments=arguments,
            mode=PermissionMode(self.agent.config.permission_mode.value),
        )

        # Handle bubble mode
        if result.should_bubble and self._bubble_handler:
            return self._bubble_handler.send_bubble_request(
                self._bubble_handler.create_bubble_request(
                    tool_name=tool_name,
                    arguments=arguments,
                    reason=f"Permission request for tool: {tool_name}",
                )
            )

        return result

    async def _execute_tool(
        self,
        tool_call: ToolCall,
    ) -> ToolExecutionResult:
        """
        Execute a tool call.

        Args:
            tool_call: The tool call to execute

        Returns:
            ToolExecutionResult
        """
        import json

        tool_name = tool_call.function.get("name", "")
        arguments_str = tool_call.function.get("arguments", "{}")

        try:
            arguments = json.loads(arguments_str)
        except json.JSONDecodeError:
            arguments = {}

        # Check permission
        permission = await self._check_permission(tool_name, arguments)
        if not permission.allowed:
            return ToolExecutionResult(
                tool_call_id=tool_call.id,
                tool_name=tool_name,
                output=self._create_error_output(
                    tool_call.id,
                    f"Permission denied: {permission.reason}",
                ),
                execution_time_ms=0,
            )

        # Get tool
        tool = self._tool_registry.get(tool_name)
        if not tool:
            return ToolExecutionResult(
                tool_call_id=tool_call.id,
                tool_name=tool_name,
                output=self._create_error_output(
                    tool_call.id,
                    f"Tool not found: {tool_name}",
                ),
                execution_time_ms=0,
            )

        # Execute tool
        start_time = time.time()
        try:
            args = ToolCallArgs(
                tool_call_id=tool_call.id,
                arguments=arguments,
            )
            result = await tool.execute(args)
            return result
        except Exception as e:
            return ToolExecutionResult(
                tool_call_id=tool_call.id,
                tool_name=tool_name,
                output=self._create_error_output(
                    tool_call.id,
                    f"Tool execution error: {str(e)}",
                ),
                execution_time_ms=(time.time() - start_time) * 1000,
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

    async def execute(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
    ) -> AgentExecutionResult:
        """
        Execute the agent with the given messages.

        Args:
            messages: The conversation messages
            system_prompt: Optional system prompt override

        Returns:
            AgentExecutionResult
        """
        start_time = time.time()

        # Prepare execution
        self._prepare_llm_client()
        self._messages = messages.copy()

        # Use agent's system prompt if not overridden
        if system_prompt is None:
            system_prompt = self.agent.config.system_prompt

        try:
            # Main execution loop
            while self._iteration_count < self.config.max_iterations:
                self._iteration_count += 1

                # Get LLM response
                response = await self.llm_client.complete(
                    messages=self._messages,
                    system=system_prompt,
                )

                # Track tokens
                if response.usage:
                    self._total_tokens += response.usage.get("total_tokens", 0)

                # Add assistant message
                self._messages.append(response)

                # Check if done
                if not response.tool_calls:
                    # No more tool calls, we're done
                    execution_time_ms = (time.time() - start_time) * 1000
                    return AgentExecutionResult(
                        success=True,
                        message=response,
                        iterations=self._iteration_count,
                        total_tokens=self._total_tokens,
                        execution_time_ms=execution_time_ms,
                        tool_calls=self._tool_calls,
                        tool_results=self._tool_results,
                    )

                # Execute tool calls
                for tool_call in response.tool_calls:
                    self._tool_calls.append(tool_call)
                    result = await self._execute_tool(tool_call)
                    self._tool_results.append(result)

                    # Add tool result message
                    tool_message = ToolMessage(
                        tool_call_id=tool_call.id,
                        content=result.output.content,
                        name=tool_call.function.get("name"),
                    )
                    self._messages.append(tool_message)

            # Max iterations reached
            execution_time_ms = (time.time() - start_time) * 1000
            return AgentExecutionResult(
                success=False,
                error=f"Max iterations ({self.config.max_iterations}) reached",
                iterations=self._iteration_count,
                total_tokens=self._total_tokens,
                execution_time_ms=execution_time_ms,
                tool_calls=self._tool_calls,
                tool_results=self._tool_results,
            )

        except asyncio.TimeoutError:
            execution_time_ms = (time.time() - start_time) * 1000
            return AgentExecutionResult(
                success=False,
                error="Execution timeout",
                iterations=self._iteration_count,
                total_tokens=self._total_tokens,
                execution_time_ms=execution_time_ms,
                tool_calls=self._tool_calls,
                tool_results=self._tool_results,
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            return AgentExecutionResult(
                success=False,
                error=str(e),
                iterations=self._iteration_count,
                total_tokens=self._total_tokens,
                execution_time_ms=execution_time_ms,
                tool_calls=self._tool_calls,
                tool_results=self._tool_results,
            )

    async def execute_streaming(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
        on_tool_call: Optional[Callable[[ToolCall], None]] = None,
    ) -> AgentExecutionResult:
        """
        Execute the agent with streaming output.

        Args:
            messages: The conversation messages
            system_prompt: Optional system prompt override
            on_chunk: Callback for text chunks
            on_tool_call: Callback for tool calls

        Returns:
            AgentExecutionResult
        """
        if not self.config.enable_streaming:
            return await self.execute(messages, system_prompt)

        start_time = time.time()

        # Prepare execution
        self._prepare_llm_client()
        self._messages = messages.copy()

        if system_prompt is None:
            system_prompt = self.agent.config.system_prompt

        try:
            # Main execution loop
            while self._iteration_count < self.config.max_iterations:
                self._iteration_count += 1

                # Stream response
                content_parts = []
                tool_calls = []

                async for chunk in self.llm_client.stream_with_tools(
                    messages=self._messages,
                    system=system_prompt,
                ):
                    if isinstance(chunk, str):
                        content_parts.append(chunk)
                        if on_chunk:
                            on_chunk(chunk)
                    elif isinstance(chunk, ToolCall):
                        tool_calls.append(chunk)
                        if on_tool_call:
                            on_tool_call(chunk)

                # Create assistant message
                response = AssistantMessage(
                    content="".join(content_parts) if content_parts else None,
                    tool_calls=tool_calls if tool_calls else None,
                )
                self._messages.append(response)

                # Check if done
                if not tool_calls:
                    execution_time_ms = (time.time() - start_time) * 1000
                    return AgentExecutionResult(
                        success=True,
                        message=response,
                        iterations=self._iteration_count,
                        total_tokens=self._total_tokens,
                        execution_time_ms=execution_time_ms,
                        tool_calls=self._tool_calls,
                        tool_results=self._tool_results,
                    )

                # Execute tool calls
                for tool_call in tool_calls:
                    self._tool_calls.append(tool_call)
                    result = await self._execute_tool(tool_call)
                    self._tool_results.append(result)

                    tool_message = ToolMessage(
                        tool_call_id=tool_call.id,
                        content=result.output.content,
                        name=tool_call.function.get("name"),
                    )
                    self._messages.append(tool_message)

            # Max iterations reached
            execution_time_ms = (time.time() - start_time) * 1000
            return AgentExecutionResult(
                success=False,
                error=f"Max iterations ({self.config.max_iterations}) reached",
                iterations=self._iteration_count,
                total_tokens=self._total_tokens,
                execution_time_ms=execution_time_ms,
                tool_calls=self._tool_calls,
                tool_results=self._tool_results,
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            return AgentExecutionResult(
                success=False,
                error=str(e),
                iterations=self._iteration_count,
                total_tokens=self._total_tokens,
                execution_time_ms=execution_time_ms,
                tool_calls=self._tool_calls,
                tool_results=self._tool_results,
            )


def create_subagent_context_for_agent(
    agent: AgentDefinition,
    parent_context: Optional[SubagentContext] = None,
) -> SubagentContext:
    """
    Create a subagent context for an agent execution.

    Args:
        agent: The agent definition
        parent_context: Optional parent context

    Returns:
        SubagentContext instance
    """
    agent_id = f"{agent.name}_{str(uuid4())[:8]}"

    return SubagentContext(
        agent_id=agent_id,
        agent_type="subagent",
        parent_session_id=parent_context.parent_session_id if parent_context else None,
        subagent_name=agent.name,
        is_built_in=agent.kind == AgentKind.BUILTIN,
    )


async def run_agent(
    agent: AgentDefinition,
    messages: List[Message],
    llm_client: LLMClient,
    config: Optional[AgentExecutionConfig] = None,
    permission_checker: Optional[PermissionChecker] = None,
    parent_context: Optional[SubagentContext] = None,
) -> AgentExecutionResult:
    """
    Run a named agent.

    This is the main entry point for executing a named agent.

    Args:
        agent: The agent definition
        messages: The conversation messages
        llm_client: The LLM client to use
        config: Execution configuration
        permission_checker: Permission checker instance
        parent_context: Parent agent context

    Returns:
        AgentExecutionResult
    """
    # Create executor
    executor = AgentExecutor(
        agent=agent,
        llm_client=llm_client,
        config=config,
        permission_checker=permission_checker,
    )

    # Create subagent context
    context = create_subagent_context_for_agent(agent, parent_context)

    # Run within context
    def execute_in_context():
        return executor.execute(messages)

    with SubagentContextManager(context):
        return await execute_in_context()


async def run_agent_streaming(
    agent: AgentDefinition,
    messages: List[Message],
    llm_client: LLMClient,
    on_chunk: Callable[[str], None],
    on_tool_call: Optional[Callable[[ToolCall], None]] = None,
    config: Optional[AgentExecutionConfig] = None,
    permission_checker: Optional[PermissionChecker] = None,
    parent_context: Optional[SubagentContext] = None,
) -> AgentExecutionResult:
    """
    Run a named agent with streaming output.

    Args:
        agent: The agent definition
        messages: The conversation messages
        llm_client: The LLM client to use
        on_chunk: Callback for text chunks
        on_tool_call: Callback for tool calls
        config: Execution configuration
        permission_checker: Permission checker instance
        parent_context: Parent agent context

    Returns:
        AgentExecutionResult
    """
    # Create executor with streaming enabled
    exec_config = config or AgentExecutionConfig()
    exec_config.enable_streaming = True

    executor = AgentExecutor(
        agent=agent,
        llm_client=llm_client,
        config=exec_config,
        permission_checker=permission_checker,
    )

    # Create subagent context
    context = create_subagent_context_for_agent(agent, parent_context)

    # Run within context
    with SubagentContextManager(context):
        return await executor.execute_streaming(
            messages=messages,
            on_chunk=on_chunk,
            on_tool_call=on_tool_call,
        )
