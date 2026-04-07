"""
Project state tracking for CCMAS.

Provides state.json functionality for tracking task status.
This enables external tools (like OpenClaw) to monitor CCMAS task execution.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Literal, Optional


@dataclass
class ProjectState:
    """Represents the current state of a CCMAS project task."""

    task_id: str
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    summary: str = ""
    errors: List[str] = field(default_factory=list)
    started_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "summary": self.summary,
            "errors": self.errors,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProjectState:
        return cls(
            task_id=data.get("task_id", ""),
            status=data.get("status", "pending"),
            summary=data.get("summary", ""),
            errors=data.get("errors", []),
            started_at=data.get("started_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> ProjectState:
        data = json.loads(json_str)
        return cls.from_dict(data)


class ProjectStateManager:
    """Manages project state persistence."""

    STATE_FILENAME = "state.json"

    def __init__(self, project_dir: Optional[Path] = None):
        """Initialize the state manager.

        Args:
            project_dir: Path to project directory. Defaults to ~/.ccmas/projects/{hash}/
        """
        if project_dir is None:
            from ccmas.memory.loader import get_projects_dir
            project_dir = get_projects_dir()
        self.project_dir = Path(project_dir)
        self.state_file = self.project_dir / self.STATE_FILENAME

    def _ensure_project_dir(self) -> Path:
        """Ensure project directory exists."""
        self.project_dir.mkdir(parents=True, exist_ok=True)
        return self.project_dir

    def create_state(self, task_id: str, workspace: str) -> ProjectState:
        """Create a new project state.

        Args:
            task_id: Unique identifier for the task
            workspace: Workspace path

        Returns:
            New ProjectState instance
        """
        project_hash = self._hash_workspace(workspace)
        self.project_dir = self.project_dir.parent / project_hash
        self._ensure_project_dir()

        state = ProjectState(
            task_id=task_id,
            status="running",
            summary="",
            errors=[],
            started_at=datetime.now().isoformat() + "Z",
            updated_at=datetime.now().isoformat() + "Z",
        )
        self.save_state(state)
        return state

    def get_state(self) -> Optional[ProjectState]:
        """Load current project state.

        Returns:
            ProjectState if exists, None otherwise
        """
        if not self.state_file.exists():
            return None
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            return ProjectState.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def save_state(self, state: ProjectState) -> None:
        """Save project state to disk.

        Args:
            state: ProjectState to save
        """
        state.updated_at = datetime.now().isoformat() + "Z"
        self.state_file.write_text(state.to_json(), encoding="utf-8")

    def update_status(self, status: Literal["pending", "running", "completed", "failed"]) -> Optional[ProjectState]:
        """Update task status.

        Args:
            status: New status

        Returns:
            Updated ProjectState or None
        """
        state = self.get_state()
        if state:
            state.status = status
            self.save_state(state)
        return state

    def update_summary(self, summary: str) -> Optional[ProjectState]:
        """Update task summary.

        Args:
            summary: Summary text

        Returns:
            Updated ProjectState or None
        """
        state = self.get_state()
        if state:
            state.summary = summary
            self.save_state(state)
        return state

    def add_error(self, error: str) -> Optional[ProjectState]:
        """Track an error.

        Args:
            error: Error message
        """
        state = self.get_state()
        if state:
            state.errors.append(error)
            self.save_state(state)
        return state

    def mark_completed(self, summary: str = "") -> Optional[ProjectState]:
        """Mark task as completed.

        Args:
            summary: Optional completion summary
        """
        state = self.get_state()
        if state:
            state.status = "completed"
            if summary:
                state.summary = summary
            self.save_state(state)
        return state

    def mark_failed(self, error: Optional[str] = None) -> Optional[ProjectState]:
        """Mark task as failed.

        Args:
            error: Optional error message
        """
        state = self.get_state()
        if state:
            state.status = "failed"
            if error:
                state.errors.append(error)
            self.save_state(state)
        return state

    def mark_running(self) -> Optional[ProjectState]:
        """Mark task as running."""
        return self.update_status("running")

    @staticmethod
    def _hash_workspace(workspace: str) -> str:
        """Generate a hash for workspace path."""
        import hashlib
        return hashlib.md5(workspace.encode()).hexdigest()[:8]

    def get_state_path(self) -> Path:
        """Get the path to the state file.

        Returns:
            Path to state.json
        """
        return self.state_file


_global_manager: Optional[ProjectStateManager] = None


def get_project_state_manager(workspace: Optional[str] = None) -> ProjectStateManager:
    """Get the global project state manager instance.

    Args:
        workspace: Optional workspace path

    Returns:
        ProjectStateManager instance
    """
    global _global_manager
    if workspace:
        project_hash = ProjectStateManager._hash_workspace(workspace)
        from ccmas.memory.loader import get_projects_dir
        project_dir = get_projects_dir() / project_hash
        return ProjectStateManager(project_dir)
    if _global_manager is None:
        from ccmas.memory.loader import get_projects_dir
        _global_manager = ProjectStateManager(get_projects_dir())
    return _global_manager


def create_project_state(task_id: str, workspace: str) -> ProjectState:
    """Create a new project state.

    Args:
        task_id: Unique task identifier
        workspace: Workspace path

    Returns:
        New ProjectState
    """
    manager = get_project_state_manager(workspace)
    return manager.create_state(task_id, workspace)


def get_project_state() -> Optional[ProjectState]:
    """Get current project state.

    Returns:
        Current ProjectState or None
    """
    return get_project_state_manager().get_state()


def mark_task_running() -> None:
    """Mark current task as running."""
    get_project_state_manager().mark_running()


def mark_task_completed(summary: str = "") -> None:
    """Mark current task as completed.

    Args:
        summary: Optional completion summary
    """
    get_project_state_manager().mark_completed(summary)


def mark_task_failed(error: Optional[str] = None) -> None:
    """Mark current task as failed.

    Args:
        error: Optional error message
    """
    get_project_state_manager().mark_failed(error)


def update_summary(summary: str) -> None:
    """Update task summary.

    Args:
        summary: Summary text
    """
    get_project_state_manager().update_summary(summary)
