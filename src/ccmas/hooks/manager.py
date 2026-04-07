"""Hooks system for CCMAS."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import json
import subprocess


HOOK_EVENTS = [
    'PreToolUse',
    'PostToolUse',
    'PostToolUseFailure',
    'PreAgent',
    'PostAgent',
    'Notification',
    'UserPromptSubmit',
    'Start',
    'Exit',
    'SessionStart',
    'AgentStart',
    'AgentEnd',
    'OnboardingResolve',
    'McpStart',
    'Error',
]


class HookEvent(str, Enum):
    PRE_TOOL_USE = 'PreToolUse'
    POST_TOOL_USE = 'PostToolUse'
    POST_TOOL_USE_FAILURE = 'PostToolUseFailure'
    PRE_AGENT = 'PreAgent'
    POST_AGENT = 'PostAgent'
    NOTIFICATION = 'Notification'
    USER_PROMPT_SUBMIT = 'UserPromptSubmit'
    START = 'Start'
    EXIT = 'Exit'
    SESSION_START = 'SessionStart'
    AGENT_START = 'AgentStart'
    AGENT_END = 'AgentEnd'
    ONBOARDING_RESOLVE = 'OnboardingResolve'
    MCP_START = 'McpStart'
    ERROR = 'Error'


@dataclass
class HookResult:
    outcome: str = 'success'
    message: Optional[str] = None
    system_message: Optional[str] = None
    continue_: bool = True
    suppress_output: bool = False
    stop_reason: Optional[str] = None
    updated_input: Optional[Dict[str, Any]] = None
    additional_context: Optional[str] = None
    permission_behavior: Optional[str] = None


@dataclass
class Hook:
    name: str
    event: HookEvent
    command: str
    timeout: float = 30.0
    description: Optional[str] = None


@dataclass
class HookInput:
    event: HookEvent
    payload: Dict[str, Any]


def is_valid_hook_event(event: str) -> bool:
    return event in HOOK_EVENTS


def parse_hook_result(stdout: str) -> Optional[HookResult]:
    try:
        data = json.loads(stdout)
        return HookResult(
            outcome=data.get('outcome', 'success'),
            message=data.get('message'),
            system_message=data.get('systemMessage'),
            continue_=data.get('continue', True),
            suppress_output=data.get('suppressOutput', False),
            stop_reason=data.get('stopReason'),
            updated_input=data.get('updatedInput'),
            additional_context=data.get('additionalContext'),
            permission_behavior=data.get('permissionBehavior'),
        )
    except json.JSONDecodeError:
        return None


async def execute_hook(hook: Hook, hook_input: HookInput) -> HookResult:
    try:
        result = subprocess.run(
            [hook.command],
            input=json.dumps({
                'event': hook_input.event.value,
                'payload': hook_input.payload,
            }),
            capture_output=True,
            text=True,
            timeout=hook.timeout,
        )

        if result.returncode == 0 and result.stdout:
            parsed = parse_hook_result(result.stdout)
            if parsed:
                return parsed

        return HookResult(outcome='success')

    except subprocess.TimeoutExpired:
        return HookResult(outcome='non_blocking_error', message='Hook timed out')
    except Exception as e:
        return HookResult(outcome='non_blocking_error', message=str(e))


class HookManager:
    def __init__(self):
        self._hooks: Dict[HookEvent, List[Hook]] = {}

    def register_hook(self, hook: Hook) -> None:
        if hook.event not in self._hooks:
            self._hooks[hook.event] = []
        self._hooks[hook.event].append(hook)

    def unregister_hook(self, name: str) -> bool:
        for event_hooks in self._hooks.values():
            for i, h in enumerate(event_hooks):
                if h.name == name:
                    event_hooks.pop(i)
                    return True
        return False

    def get_hooks(self, event: HookEvent) -> List[Hook]:
        return self._hooks.get(event, [])

    async def execute_pre_tool_use(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
    ) -> Optional[HookResult]:
        hooks = self.get_hooks(HookEvent.PRE_TOOL_USE)
        if not hooks:
            return None

        input_data = HookInput(
            event=HookEvent.PRE_TOOL_USE,
            payload={
                'tool': tool_name,
                'input': tool_input,
            },
        )

        for hook in hooks:
            result = await execute_hook(hook, input_data)
            if result.outcome == 'blocking':
                return result

        return None

    async def execute_post_tool_use(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Any,
    ) -> Optional[HookResult]:
        hooks = self.get_hooks(HookEvent.POST_TOOL_USE)
        if not hooks:
            return None

        input_data = HookInput(
            event=HookEvent.POST_TOOL_USE,
            payload={
                'tool': tool_name,
                'input': tool_input,
                'output': tool_output,
            },
        )

        for hook in hooks:
            result = await execute_hook(hook, input_data)
            if result.outcome == 'blocking':
                return result

        return None

    async def execute_notification(
        self,
        message: str,
    ) -> Optional[HookResult]:
        hooks = self.get_hooks(HookEvent.NOTIFICATION)
        if not hooks:
            return None

        input_data = HookInput(
            event=HookEvent.NOTIFICATION,
            payload={'message': message},
        )

        for hook in hooks:
            result = await execute_hook(hook, input_data)
            if result.outcome == 'blocking':
                return result

        return None


_global_hook_manager: Optional[HookManager] = None


def get_hook_manager() -> HookManager:
    global _global_hook_manager
    if _global_hook_manager is None:
        _global_hook_manager = HookManager()
    return _global_hook_manager


def register_builtin_hooks() -> None:
    manager = get_hook_manager()
