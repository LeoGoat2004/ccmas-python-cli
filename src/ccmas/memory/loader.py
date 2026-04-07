"""Memory loader for CCMAS."""

import os
from pathlib import Path
from typing import Optional

from .types import MemoryFile, MemoryFilesResult


CCMAS_FILE_NAME = "CCMAS.md"


def load_ccmas_md(workspace: str) -> Optional[str]:
    """Load CCMAS.md file from workspace.

    Args:
        workspace: Path to the workspace directory.

    Returns:
        The content of CCMAS.md or None if not found.
    """
    ccmas_path = Path(workspace) / CCMAS_FILE_NAME

    if ccmas_path.exists() and ccmas_path.is_file():
        try:
            return ccmas_path.read_text(encoding="utf-8")
        except (OSError, IOError):
            return None

    return None


def load_user_memory() -> Optional[str]:
    """Load user memory from ~/.ccmas/memory.md.

    Returns:
        The content of user memory or None if not found.
    """
    memory_path = Path.home() / ".ccmas" / "memory.md"

    if memory_path.exists() and memory_path.is_file():
        try:
            return memory_path.read_text(encoding="utf-8")
        except (OSError, IOError):
            return None

    return None


def get_memory_files(workspace: str) -> MemoryFilesResult:
    """Get all available memory files.

    Args:
        workspace: Path to the workspace directory.

    Returns:
        MemoryFilesResult containing all available memory files.
    """
    result = MemoryFilesResult()

    # Load project memory (CCMAS.md)
    project_memory_path = Path(workspace) / CCMAS_FILE_NAME
    if project_memory_path.exists() and project_memory_path.is_file():
        try:
            content = project_memory_path.read_text(encoding="utf-8")
            result.files.append(MemoryFile(
                path=str(project_memory_path),
                type="project",
                content=content
            ))
            result.project_memory = content
        except (OSError, IOError):
            pass

    # Load user memory (~/.ccmas/memory.md)
    user_memory_path = Path.home() / ".ccmas" / "memory.md"
    if user_memory_path.exists() and user_memory_path.is_file():
        try:
            content = user_memory_path.read_text(encoding="utf-8")
            result.files.append(MemoryFile(
                path=str(user_memory_path),
                type="user",
                content=content
            ))
            result.user_memory = content
        except (OSError, IOError):
            pass

    return result
