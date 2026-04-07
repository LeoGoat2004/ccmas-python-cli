"""
Teammate spawning system.

This module provides the spawn_teammate() function for creating new
teammates in a swarm. It supports multiple backends:
- IN_PROCESS: Lightweight in-process teammates (same process)
- SUBPROCESS: Subprocess-based teammates (separate process)
- TMUX: tmux-based teammates (terminal multiplexer)
- DOCKER: Docker container teammates (isolated environment)

The backend is automatically selected based on configuration and
environment capabilities.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from ccmas.context.agent_context import get_agent_context, is_teammate_context

from .in_process import InProcessTeammate, InProcessTeammateConfig

logger = logging.getLogger(__name__)


class TeammateBackend(str, Enum):
    """
    Backend type for teammate execution.

    Each backend offers different trade-offs between:
    - Performance (startup time, communication overhead)
    - Isolation (state separation, fault tolerance)
    - Resource usage (memory, CPU)
    """

    # In-process: Fastest, shared memory, no isolation
    IN_PROCESS = "in_process"

    # Subprocess: Moderate speed, OS-level isolation
    SUBPROCESS = "subprocess"

    # tmux: Terminal-based, good for interactive workflows
    TMUX = "tmux"

    # Docker: Full container isolation
    DOCKER = "docker"

    # Auto-select based on environment
    AUTO = "auto"


@dataclass
class TeammateConfig:
    """
    Configuration for spawning a teammate.

    This configuration is backend-agnostic and is used to create
teammates regardless of the selected backend.
    """

    # Required fields
    # Agent name (e.g., "researcher", "coder")
    agent_name: str
    # Team name this teammate belongs to
    team_name: str

    # Optional fields
    # System prompt defining the teammate's role
    system_prompt: str = ""
    # Whether teammate must enter plan mode before implementing
    plan_mode_required: bool = False
    # Backend to use (AUTO for automatic selection)
    backend: TeammateBackend = TeammateBackend.AUTO
    # Tools available to this teammate
    tools: List[str] = field(default_factory=list)
    # LLM model to use
    model: str = "default"
    # Maximum iterations per task
    max_iterations: int = 50
    # Working directory for the teammate
    working_dir: Optional[str] = None
    # Environment variables
    env_vars: Dict[str, str] = field(default_factory=dict)
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    # In-process specific options
    # Max mailbox queue size
    mailbox_size: int = 1000

    # Subprocess/tmux specific options
    # Command to run (for subprocess backend)
    command: Optional[str] = None
    # Session name (for tmux backend)
    session_name: Optional[str] = None

    # Docker specific options
    # Docker image
    image: Optional[str] = None
    # Container resources
    cpu_limit: Optional[str] = None
    memory_limit: Optional[str] = None

    def get_agent_id(self) -> str:
        """
        Generate agent ID from configuration.

        Returns:
            Agent ID in format "agent_name@team_name"
        """
        return f"{self.agent_name}@{self.team_name}"


class SpawnResult:
    """
    Result of spawning a teammate.

    Contains the created teammate instance and metadata about the spawn.
    """

    def __init__(
        self,
        teammate: Optional[InProcessTeammate] = None,
        agent_id: str = "",
        backend: TeammateBackend = TeammateBackend.AUTO,
        success: bool = False,
        error: Optional[str] = None,
    ):
        self.teammate = teammate
        self.agent_id = agent_id
        self.backend = backend
        self.success = success
        self.error = error

    def __repr__(self) -> str:
        if self.success:
            return f"SpawnResult(success=True, agent_id={self.agent_id}, backend={self.backend})"
        return f"SpawnResult(success=False, error={self.error})"


def _detect_backend(config: TeammateConfig) -> TeammateBackend:
    """
    Detect the best backend based on configuration and environment.

    Args:
        config: Teammate configuration

    Returns:
        Selected backend
    """
    if config.backend != TeammateBackend.AUTO:
        return config.backend

    # Check if running in a restricted environment
    # TODO: Add checks for containerized environments, etc.

    # Default to in-process for simplicity and performance
    return TeammateBackend.IN_PROCESS


def _get_parent_session_id() -> str:
    """
    Get the parent session ID from current context.

    Returns:
        Parent session ID or empty string
    """
    context = get_agent_context()

    if is_teammate_context(context):
        # Running within a teammate, use its parent session
        return context.parent_session_id

    # TODO: Get main session ID for non-teammate contexts
    return ""


async def spawn_teammate(config: TeammateConfig) -> SpawnResult:
    """
    Spawn a new teammate.

    This is the main entry point for creating teammates. It automatically
    selects the appropriate backend and creates the teammate.

    Args:
        config: Teammate configuration

    Returns:
        SpawnResult with the created teammate or error information

    Example:
        config = TeammateConfig(
            agent_name="researcher",
            team_name="my-team",
            system_prompt="You are a research specialist...",
            backend=TeammateBackend.IN_PROCESS,
        )

        result = await spawn_teammate(config)
        if result.success:
            print(f"Created teammate: {result.agent_id}")
            await result.teammate.start()
        else:
            print(f"Failed to spawn: {result.error}")
    """
    agent_id = config.get_agent_id()
    backend = _detect_backend(config)

    logger.info(f"Spawning teammate {agent_id} using {backend} backend")

    try:
        if backend == TeammateBackend.IN_PROCESS:
            return await _spawn_in_process(config, agent_id)
        elif backend == TeammateBackend.SUBPROCESS:
            return await _spawn_subprocess(config, agent_id)
        elif backend == TeammateBackend.TMUX:
            return await _spawn_tmux(config, agent_id)
        elif backend == TeammateBackend.DOCKER:
            return await _spawn_docker(config, agent_id)
        else:
            return SpawnResult(
                agent_id=agent_id,
                backend=backend,
                success=False,
                error=f"Unsupported backend: {backend}",
            )
    except Exception as e:
        logger.error(f"Failed to spawn teammate {agent_id}: {e}")
        return SpawnResult(
            agent_id=agent_id,
            backend=backend,
            success=False,
            error=str(e),
        )


async def _spawn_in_process(config: TeammateConfig, agent_id: str) -> SpawnResult:
    """
    Spawn an in-process teammate.

    Args:
        config: Teammate configuration
        agent_id: Generated agent ID

    Returns:
        SpawnResult
    """
    parent_session_id = _get_parent_session_id()

    in_process_config = InProcessTeammateConfig(
        agent_id=agent_id,
        agent_name=config.agent_name,
        team_name=config.team_name,
        system_prompt=config.system_prompt,
        plan_mode_required=config.plan_mode_required,
        parent_session_id=parent_session_id,
        is_team_lead=False,
        tools=config.tools,
        model=config.model,
        max_iterations=config.max_iterations,
        metadata=config.metadata,
    )

    teammate = InProcessTeammate(in_process_config)

    return SpawnResult(
        teammate=teammate,
        agent_id=agent_id,
        backend=TeammateBackend.IN_PROCESS,
        success=True,
    )


async def _spawn_subprocess(config: TeammateConfig, agent_id: str) -> SpawnResult:
    """
    Spawn a subprocess-based teammate.

    Args:
        config: Teammate configuration
        agent_id: Generated agent ID

    Returns:
        SpawnResult
    """
    # TODO: Implement subprocess backend
    return SpawnResult(
        agent_id=agent_id,
        backend=TeammateBackend.SUBPROCESS,
        success=False,
        error="Subprocess backend not yet implemented",
    )


async def _spawn_tmux(config: TeammateConfig, agent_id: str) -> SpawnResult:
    """
    Spawn a tmux-based teammate.

    Args:
        config: Teammate configuration
        agent_id: Generated agent ID

    Returns:
        SpawnResult
    """
    # TODO: Implement tmux backend
    return SpawnResult(
        agent_id=agent_id,
        backend=TeammateBackend.TMUX,
        success=False,
        error="tmux backend not yet implemented",
    )


async def _spawn_docker(config: TeammateConfig, agent_id: str) -> SpawnResult:
    """
    Spawn a Docker container teammate.

    Args:
        config: Teammate configuration
        agent_id: Generated agent ID

    Returns:
        SpawnResult
    """
    # TODO: Implement Docker backend
    return SpawnResult(
        agent_id=agent_id,
        backend=TeammateBackend.DOCKER,
        success=False,
        error="Docker backend not yet implemented",
    )


# Convenience functions for common use cases


async def spawn_in_process_teammate(
    agent_name: str,
    team_name: str,
    system_prompt: str = "",
    **kwargs: Any,
) -> SpawnResult:
    """
    Convenience function to spawn an in-process teammate.

    Args:
        agent_name: Name of the agent
        team_name: Name of the team
        system_prompt: System prompt for the agent
        **kwargs: Additional configuration options

    Returns:
        SpawnResult
    """
    config = TeammateConfig(
        agent_name=agent_name,
        team_name=team_name,
        system_prompt=system_prompt,
        backend=TeammateBackend.IN_PROCESS,
        **kwargs,
    )
    return await spawn_teammate(config)


def create_team(
    team_name: str,
    members: List[Dict[str, Any]],
) -> List[TeammateConfig]:
    """
    Create configurations for a team of teammates.

    Args:
        team_name: Name of the team
        members: List of member configurations (each dict needs at least 'agent_name')

    Returns:
        List of TeammateConfig

    Example:
        configs = create_team("my-team", [
            {"agent_name": "researcher", "system_prompt": "You research..."},
            {"agent_name": "coder", "system_prompt": "You code..."},
        ])
    """
    configs = []
    for member in members:
        config = TeammateConfig(
            team_name=team_name,
            agent_name=member["agent_name"],
            system_prompt=member.get("system_prompt", ""),
            plan_mode_required=member.get("plan_mode_required", False),
            tools=member.get("tools", []),
            model=member.get("model", "default"),
            backend=TeammateBackend.IN_PROCESS,
        )
        configs.append(config)
    return configs
