"""Hooks module for CCMAS."""

from ccmas.hooks.integration import (
    HookExecutionContext,
    HookExecutionSummary,
    execute_post_tool_hooks,
    execute_pre_tool_hooks,
    execute_tool_with_hooks,
    execute_tools_with_hooks,
    format_hook_result_for_display,
    is_blocking_result,
    merge_hook_results,
    should_continue_execution,
)
from ccmas.hooks.manager import (
    Hook,
    HookEvent,
    HookInput,
    HookManager,
    HookResult,
    get_hook_manager,
    register_builtin_hooks,
)

__all__ = [
    'Hook',
    'HookEvent',
    'HookExecutionContext',
    'HookExecutionSummary',
    'HookInput',
    'HookManager',
    'HookResult',
    'execute_post_tool_hooks',
    'execute_pre_tool_hooks',
    'execute_tool_with_hooks',
    'execute_tools_with_hooks',
    'format_hook_result_for_display',
    'get_hook_manager',
    'is_blocking_result',
    'merge_hook_results',
    'register_builtin_hooks',
    'should_continue_execution',
]
