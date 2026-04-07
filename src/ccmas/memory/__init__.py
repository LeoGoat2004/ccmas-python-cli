"""Memory module for CCMAS - handles session and memory file management."""

from .loader import (
    CCMAS_FILE_NAME,
    DEFAULT_MEMORY_FILE,
    ensure_ccmas_dirs,
    get_ccmas_dir,
    get_default_memory_path,
    get_memory_dir,
    get_memory_files,
    get_project_ccmas_md,
    get_project_dir,
    get_project_hash,
    get_sessions_dir,
    get_skill_dir,
    load_ccmas_md,
    load_user_memory,
    save_user_memory,
)
from .session import SessionManager, get_session_manager
from .state_manager import (
    QueryLoopState,
    RecoveryManager,
    StateCheckpoint,
    StateManager,
    get_state_manager,
    restore_messages_from_checkpoint,
)
from .template import (
    get_default_memory_template,
    get_project_memory_template,
)
from .types import (
    MemoryFile,
    MemoryFilesResult,
    Message,
    Session,
    SessionSummary,
)

__all__ = [
    # Constants
    "CCMAS_FILE_NAME",
    "DEFAULT_MEMORY_FILE",
    # Types
    "Message",
    "Session",
    "SessionSummary",
    "MemoryFile",
    "MemoryFilesResult",
    # Loader functions
    "load_ccmas_md",
    "load_user_memory",
    "save_user_memory",
    "get_memory_files",
    "get_project_hash",
    "get_project_ccmas_md",
    "get_default_memory_path",
    # Directory functions
    "get_ccmas_dir",
    "get_memory_dir",
    "get_sessions_dir",
    "get_project_dir",
    "get_skill_dir",
    "ensure_ccmas_dirs",
    # Session management
    "SessionManager",
    "get_session_manager",
    # State management for recovery
    "StateManager",
    "StateCheckpoint",
    "QueryLoopState",
    "RecoveryManager",
    "get_state_manager",
    "restore_messages_from_checkpoint",
    # Templates
    "get_default_memory_template",
    "get_project_memory_template",
]
