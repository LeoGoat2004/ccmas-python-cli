"""
Agent definition structures.

This module defines the core structures for agent definitions, including
built-in agents, custom agents, and agent configurations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class AgentKind(str, Enum):
    """
    Agent kind enumeration.

    Defines the types of agents in the system.
    """

    BUILTIN = "builtin"
    CUSTOM = "custom"
    FORK = "fork"
    TEAMMATE = "teammate"
    REMOTE = "remote"


class PermissionModeType(str, Enum):
    """
    Permission mode type for agents.

    Defines how permissions are handled for agent operations.
    """

    DEFAULT = "default"
    ACCEPT_EDITS = "acceptEdits"
    BYPASS_PERMISSIONS = "bypassPermissions"
    BUBBLE = "bubble"
    PLAN = "plan"
    AUTO = "auto"


class AgentConfig(BaseModel):
    """
    Agent configuration.

    Defines the configuration for an agent, including model settings,
    tools, and permission modes.
    """

    model: Optional[str] = Field(
        default=None,
        description="Model identifier for the agent (None or 'inherit' for parent model)"
    )
    temperature: Optional[float] = Field(
        default=None,
        description="Sampling temperature (0-2)"
    )
    max_tokens: Optional[int] = Field(
        default=None,
        description="Maximum tokens to generate"
    )
    tools: List[str] = Field(
        default_factory=lambda: ["*"],
        description="List of tool names available to the agent ('*' for all tools)"
    )
    permission_mode: PermissionModeType = Field(
        default=PermissionModeType.DEFAULT,
        description="Permission mode for the agent"
    )
    system_prompt: Optional[str] = Field(
        default=None,
        description="Custom system prompt for the agent"
    )
    max_iterations: Optional[int] = Field(
        default=None,
        description="Maximum number of tool call iterations"
    )
    timeout_seconds: Optional[int] = Field(
        default=None,
        description="Timeout for agent execution in seconds"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata for the agent"
    )

    class Config:
        """Pydantic config."""

        use_enum_values = True

    def should_inherit_model(self) -> bool:
        """Check if the agent should inherit the parent's model."""
        return self.model is None or self.model == "inherit"

    def has_all_tools(self) -> bool:
        """Check if the agent has access to all tools."""
        return "*" in self.tools

    def get_tools_list(self) -> List[str]:
        """Get the list of tools (excluding wildcard)."""
        if self.has_all_tools():
            return []
        return [t for t in self.tools if t != "*"]


@dataclass
class AgentDefinition:
    """
    Agent definition.

    Defines an agent's identity, capabilities, and configuration.
    """

    name: str
    description: str
    kind: AgentKind
    config: AgentConfig = field(default_factory=AgentConfig)
    version: str = "1.0.0"
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    is_active: bool = True

    def get_display_name(self) -> str:
        """Get the display name for the agent."""
        return self.name

    def get_full_description(self) -> str:
        """Get the full description including metadata."""
        parts = [self.description]
        if self.tags:
            parts.append(f"Tags: {', '.join(self.tags)}")
        if self.author:
            parts.append(f"Author: {self.author}")
        return "\n".join(parts)

    def matches_query(self, query: str) -> bool:
        """
        Check if the agent matches a search query.

        Args:
            query: Search query string

        Returns:
            True if the agent matches the query
        """
        query_lower = query.lower()
        return (
            query_lower in self.name.lower() or
            query_lower in self.description.lower() or
            any(query_lower in tag.lower() for tag in self.tags)
        )


@dataclass
class BuiltInAgentDefinition(AgentDefinition):
    """
    Built-in agent definition.

    Defines a built-in agent with predefined behavior and configuration.
    Built-in agents are provided by the system and cannot be modified.
    """

    kind: AgentKind = AgentKind.BUILTIN
    is_built_in: bool = True
    implementation: Optional[str] = None  # Reference to implementation

    def __post_init__(self):
        """Ensure built-in flag is set."""
        self.is_built_in = True


@dataclass
class CustomAgentDefinition(AgentDefinition):
    """
    Custom agent definition.

    Defines a user-created custom agent with custom configuration.
    """

    kind: AgentKind = AgentKind.CUSTOM
    is_built_in: bool = False
    file_path: Optional[str] = None  # Path to agent definition file
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class ForkAgentDefinition(AgentDefinition):
    """
    Fork agent definition.

    Defines a fork agent that creates a child agent inheriting from the parent.
    Fork agents are used for spawning subagents with specific capabilities.
    """

    kind: AgentKind = AgentKind.FORK
    is_built_in: bool = True
    parent_context: Optional[Any] = None  # Reference to parent agent context

    def __post_init__(self):
        """Ensure built-in flag is set."""
        self.is_built_in = True


# Type alias for any agent definition
AnyAgentDefinition = Union[
    AgentDefinition,
    BuiltInAgentDefinition,
    CustomAgentDefinition,
    ForkAgentDefinition,
]


def create_agent_config(
    model: Optional[str] = None,
    tools: Optional[List[str]] = None,
    permission_mode: Union[str, PermissionModeType] = PermissionModeType.DEFAULT,
    system_prompt: Optional[str] = None,
    **kwargs: Any,
) -> AgentConfig:
    """
    Create an agent configuration.

    Args:
        model: Model identifier
        tools: List of tool names
        permission_mode: Permission mode
        system_prompt: Custom system prompt
        **kwargs: Additional configuration options

    Returns:
        AgentConfig instance
    """
    if isinstance(permission_mode, str):
        permission_mode = PermissionModeType(permission_mode)

    return AgentConfig(
        model=model,
        tools=tools or ["*"],
        permission_mode=permission_mode,
        system_prompt=system_prompt,
        **kwargs,
    )


def create_builtin_agent(
    name: str,
    description: str,
    config: AgentConfig,
    implementation: Optional[str] = None,
    **kwargs: Any,
) -> BuiltInAgentDefinition:
    """
    Create a built-in agent definition.

    Args:
        name: Agent name
        description: Agent description
        config: Agent configuration
        implementation: Implementation reference
        **kwargs: Additional options

    Returns:
        BuiltInAgentDefinition instance
    """
    return BuiltInAgentDefinition(
        name=name,
        description=description,
        kind=AgentKind.BUILTIN,
        config=config,
        implementation=implementation,
        **kwargs,
    )


def create_custom_agent(
    name: str,
    description: str,
    config: AgentConfig,
    file_path: Optional[str] = None,
    **kwargs: Any,
) -> CustomAgentDefinition:
    """
    Create a custom agent definition.

    Args:
        name: Agent name
        description: Agent description
        config: Agent configuration
        file_path: Path to agent definition file
        **kwargs: Additional options

    Returns:
        CustomAgentDefinition instance
    """
    return CustomAgentDefinition(
        name=name,
        description=description,
        kind=AgentKind.CUSTOM,
        config=config,
        file_path=file_path,
        **kwargs,
    )
