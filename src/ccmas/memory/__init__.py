"""Memory module for CCMAS - handles session and memory file management."""

from .loader import (
    CCMAS_FILE_NAME,
    get_memory_files,
    load_ccmas_md,
    load_user_memory,
)
from .session import SessionManager
from .types import (
    MemoryFile,
    MemoryFilesResult,
    Message,
    Session,
    SessionSummary,
)

__all__ = [
    # Types
    "Message",
    "Session",
    "SessionSummary",
    "MemoryFile",
    "MemoryFilesResult",
    # Session management
    "SessionManager",
    # Loader
    "CCMAS_FILE_NAME",
    "load_ccmas_md",
    "load_user_memory",
    "get_memory_files",
]
