"""
Agent context for analytics attribution using contextvars.

This module provides a way to track agent identity across async operations
without parameter drilling. Supports two agent types:

1. Subagents (Agent tool): Run in-process for quick, delegated tasks.
   Context: SubagentContext with agentType: 'subagent'

2. In-process teammates: Part of a swarm with team coordination.
   Context: TeammateAgentContext with agentType: 'teammate'

For swarm teammates in separate processes (tmux/iTerm2), use environment
variables instead: CLAUDE_CODE_AGENT_ID, CLAUDE_CODE_PARENT_SESSION_ID

WHY contextvars (not global state):
When agents are backgrounded (ctrl+b), multiple agents can run concurrently
in the same process. Global state would be overwritten, causing Agent A's
events to incorrectly use Agent B's context.
contextvars isolates each async execution chain, so concurrent agents
don't interfere with each other.

Python's contextvars module provides similar functionality to Node.js's
AsyncLocalStorage, enabling context propagation across async boundaries.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional, TypeVar, Union

T = TypeVar('T')


@dataclass
class SubagentContext:
    """
    Context for subagents (Agent tool agents).
    Subagents run in-process for quick, delegated tasks.
    """
    # The subagent's UUID (from create_agent_id())
    agent_id: str
    # Agent type - 'subagent' for Agent tool agents
    agent_type: Literal['subagent'] = 'subagent'
    # The team lead's session ID, None for main REPL subagents
    parent_session_id: Optional[str] = None
    # The subagent's type name (e.g., "Explore", "Bash", "code-reviewer")
    subagent_name: Optional[str] = None
    # Whether this is a built-in agent (vs user-defined custom agent)
    is_built_in: Optional[bool] = None
    # The request_id in the invoking agent that spawned or resumed this agent
    invoking_request_id: Optional[str] = None
    # Whether this invocation is the initial spawn or a subsequent resume
    invocation_kind: Optional[Literal['spawn', 'resume']] = None
    # Mutable flag: has this invocation's edge been emitted to telemetry yet?
    invocation_emitted: bool = False


@dataclass
class TeammateAgentContext:
    """
    Context for in-process teammates.
    Teammates are part of a swarm and have team coordination.
    """
    # Full agent ID, e.g., "researcher@my-team"
    agent_id: str
    # Display name, e.g., "researcher"
    agent_name: str
    # Team name this teammate belongs to
    team_name: str
    # Whether teammate must enter plan mode before implementing
    plan_mode_required: bool
    # The team lead's session ID for transcript correlation
    parent_session_id: str
    # Whether this agent is the team lead
    is_team_lead: bool
    # Agent type - 'teammate' for swarm teammates
    agent_type: Literal['teammate'] = 'teammate'
    # UI color assigned to this teammate
    agent_color: Optional[str] = None
    # The request_id in the invoking agent that spawned or resumed this teammate
    invoking_request_id: Optional[str] = None
    # See SubagentContext.invocation_kind
    invocation_kind: Optional[Literal['spawn', 'resume']] = None
    # Mutable flag: see SubagentContext.invocation_emitted
    invocation_emitted: bool = False


# Discriminated union for agent context
AgentContext = Union[SubagentContext, TeammateAgentContext]

# Context variable for storing agent context
# Similar to AsyncLocalStorage in Node.js
agent_context_var: ContextVar[Optional[AgentContext]] = ContextVar('agent_context', default=None)


def get_agent_context() -> Optional[AgentContext]:
    """
    Get the current agent context, if any.
    Returns None if not running within an agent context (subagent or teammate).
    Use type guards is_subagent_context() or is_teammate_context() to narrow the type.
    """
    return agent_context_var.get()


def run_with_agent_context(context: AgentContext, fn: Callable[[], T]) -> T:
    """
    Run a function with the given agent context.
    All async operations within the function will have access to this context.

    Note: In Python, contextvars automatically propagates to async tasks.
    For synchronous code, the context is maintained within the call stack.

    Args:
        context: The agent context to set
        fn: The function to run with the context

    Returns:
        The return value of fn
    """
    token = agent_context_var.set(context)
    try:
        return fn()
    finally:
        agent_context_var.reset(token)


def is_subagent_context(context: Optional[AgentContext]) -> bool:
    """
    Type guard to check if context is a SubagentContext.
    """
    return context is not None and context.agent_type == 'subagent'


def is_teammate_context(context: Optional[AgentContext]) -> bool:
    """
    Type guard to check if context is a TeammateAgentContext.
    """
    return context is not None and context.agent_type == 'teammate'


def get_subagent_log_name() -> Optional[str]:
    """
    Get the subagent name suitable for analytics logging.
    Returns the agent type name for built-in agents, "user-defined" for custom agents,
    or None if not running within a subagent context.

    Safe for analytics metadata: built-in agent names are code constants,
    and custom agents are always mapped to the literal "user-defined".
    """
    context = get_agent_context()
    if not is_subagent_context(context) or not context.subagent_name:
        return None
    return context.subagent_name if context.is_built_in else 'user-defined'


def consume_invoking_request_id() -> Optional[dict[str, Any]]:
    """
    Get the invoking request_id for the current agent context - once per invocation.
    Returns the id on the first call after a spawn/resume, then None until the next
    boundary. Also None on the main thread or when the spawn path had no request_id.

    Sparse edge semantics: invokingRequestId appears on exactly one
    API success/error per invocation, so a non-NULL value downstream
    marks a spawn/resume boundary.

    Returns:
        dict with 'invoking_request_id' and 'invocation_kind' if available,
        None otherwise
    """
    context = get_agent_context()
    if context is None or context.invoking_request_id is None or context.invocation_emitted:
        return None

    context.invocation_emitted = True
    return {
        'invoking_request_id': context.invoking_request_id,
        'invocation_kind': context.invocation_kind,
    }
