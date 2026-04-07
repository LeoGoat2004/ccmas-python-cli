"""
Agent loader for loading and managing agent definitions.

This module provides functionality for loading agents from various sources,
including built-in agents, custom agents, and remote agents.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ccmas.agent.builtin import BUILTIN_AGENT_MAP, BUILTIN_AGENTS
from ccmas.agent.definition import (
    AgentConfig,
    AgentDefinition,
    AgentKind,
    BuiltInAgentDefinition,
    CustomAgentDefinition,
    ForkAgentDefinition,
)


class AgentLoader:
    """
    Agent loader for loading and managing agent definitions.

    Provides methods to load agents from various sources and manage
    the agent registry.
    """

    def __init__(self, custom_agents_dir: Optional[Path] = None):
        """
        Initialize the agent loader.

        Args:
            custom_agents_dir: Directory containing custom agent definitions
        """
        self.custom_agents_dir = custom_agents_dir
        self._loaded_agents: Dict[str, AgentDefinition] = {}
        self._load_builtin_agents()

    def _load_builtin_agents(self) -> None:
        """Load all built-in agents into the registry."""
        for agent in BUILTIN_AGENTS:
            self._loaded_agents[agent.name] = agent

    def load_agent(self, name: str) -> Optional[AgentDefinition]:
        """
        Load an agent by name.

        Args:
            name: The agent name

        Returns:
            The agent definition, or None if not found
        """
        # Check if already loaded
        if name in self._loaded_agents:
            return self._loaded_agents[name]

        # Check built-in agents
        if name in BUILTIN_AGENT_MAP:
            agent = BUILTIN_AGENT_MAP[name]
            self._loaded_agents[name] = agent
            return agent

        # Try to load custom agent
        if self.custom_agents_dir:
            agent = self._load_custom_agent(name)
            if agent:
                self._loaded_agents[name] = agent
                return agent

        return None

    def _load_custom_agent(self, name: str) -> Optional[CustomAgentDefinition]:
        """
        Load a custom agent from the custom agents directory.

        Args:
            name: The agent name

        Returns:
            The custom agent definition, or None if not found
        """
        if not self.custom_agents_dir:
            return None

        # Look for agent definition file
        agent_file = self.custom_agents_dir / f"{name}.json"
        if not agent_file.exists():
            agent_file = self.custom_agents_dir / name / "agent.json"

        if not agent_file.exists():
            return None

        try:
            with open(agent_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            return self._parse_custom_agent(data, str(agent_file))
        except Exception as e:
            print(f"Error loading custom agent {name}: {e}")
            return None

    def _parse_custom_agent(
        self,
        data: Dict[str, Any],
        file_path: str,
    ) -> CustomAgentDefinition:
        """
        Parse a custom agent definition from JSON data.

        Args:
            data: The JSON data
            file_path: Path to the agent definition file

        Returns:
            CustomAgentDefinition instance
        """
        config_data = data.get("config", {})
        config = AgentConfig(
            model=config_data.get("model"),
            temperature=config_data.get("temperature"),
            max_tokens=config_data.get("max_tokens"),
            tools=config_data.get("tools", ["*"]),
            permission_mode=config_data.get("permission_mode", "default"),
            system_prompt=config_data.get("system_prompt"),
            max_iterations=config_data.get("max_iterations"),
            timeout_seconds=config_data.get("timeout_seconds"),
            metadata=config_data.get("metadata", {}),
        )

        return CustomAgentDefinition(
            name=data["name"],
            description=data.get("description", ""),
            kind=AgentKind.CUSTOM,
            config=config,
            version=data.get("version", "1.0.0"),
            author=data.get("author"),
            tags=data.get("tags", []),
            examples=data.get("examples", []),
            file_path=file_path,
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def get_builtin_agents(self) -> List[BuiltInAgentDefinition]:
        """
        Get all built-in agents.

        Returns:
            List of built-in agent definitions
        """
        return [
            agent for agent in self._loaded_agents.values()
            if isinstance(agent, BuiltInAgentDefinition)
        ]

    def get_custom_agents(self) -> List[CustomAgentDefinition]:
        """
        Get all custom agents.

        Returns:
            List of custom agent definitions
        """
        return [
            agent for agent in self._loaded_agents.values()
            if isinstance(agent, CustomAgentDefinition)
        ]

    def get_all_agents(self) -> List[AgentDefinition]:
        """
        Get all loaded agents.

        Returns:
            List of all agent definitions
        """
        return list(self._loaded_agents.values())

    def search_agents(self, query: str) -> List[AgentDefinition]:
        """
        Search for agents matching a query.

        Args:
            query: Search query

        Returns:
            List of matching agent definitions
        """
        return [
            agent for agent in self._loaded_agents.values()
            if agent.matches_query(query)
        ]

    def register_agent(self, agent: AgentDefinition) -> None:
        """
        Register an agent in the loader.

        Args:
            agent: The agent definition to register
        """
        self._loaded_agents[agent.name] = agent

    def unregister_agent(self, name: str) -> Optional[AgentDefinition]:
        """
        Unregister an agent from the loader.

        Args:
            name: The agent name to unregister

        Returns:
            The unregistered agent, or None if not found
        """
        return self._loaded_agents.pop(name, None)

    def has_agent(self, name: str) -> bool:
        """
        Check if an agent is loaded.

        Args:
            name: The agent name

        Returns:
            True if the agent is loaded
        """
        return name in self._loaded_agents

    def clear(self) -> None:
        """Clear all loaded agents and reload built-ins."""
        self._loaded_agents.clear()
        self._load_builtin_agents()


# Global loader instance
_global_loader: Optional[AgentLoader] = None


def get_loader(custom_agents_dir: Optional[Path] = None) -> AgentLoader:
    """
    Get the global agent loader.

    Args:
        custom_agents_dir: Directory containing custom agent definitions

    Returns:
        The global AgentLoader instance
    """
    global _global_loader
    if _global_loader is None:
        _global_loader = AgentLoader(custom_agents_dir)
    return _global_loader


def load_agent(name: str) -> Optional[AgentDefinition]:
    """
    Load an agent by name using the global loader.

    Args:
        name: The agent name

    Returns:
        The agent definition, or None if not found
    """
    return get_loader().load_agent(name)


def get_builtin_agents() -> List[BuiltInAgentDefinition]:
    """
    Get all built-in agents using the global loader.

    Returns:
        List of built-in agent definitions
    """
    return get_loader().get_builtin_agents()


def get_all_agents() -> List[AgentDefinition]:
    """
    Get all loaded agents using the global loader.

    Returns:
        List of all agent definitions
    """
    return get_loader().get_all_agents()


def search_agents(query: str) -> List[AgentDefinition]:
    """
    Search for agents using the global loader.

    Args:
        query: Search query

    Returns:
        List of matching agent definitions
    """
    return get_loader().search_agents(query)


def register_agent(agent: AgentDefinition) -> None:
    """
    Register an agent using the global loader.

    Args:
        agent: The agent definition to register
    """
    get_loader().register_agent(agent)
