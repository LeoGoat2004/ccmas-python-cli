"""Memory type definitions using Pydantic for data validation."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    """Message in a session."""
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)


class SessionSummary(BaseModel):
    """Summary of a session."""
    id: str
    workspace: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    preview: Optional[str] = None


class Session(BaseModel):
    """Represents a conversation session."""
    id: str
    workspace: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    messages: List[Message] = Field(default_factory=list)
    summary: Optional[str] = None

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the session."""
        self.messages.append(Message(role=role, content=content))
        self.updated_at = datetime.now()


class MemoryFile(BaseModel):
    """Represents a memory file."""
    path: str
    type: str = Field(pattern="^(project|user)$")  # project or user
    content: Optional[str] = None


class MemoryFilesResult(BaseModel):
    """Result of fetching memory files."""
    files: List[MemoryFile] = Field(default_factory=list)
    project_memory: Optional[str] = None
    user_memory: Optional[str] = None
