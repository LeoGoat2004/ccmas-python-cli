"""
Teammate context management for in-process swarm teammates.

This module provides context management for in-process teammates that are
part of a swarm with team coordination. Teammates can run concurrently
without global state conflicts.

Relationship with other teammate identity mechanisms:
- Env vars (CLAUDE_CODE_AGENT_ID): Process-based teammates spawned via tmux
- dynamicTeamContext: Process-based teammates joining at runtime
- TeammateContext (this file): In-process teammates via contextvars

The helper functions check contextvars first, then dynamic context, then env vars.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional, TypeVar

from .agent_context import (
    TeammateAgentContext,
    agent_context_var,
    get_agent_context,
    is_teammate_context,
)

T = TypeVar('T')


@dataclass
class TeammateContextOptions:
    """Options for creating a teammate context."""
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
    is_team_lead: bool = False
    # UI color assigned to this teammate
    agent_color: Optional[str] = None
    # The request_id in the invoking agent
    invoking_request_id: Optional[str] = None
    # Whether this is spawn or resume
    invocation_kind: Optional[Literal['spawn', 'resume']] = None


def create_teammate_context(options: TeammateContextOptions) -> TeammateAgentContext:
    """
    Create a teammate context from spawn configuration.

    Args:
        options: Configuration for the teammate context

    Returns:
        A complete TeammateAgentContext
    """
    return TeammateAgentContext(
        agent_id=options.agent_id,
        agent_name=options.agent_name,
        team_name=options.team_name,
        plan_mode_required=options.plan_mode_required,
        parent_session_id=options.parent_session_id,
        is_team_lead=options.is_team_lead,
        agent_type='teammate',
        agent_color=options.agent_color,
        invoking_request_id=options.invoking_request_id,
        invocation_kind=options.invocation_kind,
        invocation_emitted=False,
    )


class TeammateContextManager:
    """
    Context manager for running code within a teammate context.

    Usage:
        with TeammateContextManager(context):
            # Code running within teammate context
            ctx = get_agent_context()
            assert ctx is not None
            assert is_teammate_context(ctx)
    """

    def __init__(self, context: TeammateAgentContext):
        self._context = context
        self._token = None

    def __enter__(self) -> TeammateAgentContext:
        self._token = agent_context_var.set(self._context)
        return self._context

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._token is not None:
            agent_context_var.reset(self._token)

    async def __aenter__(self) -> TeammateAgentContext:
        self._token = agent_context_var.set(self._context)
        return self._context

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._token is not None:
            agent_context_var.reset(self._token)


def run_in_teammate_context(
    context: TeammateAgentContext,
    fn: Callable[[], T],
) -> T:
    """
    Run a function within a teammate context.

    Args:
        context: The teammate context to use
        fn: The function to run

    Returns:
        The return value of fn
    """
    with TeammateContextManager(context):
        return fn()


# Convenience functions for teammate context access

def get_teammate_agent_id() -> Optional[str]:
    """
    Get the agent ID if running as a teammate in a swarm.
    Returns None if not running within a teammate context.
    """
    context = get_agent_context()
    if is_teammate_context(context):
        return context.agent_id
    return None


def get_teammate_agent_name() -> Optional[str]:
    """
    Get the agent name if running as a teammate in a swarm.
    Returns None if not running within a teammate context.
    """
    context = get_agent_context()
    if is_teammate_context(context):
        return context.agent_name
    return None


def get_teammate_team_name() -> Optional[str]:
    """
    Get the team name if running as a teammate in a swarm.
    Returns None if not running within a teammate context.
    """
    context = get_agent_context()
    if is_teammate_context(context):
        return context.team_name
    return None


def is_team_lead() -> bool:
    """
    Check if the current agent is a team lead.
    Returns False if not running within a teammate context.
    """
    context = get_agent_context()
    if is_teammate_context(context):
        return context.is_team_lead
    return False


def is_in_process_teammate() -> bool:
    """
    Check if current execution is within an in-process teammate.
    This is faster than get_agent_context() is not None for simple checks.
    """
    context = get_agent_context()
    return is_teammate_context(context)
