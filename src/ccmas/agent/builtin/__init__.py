"""
Built-in agents module.

This module exports all built-in agent definitions.
"""

from ccmas.agent.builtin.fork_agent import (
    FORK_AGENT,
    FORK_BOILERPLATE_TAG,
    build_child_message,
    create_fork_agent_config,
    create_fork_agent_instance,
    extract_fork_task,
    is_fork_message,
)
from ccmas.agent.builtin.general_purpose import (
    CODE_REVIEW_AGENT,
    EXPLORER_AGENT,
    GENERAL_PURPOSE_AGENT,
    TEST_RUNNER_AGENT,
    create_code_review_agent_config,
    create_explorer_agent_config,
    create_general_purpose_config,
    create_test_runner_agent_config,
)

from ccmas.agent.builtin.plan_agent import (
    PLAN_AGENT,
    create_plan_agent_config,
    get_plan_system_prompt,
)
from ccmas.agent.builtin.verification_agent import (
    VERIFICATION_AGENT,
    create_verification_agent_config,
    get_verification_system_prompt,
)

# List of all built-in agents
BUILTIN_AGENTS = [
    GENERAL_PURPOSE_AGENT,
    FORK_AGENT,
    CODE_REVIEW_AGENT,
    EXPLORER_AGENT,
    TEST_RUNNER_AGENT,
    PLAN_AGENT,
    VERIFICATION_AGENT,
]

# Map of agent names to definitions
BUILTIN_AGENT_MAP = {
    agent.name: agent
    for agent in BUILTIN_AGENTS
}

__all__ = [
    # General Purpose Agent
    "GENERAL_PURPOSE_AGENT",
    "create_general_purpose_config",
    # Fork Agent
    "FORK_AGENT",
    "FORK_BOILERPLATE_TAG",
    "build_child_message",
    "create_fork_agent_config",
    "create_fork_agent_instance",
    "is_fork_message",
    "extract_fork_task",
    # Specialized Agents
    "CODE_REVIEW_AGENT",
    "create_code_review_agent_config",
    "EXPLORER_AGENT",
    "create_explorer_agent_config",
    "TEST_RUNNER_AGENT",
    "create_test_runner_agent_config",
    # Plan Agent
    "PLAN_AGENT",
    "create_plan_agent_config",
    "get_plan_system_prompt",
    # Verification Agent
    "VERIFICATION_AGENT",
    "create_verification_agent_config",
    "get_verification_system_prompt",
    # Collections
    "BUILTIN_AGENTS",
    "BUILTIN_AGENT_MAP",
]
