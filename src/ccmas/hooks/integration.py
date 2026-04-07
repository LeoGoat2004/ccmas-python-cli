"""
Hooks integration module for tool execution pipeline.

This module provides functions to integrate hooks into the tool execution pipeline,
supporting pre-tool and post-tool hooks with blocking/non-blocking behavior.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ccmas.hooks.manager import HookEvent, HookManager, HookResult, get_hook_manager


@dataclass
class HookExecutionContext:
    tool_name: str
    tool_input: Dict[str, Any]
    tool_output: Any = None
    pre_result: Optional[HookResult] = None
    post_result: Optional[HookResult] = None


@dataclass
class HookExecutionSummary:
    success: bool
    blocked: bool
    message: Optional[str] = None
    system_message: Optional[str] = None
    updated_input: Optional[Dict[str, Any]] = None
    pre_hook_results: List[HookResult] = field(default_factory=list)
    post_hook_results: List[HookResult] = field(default_factory=list)


async def execute_pre_tool_hooks(
    tool_name: str,
    tool_input: Dict[str, Any],
    hook_manager: Optional[HookManager] = None,
) -> HookResult:
    """
    Execute pre-tool hooks for a tool call.

    Args:
        tool_name: Name of the tool being called
        tool_input: Input arguments to the tool
        hook_manager: Optional hook manager instance (uses global if not provided)

    Returns:
        HookResult with outcome, message, and whether to continue/block
    """
    manager = hook_manager or get_hook_manager()
    result = await manager.execute_pre_tool_use(tool_name, tool_input)

    if result is None:
        return HookResult(outcome="success", continue_=True)

    return result


async def execute_post_tool_hooks(
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_output: Any,
    hook_manager: Optional[HookManager] = None,
) -> HookResult:
    """
    Execute post-tool hooks for a tool call.

    Args:
        tool_name: Name of the tool that was called
        tool_input: Input arguments that were passed to the tool
        tool_output: Output/result from the tool execution
        hook_manager: Optional hook manager instance (uses global if not provided)

    Returns:
        HookResult with outcome and any additional context
    """
    manager = hook_manager or get_hook_manager()
    result = await manager.execute_post_tool_use(tool_name, tool_input, tool_output)

    if result is None:
        return HookResult(outcome="success", continue_=True)

    return result


def is_blocking_result(result: HookResult) -> bool:
    """
    Check if a hook result indicates blocking behavior.

    Args:
        result: The hook result to check

    Returns:
        True if the result indicates blocking
    """
    return result.outcome == "blocking" or result.outcome == "deny"


def should_continue_execution(result: HookResult) -> bool:
    """
    Check if tool execution should continue based on hook result.

    Args:
        result: The hook result to check

    Returns:
        True if execution should continue
    """
    if result.outcome in ("blocking", "deny", "error"):
        return False
    return result.continue_


async def execute_tool_with_hooks(
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_executor: Callable[[Dict[str, Any]], Any],
    hook_manager: Optional[HookManager] = None,
    user_confirm_callback: Optional[Callable[[str, HookResult], bool]] = None,
) -> HookExecutionSummary:
    """
    Execute a tool with pre and post hooks.

    This function orchestrates the full hook execution flow:
    1. Execute pre-tool hooks
    2. If blocking, optionally request user confirmation
    3. Execute the tool if allowed
    4. Execute post-tool hooks

    Args:
        tool_name: Name of the tool to execute
        tool_input: Input arguments for the tool
        tool_executor: Async callable that executes the tool with tool_input
        hook_manager: Optional hook manager instance
        user_confirm_callback: Optional callback for user confirmation on blocking hooks.
                              Should return True if user approves, False otherwise.
                              If not provided and hook is blocking, defaults to deny.

    Returns:
        HookExecutionSummary with results and execution status
    """
    manager = hook_manager or get_hook_manager()
    pre_results: List[HookResult] = []
    post_results: List[HookResult] = []
    updated_input = tool_input
    blocked = False
    system_message = None
    final_output = None
    execution_allowed = True

    pre_result = await execute_pre_tool_hooks(tool_name, updated_input, manager)
    pre_results.append(pre_result)

    if is_blocking_result(pre_result):
        blocked = True
        execution_allowed = False

        if user_confirm_callback and pre_result.message:
            confirmed = await asyncio.get_event_loop().run_in_executor(
                None, lambda: user_confirm_callback(pre_result.message, pre_result)
            )
            if confirmed:
                execution_allowed = True
                blocked = False
        else:
            system_message = pre_result.system_message or pre_result.message

    if execution_allowed:
        try:
            final_output = await tool_executor(updated_input)
        except Exception as e:
            final_output = {"error": str(e), "is_error": True}

    post_result = await execute_post_tool_hooks(
        tool_name, updated_input, final_output, manager
    )
    post_results.append(post_result)

    if is_blocking_result(post_result):
        blocked = True
        if post_result.system_message:
            system_message = post_result.system_message

    return HookExecutionSummary(
        success=not blocked and final_output is not None and not (
            isinstance(final_output, dict) and final_output.get("is_error")
        ),
        blocked=blocked,
        message=post_result.message if blocked else None,
        system_message=system_message,
        updated_input=post_result.updated_input or updated_input,
        pre_hook_results=pre_results,
        post_hook_results=post_results,
    )


async def execute_tools_with_hooks(
    tool_executions: List[Dict[str, Any]],
    hook_manager: Optional[HookManager] = None,
    user_confirm_callback: Optional[Callable[[str, HookResult], bool]] = None,
) -> List[HookExecutionSummary]:
    """
    Execute multiple tools with hooks concurrently.

    Args:
        tool_executions: List of dicts with 'tool_name', 'tool_input', 'tool_executor' keys
        hook_manager: Optional hook manager instance
        user_confirm_callback: Optional callback for user confirmation

    Returns:
        List of HookExecutionSummary objects for each tool execution
    """
    tasks = [
        execute_tool_with_hooks(
            tool_name=te["tool_name"],
            tool_input=te["tool_input"],
            tool_executor=te["tool_executor"],
            hook_manager=hook_manager,
            user_confirm_callback=user_confirm_callback,
        )
        for te in tool_executions
    ]
    return await asyncio.gather(*tasks)


def format_hook_result_for_display(result: HookResult) -> str:
    """
    Format a hook result for display to the user.

    Args:
        result: The hook result to format

    Returns:
        Formatted string for display
    """
    lines = []

    if result.message:
        lines.append(f"Hook Message: {result.message}")

    if result.system_message:
        lines.append(f"System Message: {result.system_message}")

    if result.outcome:
        lines.append(f"Outcome: {result.outcome}")

    if result.updated_input:
        lines.append(f"Updated Input: {result.updated_input}")

    if result.additional_context:
        lines.append(f"Additional Context: {result.additional_context}")

    return "\n".join(lines) if lines else "No additional information"


def merge_hook_results(results: List[HookResult]) -> HookResult:
    """
    Merge multiple hook results into a single result.

    The last non-success result takes precedence.

    Args:
        results: List of hook results to merge

    Returns:
        Merged HookResult
    """
    if not results:
        return HookResult(outcome="success", continue_=True)

    final_result = results[0]
    for result in results[1:]:
        if result.outcome != "success":
            final_result = result
            if result.system_message:
                final_result.system_message = result.system_message
        if result.updated_input:
            final_result.updated_input = result.updated_input
        if result.additional_context:
            final_result.additional_context = result.additional_context

    return final_result
