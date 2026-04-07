"""State management for interrupt recovery in CCMAS."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ccmas.types.message import Message


@dataclass
class QueryLoopState:
    """State of the query loop for recovery."""
    turn_count: int = 0
    state: str = "running"
    messages: List[Dict[str, Any]] = field(default_factory=list)
    global_turn_tokens: int = 0
    budget_tracker_data: Optional[Dict[str, Any]] = None
    saved_at: datetime = field(default_factory=datetime.now)


@dataclass
class StateCheckpoint:
    """Complete state checkpoint for recovery."""
    checkpoint_id: str
    workspace: str
    created_at: datetime
    updated_at: datetime
    query_loop_state: QueryLoopState
    metadata: Dict[str, Any] = field(default_factory=dict)


class StateManager:
    """Manages state persistence for interrupt recovery."""

    def __init__(self, state_dir: Optional[Path] = None):
        """Initialize StateManager.

        Args:
            state_dir: Directory to store state files. Defaults to ~/.ccmas/state/
        """
        if state_dir is None:
            import os
            home_dir = Path.home()
            state_dir = home_dir / ".ccmas" / "state"
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _get_checkpoint_path(self, checkpoint_id: str) -> Path:
        """Get the file path for a checkpoint."""
        return self.state_dir / f"{checkpoint_id}.json"

    def save_checkpoint(
        self,
        checkpoint: StateCheckpoint,
    ) -> str:
        """Save a state checkpoint to disk.

        Args:
            checkpoint: The state checkpoint to save.

        Returns:
            The checkpoint_id of the saved checkpoint.
        """
        checkpoint.updated_at = datetime.now()
        checkpoint_path = self._get_checkpoint_path(checkpoint.checkpoint_id)

        data = {
            "checkpoint_id": checkpoint.checkpoint_id,
            "workspace": checkpoint.workspace,
            "created_at": checkpoint.created_at.isoformat(),
            "updated_at": checkpoint.updated_at.isoformat(),
            "query_loop_state": {
                "turn_count": checkpoint.query_loop_state.turn_count,
                "state": checkpoint.query_loop_state.state,
                "messages": checkpoint.query_loop_state.messages,
                "global_turn_tokens": checkpoint.query_loop_state.global_turn_tokens,
                "budget_tracker_data": checkpoint.query_loop_state.budget_tracker_data,
                "saved_at": checkpoint.query_loop_state.saved_at.isoformat(),
            },
            "metadata": checkpoint.metadata,
        }

        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return checkpoint.checkpoint_id

    def load_checkpoint(self, checkpoint_id: str) -> StateCheckpoint:
        """Load a state checkpoint by ID.

        Args:
            checkpoint_id: The checkpoint ID to load.

        Returns:
            The loaded StateCheckpoint object.

        Raises:
            FileNotFoundError: If checkpoint file does not exist.
        """
        checkpoint_path = self._get_checkpoint_path(checkpoint_id)

        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_id}")

        with open(checkpoint_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        query_loop_state = QueryLoopState(
            turn_count=data["query_loop_state"]["turn_count"],
            state=data["query_loop_state"]["state"],
            messages=data["query_loop_state"]["messages"],
            global_turn_tokens=data["query_loop_state"]["global_turn_tokens"],
            budget_tracker_data=data["query_loop_state"].get("budget_tracker_data"),
            saved_at=datetime.fromisoformat(data["query_loop_state"]["saved_at"]),
        )

        return StateCheckpoint(
            checkpoint_id=data["checkpoint_id"],
            workspace=data["workspace"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            query_loop_state=query_loop_state,
            metadata=data.get("metadata", {}),
        )

    def list_checkpoints(self, workspace: Optional[str] = None) -> List[StateCheckpoint]:
        """List available checkpoints.

        Args:
            workspace: Optional workspace filter.

        Returns:
            List of StateCheckpoint objects.
        """
        checkpoints = []

        for checkpoint_file in self.state_dir.glob("*.json"):
            try:
                checkpoint = self.load_checkpoint(checkpoint_file.stem)
                if workspace is None or checkpoint.workspace == workspace:
                    checkpoints.append(checkpoint)
            except (json.JSONDecodeError, ValueError, FileNotFoundError):
                continue

        checkpoints.sort(key=lambda c: c.updated_at, reverse=True)
        return checkpoints

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint.

        Args:
            checkpoint_id: The checkpoint ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        checkpoint_path = self._get_checkpoint_path(checkpoint_id)
        if checkpoint_path.exists():
            checkpoint_path.unlink()
            return True
        return False

    def create_checkpoint(
        self,
        workspace: str,
        messages: List[Message],
        turn_count: int,
        state: str,
        global_turn_tokens: int = 0,
        budget_tracker_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StateCheckpoint:
        """Create a new checkpoint from current state.

        Args:
            workspace: The workspace name.
            messages: Current messages in the conversation.
            turn_count: Current turn count.
            state: Current query loop state.
            global_turn_tokens: Current global turn tokens.
            budget_tracker_data: Optional budget tracker data.
            metadata: Optional additional metadata.

        Returns:
            The created StateCheckpoint.
        """
        import uuid

        checkpoint_id = str(uuid.uuid4())[:8]
        now = datetime.now()

        message_dicts = []
        for msg in messages:
            if hasattr(msg, 'model_dump'):
                message_dicts.append(msg.model_dump(mode="json"))
            elif isinstance(msg, dict):
                message_dicts.append(msg)

        query_loop_state = QueryLoopState(
            turn_count=turn_count,
            state=state,
            messages=message_dicts,
            global_turn_tokens=global_turn_tokens,
            budget_tracker_data=budget_tracker_data,
            saved_at=now,
        )

        checkpoint = StateCheckpoint(
            checkpoint_id=checkpoint_id,
            workspace=workspace,
            created_at=now,
            updated_at=now,
            query_loop_state=query_loop_state,
            metadata=metadata or {},
        )

        self.save_checkpoint(checkpoint)
        return checkpoint


_state_manager: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    """Get or create a singleton StateManager instance."""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager


def restore_messages_from_checkpoint(checkpoint: StateCheckpoint) -> List[Message]:
    """Restore Message objects from a checkpoint.

    Args:
        checkpoint: The checkpoint to restore from.

    Returns:
        List of Message objects.
    """
    from ccmas.types.message import (
        AssistantMessage,
        SystemMessage,
        ToolMessage,
        UserMessage,
    )

    messages = []
    for msg_data in checkpoint.query_loop_state.messages:
        role = msg_data.get("role")
        content = msg_data.get("content", "")

        if role == "user":
            messages.append(UserMessage(content=content or ""))
        elif role == "assistant":
            tool_calls = None
            if "tool_calls" in msg_data and msg_data["tool_calls"]:
                tool_calls = [ToolCall(**tc) for tc in msg_data["tool_calls"]]
            messages.append(AssistantMessage(
                content=content,
                tool_calls=tool_calls,
            ))
        elif role == "tool":
            messages.append(ToolMessage(
                tool_call_id=msg_data.get("tool_call_id", ""),
                content=content or "",
            ))
        elif role == "system":
            messages.append(SystemMessage(
                content=content or "",
                subtype=msg_data.get("subtype"),
            ))

    return messages


class RecoveryManager:
    """Manages recovery from中断 interruptions."""

    def __init__(self, state_manager: Optional[StateManager] = None):
        """Initialize RecoveryManager.

        Args:
            state_manager: Optional StateManager instance.
        """
        self.state_manager = state_manager or get_state_manager()

    def save_recovery_checkpoint(
        self,
        workspace: str,
        messages: List[Message],
        turn_count: int,
        state: str,
        global_turn_tokens: int = 0,
    ) -> StateCheckpoint:
        """Save a recovery checkpoint for the current state.

        Args:
            workspace: The workspace name.
            messages: Current messages.
            turn_count: Current turn count.
            state: Current state.
            global_turn_tokens: Current token count.

        Returns:
            The created checkpoint.
        """
        return self.state_manager.create_checkpoint(
            workspace=workspace,
            messages=messages,
            turn_count=turn_count,
            state=state,
            global_turn_tokens=global_turn_tokens,
        )

    def get_latest_checkpoint(self, workspace: str) -> Optional[StateCheckpoint]:
        """Get the most recent checkpoint for a workspace.

        Args:
            workspace: The workspace name.

        Returns:
            The most recent StateCheckpoint or None.
        """
        checkpoints = self.state_manager.list_checkpoints(workspace=workspace)
        return checkpoints[0] if checkpoints else None

    def restore_from_checkpoint(
        self,
        checkpoint: StateCheckpoint,
    ) -> Dict[str, Any]:
        """Restore state from a checkpoint.

        Args:
            checkpoint: The checkpoint to restore from.

        Returns:
            Dict containing restored state info.
        """
        messages = restore_messages_from_checkpoint(checkpoint)

        return {
            "messages": messages,
            "turn_count": checkpoint.query_loop_state.turn_count,
            "state": checkpoint.query_loop_state.state,
            "global_turn_tokens": checkpoint.query_loop_state.global_turn_tokens,
            "budget_tracker_data": checkpoint.query_loop_state.budget_tracker_data,
            "checkpoint_id": checkpoint.checkpoint_id,
        }

    def clear_checkpoint(self, checkpoint_id: str) -> bool:
        """Clear a checkpoint after successful recovery.

        Args:
            checkpoint_id: The checkpoint ID to clear.

        Returns:
            True if cleared successfully.
        """
        return self.state_manager.delete_checkpoint(checkpoint_id)
