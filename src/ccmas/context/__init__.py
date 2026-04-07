"""
Context management for agents in ccmas.

This module provides context isolation for concurrent agent execution using
Python's contextvars module (similar to Node.js's AsyncLocalStorage).

Key concepts:
- SubagentContext: For Agent tool agents running in-process
- TeammateAgentContext: For swarm teammates with team coordination

The contextvars module ensures that each async execution chain has its own
isolated context, preventing interference when multiple agents run concurrently.

Usage:
    from ccmas.context import (
        get_agent_context,
        run_with_agent_context,
        is_subagent_context,
        is_teammate_context,
        create_subagent_context,
        create_teammate_context,
        SubagentContextManager,
        TeammateContextManager,
    )

    # Create and run with subagent context
    subagent_ctx = create_subagent_context(parent_ctx, options)
    with SubagentContextManager(subagent_ctx):
        # Code running within subagent context
        ctx = get_agent_context()
        assert is_subagent_context(ctx)

    # Create and run with teammate context
    teammate_ctx = create_teammate_context(options)
    with TeammateContextManager(teammate_ctx):
        # Code running within teammate context
        ctx = get_agent_context()
        assert is_teammate_context(ctx)
"""

from .agent_context import (
    AgentContext,
    SubagentContext,
    TeammateAgentContext,
    agent_context_var,
    consume_invoking_request_id,
    get_agent_context,
    get_subagent_log_name,
    is_subagent_context,
    is_teammate_context,
    run_with_agent_context,
)
from .subagent_context import (
    SubagentContextManager,
    SubagentContextOptions,
    create_subagent_context,
    run_in_subagent_context,
)
from .teammate_context import (
    TeammateContextManager,
    TeammateContextOptions,
    create_teammate_context,
    get_teammate_agent_id,
    get_teammate_agent_name,
    get_teammate_team_name,
    is_in_process_teammate,
    is_team_lead,
    run_in_teammate_context,
)

__all__ = [
    # Core types
    'AgentContext',
    'SubagentContext',
    'TeammateAgentContext',
    # Context variable
    'agent_context_var',
    # Core functions
    'get_agent_context',
    'run_with_agent_context',
    'is_subagent_context',
    'is_teammate_context',
    'get_subagent_log_name',
    'consume_invoking_request_id',
    # Subagent context
    'SubagentContextOptions',
    'create_subagent_context',
    'SubagentContextManager',
    'run_in_subagent_context',
    # Teammate context
    'TeammateContextOptions',
    'create_teammate_context',
    'TeammateContextManager',
    'run_in_teammate_context',
    'get_teammate_agent_id',
    'get_teammate_agent_name',
    'get_teammate_team_name',
    'is_team_lead',
    'is_in_process_teammate',
]
