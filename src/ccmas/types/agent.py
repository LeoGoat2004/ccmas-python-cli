"""
Agent type definitions.

This module defines types for agent contexts, supporting both subagents
(Agent tool) and teammate agents (swarm coordination).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Literal, Optional, Union

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    """
    Agent type enumeration.

    Defines the types of agents in the system.
    """

    SUBAGENT = "subagent"
    TEAMMATE = "teammate"


class SubagentContext(BaseModel):
    """
    Context for subagents (Agent tool agents).

    Subagents run in-process for quick, delegated tasks.
    """

    agent_id: str = Field(..., description="The subagent's UUID")
    agent_type: Literal["subagent"] = Field(
        default="subagent", description="Agent type identifier"
    )
    parent_session_id: Optional[str] = Field(
        default=None, description="The team lead's session ID, None for main REPL subagents"
    )
    subagent_name: Optional[str] = Field(
        default=None, description="The subagent's type name (e.g., 'Explore', 'Bash', 'code-reviewer')"
    )
    is_built_in: Optional[bool] = Field(
        default=None, description="Whether this is a built-in agent (vs user-defined custom agent)"
    )
    invoking_request_id: Optional[str] = Field(
        default=None, description="The request_id in the invoking agent that spawned or resumed this agent"
    )
    invocation_kind: Optional[Literal["spawn", "resume"]] = Field(
        default=None, description="Whether this invocation is the initial spawn or a subsequent resume"
    )
    invocation_emitted: bool = Field(
        default=False, description="Mutable flag: has this invocation's edge been emitted to telemetry yet?"
    )

    class Config:
        """Pydantic config."""

        use_enum_values = True


class TeammateAgentContext(BaseModel):
    """
    Context for in-process teammates.

    Teammates are part of a swarm and have team coordination.
    """

    agent_id: str = Field(..., description="Full agent ID, e.g., 'researcher@my-team'")
    agent_name: str = Field(..., description="Display name, e.g., 'researcher'")
    team_name: str = Field(..., description="Team name this teammate belongs to")
    plan_mode_required: bool = Field(
        ..., description="Whether teammate must enter plan mode before implementing"
    )
    parent_session_id: str = Field(
        ..., description="The team lead's session ID for transcript correlation"
    )
    is_team_lead: bool = Field(
        ..., description="Whether this agent is the team lead"
    )
    agent_type: Literal["teammate"] = Field(
        default="teammate", description="Agent type identifier"
    )
    agent_color: Optional[str] = Field(
        default=None, description="UI color assigned to this teammate"
    )
    invoking_request_id: Optional[str] = Field(
        default=None, description="The request_id in the invoking agent that spawned or resumed this teammate"
    )
    invocation_kind: Optional[Literal["spawn", "resume"]] = Field(
        default=None, description="Whether this invocation is the initial spawn or a subsequent resume"
    )
    invocation_emitted: bool = Field(
        default=False, description="Mutable flag: has this invocation's edge been emitted to telemetry yet?"
    )

    class Config:
        """Pydantic config."""

        use_enum_values = True


# Discriminated union for agent context
AgentContext = Union[SubagentContext, TeammateAgentContext]


def is_subagent_context(context: Optional[AgentContext]) -> bool:
    """
    Type guard to check if context is a SubagentContext.

    Args:
        context: The agent context to check

    Returns:
        True if context is a SubagentContext, False otherwise
    """
    return context is not None and context.agent_type == "subagent"


def is_teammate_context(context: Optional[AgentContext]) -> bool:
    """
    Type guard to check if context is a TeammateAgentContext.

    Args:
        context: The agent context to check

    Returns:
        True if context is a TeammateAgentContext, False otherwise
    """
    return context is not None and context.agent_type == "teammate"


def get_subagent_log_name(context: Optional[AgentContext]) -> Optional[str]:
    """
    Get the subagent name suitable for analytics logging.

    Returns the agent type name for built-in agents, "user-defined" for custom agents,
    or None if not running within a subagent context.

    Safe for analytics metadata: built-in agent names are code constants,
    and custom agents are always mapped to the literal "user-defined".

    Args:
        context: The agent context

    Returns:
        Log name or None
    """
    if not is_subagent_context(context) or not context.subagent_name:
        return None
    return context.subagent_name if context.is_built_in else "user-defined"


def consume_invoking_request_id(context: Optional[AgentContext]) -> Optional[Dict[str, Any]]:
    """
    Get the invoking request_id for the current agent context - once per invocation.

    Returns the id on the first call after a spawn/resume, then None until the next
    boundary. Also None on the main thread or when the spawn path had no request_id.

    Sparse edge semantics: invokingRequestId appears on exactly one
    API success/error per invocation, so a non-NULL value downstream
    marks a spawn/resume boundary.

    Args:
        context: The agent context (will be mutated if invocation_emitted is False)

    Returns:
        dict with 'invoking_request_id' and 'invocation_kind' if available,
        None otherwise
    """
    if context is None or context.invoking_request_id is None or context.invocation_emitted:
        return None

    context.invocation_emitted = True
    return {
        "invoking_request_id": context.invoking_request_id,
        "invocation_kind": context.invocation_kind,
    }
