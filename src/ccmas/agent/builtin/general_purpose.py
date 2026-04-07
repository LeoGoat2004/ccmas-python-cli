"""
General Purpose Agent definition.

This module defines the General Purpose Agent, which is a versatile
built-in agent capable of handling a wide range of tasks.
"""

from __future__ import annotations

from typing import List

from ccmas.agent.definition import (
    AgentConfig,
    AgentKind,
    BuiltInAgentDefinition,
    PermissionModeType,
)


# General Purpose Agent system prompt
GENERAL_PURPOSE_SYSTEM_PROMPT = """You are a general-purpose AI assistant capable of handling a wide variety of tasks.
You have access to tools for file operations, code execution, and more.
Approach each task methodically and provide clear, helpful responses.

When working on tasks:
1. Understand the requirements clearly
2. Plan your approach before taking action
3. Use tools appropriately to accomplish the task
4. Verify your work and handle errors gracefully
5. Provide clear summaries of what was done

You can:
- Read, write, and edit files
- Execute bash commands
- Search and analyze code
- Create and modify code
- Run tests and verify functionality

Always be helpful, accurate, and thorough in your work."""


def create_general_purpose_config(
    tools: List[str] = None,
    permission_mode: PermissionModeType = PermissionModeType.DEFAULT,
) -> AgentConfig:
    """
    Create configuration for the general purpose agent.

    Args:
        tools: List of tool names (default: all tools)
        permission_mode: Permission mode (default: default)

    Returns:
        AgentConfig for general purpose agent
    """
    return AgentConfig(
        model=None,  # Use default model
        tools=tools or ["*"],
        permission_mode=permission_mode,
        system_prompt=GENERAL_PURPOSE_SYSTEM_PROMPT,
        max_iterations=50,
        metadata={
            "agent_type": "general_purpose",
            "version": "1.0.0",
        },
    )


# General Purpose Agent Definition
GENERAL_PURPOSE_AGENT = BuiltInAgentDefinition(
    name="general-purpose",
    description="A versatile general-purpose agent capable of handling a wide range of tasks including file operations, code execution, analysis, and more.",
    kind=AgentKind.BUILTIN,
    config=create_general_purpose_config(),
    version="1.0.0",
    author="CCMAS",
    tags=["builtin", "general", "versatile"],
    examples=[
        "Read the configuration file and explain its contents",
        "Create a new Python module with the specified functionality",
        "Search the codebase for all uses of deprecated functions",
        "Run the test suite and report any failures",
        "Analyze the code structure and suggest improvements",
    ],
    implementation="ccmas.agent.run_agent",
)


# Additional specialized agent configurations

def create_code_review_agent_config() -> AgentConfig:
    """Create configuration for a code review agent."""
    return AgentConfig(
        model=None,
        tools=["read", "search", "grep"],  # Read-only tools
        permission_mode=PermissionModeType.DEFAULT,
        system_prompt="""You are a code review specialist. Your job is to review code changes and provide:
1. Analysis of the changes
2. Potential issues or bugs
3. Suggestions for improvement
4. Best practice recommendations

Focus on code quality, maintainability, performance, and security.""",
        metadata={
            "agent_type": "code_review",
            "specialization": "review",
        },
    )


CODE_REVIEW_AGENT = BuiltInAgentDefinition(
    name="code-reviewer",
    description="Specialized agent for reviewing code changes, identifying issues, and suggesting improvements.",
    kind=AgentKind.BUILTIN,
    config=create_code_review_agent_config(),
    version="1.0.0",
    author="CCMAS",
    tags=["builtin", "review", "quality"],
    examples=[
        "Review the changes in the last commit",
        "Analyze this pull request for potential issues",
        "Check the code quality of this module",
    ],
)


def create_explorer_agent_config() -> AgentConfig:
    """Create configuration for an explorer agent."""
    return AgentConfig(
        model=None,
        tools=["read", "search", "grep", "glob", "ls"],  # Exploration tools
        permission_mode=PermissionModeType.DEFAULT,
        system_prompt="""You are a codebase explorer. Your job is to:
1. Navigate and understand code structure
2. Find relevant files and code
3. Map dependencies and relationships
4. Provide clear summaries of findings

Be thorough in your exploration and provide comprehensive reports.""",
        metadata={
            "agent_type": "explorer",
            "specialization": "navigation",
        },
    )


EXPLORER_AGENT = BuiltInAgentDefinition(
    name="explorer",
    description="Specialized agent for exploring and understanding codebase structure, finding files, and mapping dependencies.",
    kind=AgentKind.BUILTIN,
    config=create_explorer_agent_config(),
    version="1.0.0",
    author="CCMAS",
    tags=["builtin", "explore", "navigation"],
    examples=[
        "Explore the project structure",
        "Find all files related to authentication",
        "Map the dependencies of this module",
        "Locate the main entry points",
    ],
)


def create_test_runner_agent_config() -> AgentConfig:
    """Create configuration for a test runner agent."""
    return AgentConfig(
        model=None,
        tools=["bash", "read", "write"],  # Execution tools
        permission_mode=PermissionModeType.ACCEPT_EDITS,
        system_prompt="""You are a test execution specialist. Your job is to:
1. Run test suites
2. Analyze test results
3. Report failures clearly
4. Suggest fixes for failing tests

Ensure tests pass and provide detailed reports.""",
        metadata={
            "agent_type": "test_runner",
            "specialization": "testing",
        },
    )


TEST_RUNNER_AGENT = BuiltInAgentDefinition(
    name="test-runner",
    description="Specialized agent for running tests, analyzing results, and helping fix failing tests.",
    kind=AgentKind.BUILTIN,
    config=create_test_runner_agent_config(),
    version="1.0.0",
    author="CCMAS",
    tags=["builtin", "test", "execution"],
    examples=[
        "Run all tests and report results",
        "Run the unit tests for this module",
        "Execute the integration test suite",
        "Run tests and fix any failures",
    ],
)
