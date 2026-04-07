"""Session management for CCMAS history."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .types import Session
from .loader import get_sessions_dir


class SessionManager:
    """Manages session persistence and retrieval."""

    def __init__(self, history_dir: Optional[Path] = None):
        """Initialize SessionManager.

        Args:
            history_dir: Directory to store session files. Defaults to ~/.ccmas/memory/sessions/
        """
        if history_dir is None:
            history_dir = get_sessions_dir()
        self.history_dir = history_dir
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def _get_workspace_hash(self, workspace: str) -> str:
        """Generate a hash for workspace name."""
        return hashlib.md5(workspace.encode()).hexdigest()[:8]

    def _get_session_filename(self, session: Session) -> str:
        """Generate filename for a session."""
        timestamp = session.created_at.strftime("%Y%m%d_%H%M%S")
        workspace_hash = self._get_workspace_hash(session.workspace)
        return f"{timestamp}_{workspace_hash}.json"

    def _get_session_path(self, session_id: str) -> Path:
        """Get the file path for a session."""
        return self.history_dir / f"{session_id}.json"

    def save_session(self, session: Session) -> str:
        """Save a session to disk.

        Args:
            session: The session to save.

        Returns:
            The session_id of the saved session.
        """
        session.updated_at = datetime.now()
        session_path = self._get_session_path(session.id)

        with open(session_path, "w", encoding="utf-8") as f:
            json.dump(session.model_dump(mode="json"), f, ensure_ascii=False, indent=2)

        return session.id

    def load_session(self, session_id: str) -> Session:
        """Load a session by ID.

        Args:
            session_id: The session ID to load.

        Returns:
            The loaded Session object.

        Raises:
            FileNotFoundError: If session file does not exist.
        """
        session_path = self._get_session_path(session_id)

        if not session_path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")

        with open(session_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return Session.model_validate(data)

    def list_sessions(self, workspace: Optional[str] = None) -> List[Session]:
        """List available sessions.

        Args:
            workspace: Optional workspace filter.

        Returns:
            List of Session objects.
        """
        sessions = []

        for session_file in self.history_dir.glob("*.json"):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                session = Session.model_validate(data)

                if workspace is None or session.workspace == workspace:
                    sessions.append(session)
            except (json.JSONDecodeError, ValueError):
                # Skip invalid session files
                continue

        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions

    def get_latest_session(self, workspace: str) -> Optional[Session]:
        """Get the most recent session for a workspace.

        Args:
            workspace: The workspace name.

        Returns:
            The most recent Session or None if no sessions exist.
        """
        sessions = self.list_sessions(workspace=workspace)
        return sessions[0] if sessions else None


_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get or create a singleton SessionManager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
