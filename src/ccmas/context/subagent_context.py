"""
Subagent context management for Agent tool agents.

This module provides context management for subagents that run in-process
for quick, delegated tasks. Subagents are spawned by the Agent tool and
have a parent-child relationship with the invoking agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional, TypeVar

from .agent_context import (
    SubagentContext,
    agent_context_var,
    get_agent_context,
    is_subagent_context,
)

T = TypeVar('T')


@dataclass
class SubagentContextOptions:
    """Options for creating a subagent context."""
    # The subagent's UUID
    agent_id: str
    # The subagent's type name (e.g., "Explore", "Bash", "code-reviewer")
    subagent_name: Optional[str] = None
    # Whether this is a built-in agent
    is_built_in: Optional[bool] = None
    # The request_id in the invoking agent
    invoking_request_id: Optional[str] = None
    # Whether this is spawn or resume
    invocation_kind: Optional[Literal['spawn', 'resume']] = None


def create_subagent_context(
    parent_context: Optional[Any],
    options: SubagentContextOptions,
) -> SubagentContext:
    """
    Create a subagent context from spawn configuration.

    Args:
        parent_context: The parent agent's context (if any). Can be used
                       to inherit parent_session_id from a parent subagent
                       or teammate context.
        options: Configuration for the subagent context

    Returns:
        A complete SubagentContext
    """
    # Get parent session ID from parent context if available
    parent_session_id: Optional[str] = None
    if parent_context is not None:
        if is_subagent_context(parent_context):
            parent_session_id = parent_context.parent_session_id
        elif hasattr(parent_context, 'parent_session_id'):
            parent_session_id = parent_context.parent_session_id

    return SubagentContext(
        agent_id=options.agent_id,
        parent_session_id=parent_session_id,
        agent_type='subagent',
        subagent_name=options.subagent_name,
        is_built_in=options.is_built_in,
        invoking_request_id=options.invoking_request_id,
        invocation_kind=options.invocation_kind,
        invocation_emitted=False,
    )


class SubagentContextManager:
    """
    Context manager for running code within a subagent context.

    Usage:
        with SubagentContextManager(context):
            # Code running within subagent context
            ctx = get_agent_context()
            assert ctx is not None
    """

    def __init__(self, context: SubagentContext):
        self._context = context
        self._token = None

    def __enter__(self) -> SubagentContext:
        self._token = agent_context_var.set(self._context)
        return self._context

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._token is not None:
            agent_context_var.reset(self._token)

    async def __aenter__(self) -> SubagentContext:
        self._token = agent_context_var.set(self._context)
        return self._context

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._token is not None:
            agent_context_var.reset(self._token)


def run_in_subagent_context(
    context: SubagentContext,
    fn: Callable[[], T],
) -> T:
    """
    Run a function within a subagent context.

    Args:
        context: The subagent context to use
        fn: The function to run

    Returns:
        The return value of fn
    """
    with SubagentContextManager(context):
        return fn()
