"""
Tool executor for query loop.

This module provides the ToolExecutor class for executing tools
and handling their results within the query loop.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Union

from ccmas.tool.base import Tool, ToolCallArgs, ToolExecutionResult
from ccmas.tool.registry import get_tool
from ccmas.types.message import (
    AssistantMessage,
    ToolCall,
    ToolMessage,
    ToolResultContentBlock,
)
from ccmas.types.tool import ToolOutput


class ToolExecutor:
    """
    Executor for tool calls within the query loop.

    Handles tool execution, result processing, and error handling.
    """

    def __init__(
        self,
        tools: Optional[List[Tool]] = None,
        max_concurrent: int = 10,
        timeout: float = 300.0,
    ):
        """
        Initialize the tool executor.

        Args:
            tools: List of available tools (if None, uses global registry)
            max_concurrent: Maximum number of concurrent tool executions
            timeout: Default timeout for tool execution in seconds
        """
        self.tools = tools
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self._semaphore: Optional[asyncio.Semaphore] = None

    async def execute_tool(
        self,
        tool_call: ToolCall,
        abort_signal: Optional[asyncio.Event] = None,
    ) -> ToolExecutionResult:
        """
        Execute a single tool call.

        Args:
            tool_call: The tool call to execute
            abort_signal: Optional abort signal for cancellation

        Returns:
            ToolExecutionResult containing the output

        Raises:
            ValueError: If tool is not found
            asyncio.TimeoutError: If execution times out
        """
        tool_name = tool_call.function.get("name", "")
        tool_call_id = tool_call.id

        # Get tool from registry or provided list
        tool = self._get_tool(tool_name)
        if not tool:
            return self._create_error_result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                error_message=f"Tool '{tool_name}' not found",
            )

        # Parse arguments
        try:
            arguments_str = tool_call.function.get("arguments", "{}")
            if isinstance(arguments_str, str):
                arguments = json.loads(arguments_str)
            else:
                arguments = arguments_str
        except json.JSONDecodeError as e:
            return self._create_error_result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                error_message=f"Invalid tool arguments: {e}",
            )

        # Create tool call args
        args = ToolCallArgs(
            tool_call_id=tool_call_id,
            arguments=arguments,
        )

        # Execute with timeout
        start_time = time.time()
        try:
            result = await asyncio.wait_for(
                tool.execute(args),
                timeout=self.timeout,
            )
            execution_time_ms = (time.time() - start_time) * 1000
            result.execution_time_ms = execution_time_ms
            return result
        except asyncio.TimeoutError:
            execution_time_ms = (time.time() - start_time) * 1000
            return self._create_error_result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                error_message=f"Tool execution timed out after {self.timeout}s",
                execution_time_ms=execution_time_ms,
            )
        except asyncio.CancelledError:
            execution_time_ms = (time.time() - start_time) * 1000
            return self._create_error_result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                error_message="Tool execution was cancelled",
                execution_time_ms=execution_time_ms,
            )
        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            return self._create_error_result(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                error_message=f"Tool execution failed: {e}",
                execution_time_ms=execution_time_ms,
            )

    async def execute_tools(
        self,
        tool_calls: List[ToolCall],
        abort_signal: Optional[asyncio.Event] = None,
    ) -> List[ToolExecutionResult]:
        """
        Execute multiple tool calls concurrently.

        Args:
            tool_calls: List of tool calls to execute
            abort_signal: Optional abort signal for cancellation

        Returns:
            List of ToolExecutionResult objects
        """
        if not tool_calls:
            return []

        # Initialize semaphore for concurrency control
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)

        async def execute_with_semaphore(
            tool_call: ToolCall,
        ) -> ToolExecutionResult:
            async with self._semaphore:
                # Check for abort
                if abort_signal and abort_signal.is_set():
                    return self._create_error_result(
                        tool_call_id=tool_call.id,
                        tool_name=tool_call.function.get("name", ""),
                        error_message="Execution aborted",
                    )
                return await self.execute_tool(tool_call, abort_signal)

        # Execute all tools concurrently
        tasks = [execute_with_semaphore(tc) for tc in tool_calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(
                    self._create_error_result(
                        tool_call_id=tool_calls[i].id,
                        tool_name=tool_calls[i].function.get("name", ""),
                        error_message=f"Execution failed: {result}",
                    )
                )
            else:
                final_results.append(result)

        return final_results

    def handle_tool_result(
        self,
        result: ToolExecutionResult,
    ) -> ToolMessage:
        """
        Convert a tool execution result to a ToolMessage.

        Args:
            result: The tool execution result

        Returns:
            ToolMessage containing the result
        """
        content: Union[str, List[ToolResultContentBlock]]

        if result.is_error:
            # Error result
            content = result.output.content
        else:
            # Success result
            content = result.output.content

        return ToolMessage(
            tool_call_id=result.tool_call_id,
            content=content,
            name=result.tool_name,
        )

    def handle_tool_results(
        self,
        results: List[ToolExecutionResult],
    ) -> List[ToolMessage]:
        """
        Convert multiple tool execution results to ToolMessages.

        Args:
            results: List of tool execution results

        Returns:
            List of ToolMessage objects
        """
        return [self.handle_tool_result(r) for r in results]

    def _get_tool(self, name: str) -> Optional[Tool]:
        """
        Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        # First check provided tools list
        if self.tools:
            for tool in self.tools:
                if tool.name == name:
                    return tool

        # Fall back to global registry
        return get_tool(name)

    def _create_error_result(
        self,
        tool_call_id: str,
        tool_name: str,
        error_message: str,
        execution_time_ms: float = 0.0,
    ) -> ToolExecutionResult:
        """
        Create an error tool execution result.

        Args:
            tool_call_id: The tool call ID
            tool_name: The tool name
            error_message: The error message
            execution_time_ms: Execution time in milliseconds

        Returns:
            ToolExecutionResult with error
        """
        return ToolExecutionResult(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            output=ToolOutput(
                tool_call_id=tool_call_id,
                content=error_message,
                is_error=True,
                status="error",
            ),
            execution_time_ms=execution_time_ms,
        )


class StreamingToolExecutor(ToolExecutor):
    """
    Streaming tool executor for real-time tool execution.

    Supports executing tools as they are streamed from the model,
    providing incremental results.
    """

    def __init__(
        self,
        tools: Optional[List[Tool]] = None,
        max_concurrent: int = 10,
        timeout: float = 300.0,
    ):
        """
        Initialize the streaming tool executor.

        Args:
            tools: List of available tools
            max_concurrent: Maximum concurrent executions
            timeout: Default timeout in seconds
        """
        super().__init__(tools, max_concurrent, timeout)
        self._pending_results: Dict[str, asyncio.Task] = {}
        self._completed_results: List[ToolExecutionResult] = []

    def add_tool(
        self,
        tool_call: ToolCall,
        message: Optional[AssistantMessage] = None,
    ) -> None:
        """
        Add a tool call for execution.

        The tool will be executed in the background.

        Args:
            tool_call: The tool call to add
            message: Optional assistant message containing the tool call
        """
        if tool_call.id not in self._pending_results:
            task = asyncio.create_task(self.execute_tool(tool_call))
            self._pending_results[tool_call.id] = task

    def get_completed_results(self) -> List[ToolExecutionResult]:
        """
        Get all completed tool execution results.

        Returns:
            List of completed ToolExecutionResult objects
        """
        # Check for completed tasks
        completed_ids = []
        for tool_call_id, task in self._pending_results.items():
            if task.done():
                completed_ids.append(tool_call_id)
                try:
                    result = task.result()
                    self._completed_results.append(result)
                except Exception as e:
                    # Create error result for failed tasks
                    self._completed_results.append(
                        self._create_error_result(
                            tool_call_id=tool_call_id,
                            tool_name="",
                            error_message=str(e),
                        )
                    )

        # Remove completed tasks from pending
        for tool_call_id in completed_ids:
            del self._pending_results[tool_call_id]

        # Return completed results and clear the list
        results = self._completed_results.copy()
        self._completed_results.clear()
        return results

    async def get_remaining_results(self) -> List[ToolExecutionResult]:
        """
        Get all remaining tool execution results.

        Waits for all pending executions to complete.

        Returns:
            List of all remaining ToolExecutionResult objects
        """
        if not self._pending_results:
            return self.get_completed_results()

        # Wait for all pending tasks
        results = []
        for tool_call_id, task in self._pending_results.items():
            try:
                result = await task
                results.append(result)
            except Exception as e:
                results.append(
                    self._create_error_result(
                        tool_call_id=tool_call_id,
                        tool_name="",
                        error_message=str(e),
                    )
                )

        self._pending_results.clear()
        results.extend(self._completed_results)
        self._completed_results.clear()
        return results

    def discard(self) -> None:
        """
        Discard all pending tool executions.

        Cancels all pending tasks and clears state.
        """
        for task in self._pending_results.values():
            task.cancel()

        self._pending_results.clear()
        self._completed_results.clear()


async def execute_tool(
    tool_call: ToolCall,
    tools: Optional[List[Tool]] = None,
    timeout: float = 300.0,
) -> ToolExecutionResult:
    """
    Execute a single tool call.

    Convenience function for one-off tool execution.

    Args:
        tool_call: The tool call to execute
        tools: List of available tools
        timeout: Execution timeout in seconds

    Returns:
        ToolExecutionResult containing the output
    """
    executor = ToolExecutor(tools=tools, timeout=timeout)
    return await executor.execute_tool(tool_call)


async def execute_tools(
    tool_calls: List[ToolCall],
    tools: Optional[List[Tool]] = None,
    max_concurrent: int = 10,
    timeout: float = 300.0,
) -> List[ToolExecutionResult]:
    """
    Execute multiple tool calls concurrently.

    Convenience function for batch tool execution.

    Args:
        tool_calls: List of tool calls to execute
        tools: List of available tools
        max_concurrent: Maximum concurrent executions
        timeout: Execution timeout in seconds

    Returns:
        List of ToolExecutionResult objects
    """
    executor = ToolExecutor(
        tools=tools,
        max_concurrent=max_concurrent,
        timeout=timeout,
    )
    return await executor.execute_tools(tool_calls)
