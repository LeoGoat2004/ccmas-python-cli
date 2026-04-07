"""Memory loader - CCMAS memory system implementation."""

from pathlib import Path
from typing import Optional, List
import hashlib
import shutil

from ccmas.memory.template import (
    MEMORY_FILE_NAME,
    build_memory_prompt,
    get_default_memory_template,
    get_project_memory_template,
)

CCMAS_FILE_NAME = "CCMAS.md"
DEFAULT_MEMORY_FILE = "default.md"


def get_ccmas_dir() -> Path:
    """Get the base CCMAS directory."""
    ccmas_dir = Path.home() / ".ccmas"
    ccmas_dir.mkdir(parents=True, exist_ok=True)
    return ccmas_dir


def get_user_memory_dir() -> Path:
    """Get the user memory directory."""
    return get_ccmas_dir() / "memory"


def get_project_memory_dir(workspace: str) -> Path:
    """Get the project-specific memory directory."""
    project_hash = get_project_hash(workspace)
    return get_ccmas_dir() / "project" / project_hash


def get_default_memory_path() -> Path:
    """Get the default MEMORY.md path (user-level)."""
    return get_user_memory_dir() / MEMORY_FILE_NAME


def get_project_ccmas_md(workspace: str) -> Path:
    """Get the project CLAUDE.md path."""
    return get_project_memory_dir(workspace) / MEMORY_FILE_NAME


def get_user_memory_index_path() -> Path:
    """Get the user memory index file path."""
    return get_user_memory_dir() / MEMORY_FILE_NAME


def get_project_memory_index_path(workspace: str) -> Path:
    """Get the project memory index file path."""
    return get_project_memory_dir(workspace) / MEMORY_FILE_NAME


def get_memory_dir() -> Path:
    """Get the memory directory (alias for get_user_memory_dir)."""
    return get_user_memory_dir()


def get_project_dir() -> Path:
    """Get the project directory."""
    return get_ccmas_dir() / "project"


def get_projects_dir() -> Path:
    """Get the projects directory for state tracking."""
    return get_ccmas_dir() / "projects"


def get_sessions_dir() -> Path:
    """Get the sessions directory."""
    return get_ccmas_dir() / "sessions"


def get_skill_dir() -> Path:
    """Get the skill directory."""
    return get_ccmas_dir() / "skills"


def get_project_hash(workspace: str) -> str:
    """Get a unique hash for the project based on git remote or workspace path."""
    workspace_path = Path(workspace).resolve()

    git_remote = workspace_path / ".git" / "config"
    if git_remote.exists():
        content = git_remote.read_text(encoding="utf-8")
        for line in content.splitlines():
            if "url" in line.lower():
                url = line.split("=", 1)[-1].strip()
                if url:
                    return hashlib.sha256(url.encode()).hexdigest()[:16]

    return hashlib.sha256(str(workspace_path).encode()).hexdigest()[:16]


def ensure_ccmas_dirs() -> None:
    """Ensure all CCMAS directories exist."""
    get_ccmas_dir()
    get_user_memory_dir()
    get_ccmas_dir() / "sessions"


def ensure_memory_dir(workspace: str) -> None:
    """Ensure project memory directory exists."""
    get_project_memory_dir(workspace).mkdir(parents=True, exist_ok=True)


def load_memory_index(memory_dir: Path) -> List[tuple[str, str]]:
    """Load memory index entries from a MEMORY.md file.

    Returns:
        List of (link_text, file_path) tuples representing memory entries.
    """
    index_path = memory_dir / MEMORY_FILE_NAME
    if not index_path.exists():
        return []

    entries = []
    content = index_path.read_text(encoding="utf-8")

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ["):
            parts = stripped[2:].split("](", 1)
            if len(parts) == 2:
                link_text = parts[0].strip()
                file_path = parts[1].rstrip(")").strip()
                entries.append((link_text, file_path))

    return entries


def load_all_memory_files(memory_dir: Path) -> dict[str, str]:
    """Load all memory files referenced in the index.

    Returns:
        Dict mapping filename to content.
    """
    files = {}
    entries = load_memory_index(memory_dir)

    for link_text, file_path in entries:
        full_path = memory_dir / file_path
        if full_path.exists():
            try:
                files[file_path] = full_path.read_text(encoding="utf-8")
            except Exception:
                files[file_path] = ""

    return files


def build_user_memory_prompt() -> str:
    """Build the user memory prompt."""
    memory_dir = str(get_user_memory_dir())
    return build_memory_prompt("Memory", memory_dir)


def build_project_memory_prompt(workspace: str) -> str:
    """Build the project memory prompt."""
    memory_dir = str(get_project_memory_dir(workspace))
    return build_memory_prompt("Project Memory", memory_dir)


def load_user_memory() -> Optional[str]:
    """Load user memory content (all memory files concatenated)."""
    memory_dir = get_user_memory_dir()
    if not memory_dir.exists():
        return None

    files = load_all_memory_files(memory_dir)
    if not files:
        return None

    content_parts = []
    for filename, file_content in sorted(files.items()):
        content_parts.append(f"## {filename}\n\n{file_content}")

    return "\n\n".join(content_parts)


def load_project_memory(workspace: str) -> Optional[str]:
    """Load project memory content (all memory files concatenated)."""
    memory_dir = get_project_memory_dir(workspace)
    if not memory_dir.exists():
        return None

    files = load_all_memory_files(memory_dir)
    if not files:
        return None

    content_parts = []
    for filename, file_content in sorted(files.items()):
        content_parts.append(f"## {filename}\n\n{file_content}")

    return "\n\n".join(content_parts)


def load_ccmas_md(workspace: str) -> Optional[str]:
    """Load project CLAUDE.md content (legacy compatibility)."""
    claude_md = Path(workspace) / "CLAUDE.md"
    if claude_md.exists():
        try:
            return claude_md.read_text(encoding="utf-8")
        except Exception:
            return None
    return None


def initialize_memory(workspace: Optional[str] = None) -> None:
    """Initialize memory directories with empty index files."""
    ensure_ccmas_dirs()

    user_index = get_user_memory_index_path()
    if not user_index.exists():
        user_index.parent.mkdir(parents=True, exist_ok=True)
        user_index.write_text(get_default_memory_template(), encoding="utf-8")

    if workspace:
        ensure_memory_dir(workspace)
        project_index = get_project_memory_index_path(workspace)
        if not project_index.exists():
            project_index.write_text(get_project_memory_template(), encoding="utf-8")


def get_memory_files(workspace: str) -> dict:
    """Get memory files result for the workspace.

    Returns a dict with files, project_memory, and user_memory keys.
    """
    from ccmas.memory.types import MemoryFilesResult, MemoryFile

    user_memory = load_user_memory()
    project_memory = load_project_memory(workspace)

    user_dir = get_user_memory_dir()
    files = []

    if user_dir.exists():
        for entry in load_memory_index(user_dir):
            link_text, file_path = entry
            full_path = user_dir / file_path
            if full_path.exists():
                try:
                    content = full_path.read_text(encoding="utf-8")
                    files.append({
                        "name": link_text,
                        "path": str(full_path),
                        "content": content,
                    })
                except Exception:
                    pass

    return {
        "files": files,
        "project_memory": project_memory,
        "user_memory": user_memory,
    }


def save_user_memory(content: str) -> bool:
    """Save user memory content.

    Args:
        content: Memory content to save

    Returns:
        True if saved successfully
    """
    try:
        user_index = get_user_memory_index_path()
        user_index.parent.mkdir(parents=True, exist_ok=True)
        user_index.write_text(content, encoding="utf-8")
        return True
    except Exception:
        return False
