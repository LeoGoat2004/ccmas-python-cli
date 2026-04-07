"""
Agent module for CCMAS.

This module provides the agent system for CCMAS, including:
- Agent definitions and configurations
- Built-in agents (Fork, General Purpose, etc.)
- Agent loading and management
- Fork subagent mechanism
- Agent execution environment
- Agent tool for invocation
"""

from ccmas.agent.definition import (
    AgentConfig,
    AgentDefinition,
    AgentKind,
    AnyAgentDefinition,
    BuiltInAgentDefinition,
    CustomAgentDefinition,
    ForkAgentDefinition,
    PermissionModeType,
    create_agent_config,
    create_builtin_agent,
    create_custom_agent,
)
from ccmas.agent.loader import (
    AgentLoader,
    get_all_agents,
    get_builtin_agents,
    get_loader,
    load_agent,
    register_agent,
    search_agents,
)
from ccmas.agent.run_agent import (
    AgentExecutionConfig,
    AgentExecutionResult,
    AgentExecutor,
    create_subagent_context_for_agent,
    run_agent,
    run_agent_streaming,
)
from ccmas.agent.agent_tool import (
    AgentInvocationResult,
    AgentInvocationType,
    AgentRouter,
    AgentTool,
    AgentToolConfig,
    create_agent_tool,
)
from ccmas.agent.fork_subagent import (
    ForkResult,
    ForkSubagentManager,
    PlaceholderToolResult,
    build_forked_messages,
    create_placeholder_tool_result,
    is_placeholder_result,
    run_fork_subagent,
)

# Import built-in agents
from ccmas.agent.builtin import (
    BUILTIN_AGENTS,
    BUILTIN_AGENT_MAP,
    # General Purpose
    GENERAL_PURPOSE_AGENT,
    create_general_purpose_config,
    # Fork
    FORK_AGENT,
    FORK_BOILERPLATE_TAG,
    build_child_message,
    create_fork_agent_config,
    create_fork_agent_instance,
    extract_fork_task,
    is_fork_message,
    # Specialized
    CODE_REVIEW_AGENT,
    EXPLORER_AGENT,
    TEST_RUNNER_AGENT,
)

__all__ = [
    # Definitions
    "AgentConfig",
    "AgentDefinition",
    "AgentKind",
    "AnyAgentDefinition",
    "BuiltInAgentDefinition",
    "CustomAgentDefinition",
    "ForkAgentDefinition",
    "PermissionModeType",
    "create_agent_config",
    "create_builtin_agent",
    "create_custom_agent",
    # Loader
    "AgentLoader",
    "get_loader",
    "load_agent",
    "get_builtin_agents",
    "get_all_agents",
    "search_agents",
    "register_agent",
    # Execution
    "AgentExecutionConfig",
    "AgentExecutionResult",
    "AgentExecutor",
    "create_subagent_context_for_agent",
    "run_agent",
    "run_agent_streaming",
    # Agent Tool
    "AgentInvocationResult",
    "AgentInvocationType",
    "AgentRouter",
    "AgentTool",
    "AgentToolConfig",
    "create_agent_tool",
    # Fork Subagent
    "ForkResult",
    "ForkSubagentManager",
    "PlaceholderToolResult",
    "build_forked_messages",
    "create_placeholder_tool_result",
    "is_placeholder_result",
    "run_fork_subagent",
    # Built-in Agents
    "BUILTIN_AGENTS",
    "BUILTIN_AGENT_MAP",
    "GENERAL_PURPOSE_AGENT",
    "create_general_purpose_config",
    "FORK_AGENT",
    "FORK_BOILERPLATE_TAG",
    "build_child_message",
    "create_fork_agent_config",
    "create_fork_agent_instance",
    "is_fork_message",
    "extract_fork_task",
    "CODE_REVIEW_AGENT",
    "EXPLORER_AGENT",
    "TEST_RUNNER_AGENT",
]
