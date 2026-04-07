"""
Skill manager for discovering, loading, and managing skills.

This module provides functionality to manage skills stored in markdown files.
Supports Claude Code's SKILL.md format with YAML frontmatter.

Skill discovery follows Claude Code's approach:
1. Discovery phase: Only scan frontmatter (YAML) for metadata to build skill listing
2. LLM decision: Uses listing to decide which skill to invoke
3. Invoke phase: Only then is full SKILL.md content loaded
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


FRONTMATTER_PATTERN = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)
DESCRIPTION_EXTRACT_PATTERN = re.compile(r'^#\s+(.+)$', re.MULTILINE)


@dataclass
class Skill:
    """Represents a skill loaded from a SKILL.md file."""

    name: str = field(metadata={"description": "The skill name"})
    description: str = field(default="", metadata={"description": "Short description of the skill"})
    when_to_use: Optional[str] = field(default=None, metadata={"description": "When to use this skill"})
    allowed_tools: List[str] = field(default_factory=list, metadata={"description": "Tools this skill allows"})
    model: Optional[str] = field(default=None, metadata={"description": "Model override for this skill"})
    effort: Optional[str] = field(default=None, metadata={"description": "Effort level: low, medium, high"})
    context: Optional[str] = field(default=None, metadata={"description": "Execution context: fork or inline"})
    agent: Optional[str] = field(default=None, metadata={"description": "Agent type to use"})
    paths: List[str] = field(default_factory=list, metadata={"description": "Path patterns for conditional activation"})
    version: Optional[str] = field(default=None, metadata={"description": "Skill version"})
    user_invocable: bool = field(default=True, metadata={"description": "Whether user can invoke via /command"})
    disable_model_invocation: bool = field(default=False, metadata={"description": "Disable model invocation"})
    arguments: List[Dict[str, str]] = field(default_factory=list, metadata={"description": "Argument definitions"})
    hooks: Optional[Dict[str, Any]] = field(default=None, metadata={"description": "Hook configurations"})
    instructions: str = field(default="", metadata={"description": "The skill instructions (loaded lazily)"})
    content: str = field(default="", metadata={"description": "Raw markdown content"})
    file_path: str = field(default="", metadata={"description": "Path to the SKILL.md file"})
    base_dir: Optional[str] = field(default=None, metadata={"description": "Skill directory path"})
    loaded_from: str = field(default="skills", metadata={"description": "Source: skills, plugin, bundled, mcp"})
    _full_loaded: bool = field(default=False, repr=False)

    @property
    def is_valid(self) -> bool:
        """Check if the skill has valid content."""
        return bool(self.name and self.instructions)

    @property
    def display_description(self) -> str:
        """Get description with when_to_use appended."""
        if self.when_to_use:
            return f"{self.description} - {self.when_to_use}"
        return self.description


def parse_yaml_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
    """
    Parse YAML frontmatter from markdown content.

    Args:
        content: Full markdown content

    Returns:
        Tuple of (frontmatter_dict, remaining_content)
    """
    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        return {}, content

    frontmatter_text = match.group(1)
    remaining = content[match.end():]

    result: Dict[str, Any] = {}
    for line in frontmatter_text.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()

            if value.startswith('[') and value.endswith(']'):
                items = [item.strip().strip('"\',') for item in value[1:-1].split(',')]
                result[key] = [i for i in items if i]
            elif value.lower() == 'true':
                result[key] = True
            elif value.lower() == 'false':
                result[key] = False
            else:
                result[key] = value.strip('"\',')
        elif line.startswith('-'):
            if 'arguments' not in result:
                result['arguments'] = []
            arg_match = re.match(r'-\s*name:\s*(\S+)', line)
            if arg_match:
                result['arguments'].append({'name': arg_match.group(1)})

    return result, remaining


def extract_description_fallback(content: str, skill_name: str) -> str:
    """
    Extract description from markdown content when frontmatter description is missing.
    Uses the first heading or first line as fallback.
    """
    lines = content.split('\n')
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#'):
            continue
        if stripped.startswith('description:'):
            match = re.match(r'description:\s*(.*)', stripped)
            if match:
                return match.group(1).strip()
        if stripped and not stripped.startswith('##'):
            return stripped[:200]
    return f"Skill: {skill_name}"


class SkillManager:
    """Manager for discovering and loading skills."""

    SKILL_FILE_NAME = "SKILL.md"

    def __init__(self, skills_dir: Optional[str] = None):
        """
        Initialize the skill manager.

        Args:
            skills_dir: Path to the skills directory. Defaults to ~/.ccmas/skills/
        """
        if skills_dir is None:
            skills_dir = os.path.expanduser("~/.ccmas/skills/")
        self.skills_dir = Path(skills_dir)
        self._skills: Dict[str, Skill] = {}
        self._discovered = False

    def discover_skills(self, workspace: Optional[str] = None) -> List[Skill]:
        """
        Discover all skills in the skills directory.

        For performance, only reads frontmatter (YAML) for metadata.
        Full content is loaded lazily on invoke.

        Args:
            workspace: Optional workspace path to discover project-level skills

        Returns:
            List of discovered Skill objects
        """
        discovered: List[Skill] = []

        search_dirs = [self.skills_dir]
        if workspace:
            project_skills = Path(workspace) / ".claude" / "skills"
            if project_skills.exists():
                search_dirs.append(project_skills)

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue

            for entry in search_dir.iterdir():
                if entry.is_dir():
                    skill_file = entry / self.SKILL_FILE_NAME
                    if skill_file.exists():
                        skill = self._discover_skill_dir(entry, skill_file)
                        if skill and skill.name:
                            discovered.append(skill)
                            self._skills[skill.name] = skill
                elif entry.is_file() and entry.suffix == '.md':
                    skill = self._discover_skill_file(entry)
                    if skill and skill.name:
                        discovered.append(skill)
                        self._skills[skill.name] = skill

        self._discovered = True
        return discovered

    def _discover_skill_dir(self, skill_dir: Path, skill_file: Path) -> Optional[Skill]:
        """
        Discover a skill from directory format: skill-name/SKILL.md
        Only reads frontmatter for discovery.
        """
        try:
            content = skill_file.read_text(encoding="utf-8")
            return self._parse_skill_content(content, str(skill_file), base_dir=str(skill_dir.parent))
        except Exception:
            return None

    def _discover_skill_file(self, file_path: Path) -> Optional[Skill]:
        """Discover a skill from a single .md file (legacy format)."""
        try:
            content = file_path.read_text(encoding="utf-8")
            skill_name = file_path.stem
            return self._parse_skill_content(content, str(file_path), skill_name=skill_name)
        except Exception:
            return None

    def load_skill(self, name: str) -> Optional[Skill]:
        """
        Load a specific skill by name.
        Performs full content load if not already loaded.

        Args:
            name: The name of the skill to load

        Returns:
            The loaded Skill object, or None if not found
        """
        if name in self._skills:
            skill = self._skills[name]
            if not skill._full_loaded:
                self._load_full_content(skill)
            return skill

        skill_file = self.skills_dir / name / self.SKILL_FILE_NAME
        if skill_file.exists():
            skill = self._discover_skill_dir(skill_file.parent, skill_file)
            if skill:
                self._skills[name] = skill
                self._load_full_content(skill)
                return skill

        for entry in self.skills_dir.iterdir():
            if entry.is_dir() and entry.name == name:
                skill_md = entry / self.SKILL_FILE_NAME
                if skill_md.exists():
                    skill = self._discover_skill_dir(entry, skill_md)
                    if skill:
                        self._skills[name] = skill
                        self._load_full_content(skill)
                        return skill

        return None

    def _load_full_content(self, skill: Skill) -> None:
        """
        Load full content for a skill (lazy loading).
        Only called when skill is actually invoked.
        """
        if skill._full_loaded:
            return

        try:
            skill_path = Path(skill.file_path)
            if not skill_path.exists():
                return

            content = skill_path.read_text(encoding="utf-8")
            _, remaining = parse_yaml_frontmatter(content)

            lines = remaining.strip().split('\n')
            in_instructions = False
            instructions_lines: List[str] = []

            for line in lines:
                stripped = line.strip()
                if stripped.startswith('#'):
                    in_instructions = False
                if in_instructions:
                    instructions_lines.append(line)
                elif re.match(r'^##\s+Instructions?\s*$', stripped, re.IGNORECASE):
                    in_instructions = True

            skill.instructions = '\n'.join(instructions_lines).strip()
            skill._full_loaded = True
        except Exception:
            pass

    def list_skills(self, workspace: Optional[str] = None) -> List[Skill]:
        """
        List all available skills (frontmatter only, no full content load).

        Args:
            workspace: Optional workspace path

        Returns:
            List of all Skill objects
        """
        if not self._discovered:
            self.discover_skills(workspace)
        return list(self._skills.values())

    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a skill by name without full content load."""
        return self._skills.get(name)

    def reload(self, workspace: Optional[str] = None) -> List[Skill]:
        """Reload all skills from disk."""
        self._skills.clear()
        self._discovered = False
        return self.discover_skills(workspace)

    def _parse_skill_content(
        self,
        content: str,
        file_path: str,
        base_dir: Optional[str] = None,
        skill_name: Optional[str] = None
    ) -> Optional[Skill]:
        """
        Parse skill content from markdown text with YAML frontmatter.

        Expected format:
            ---
            name: skill-name
            description: Short description
            when_to_use: When to use this skill
            allowed-tools: [Read, Grep]
            model: opus
            effort: high
            context: fork
            ---
            # Skill Name

            Skill content here...

            ## Instructions
            Step 1...
            Step 2...

        Args:
            content: The markdown content
            file_path: Path to the source file
            base_dir: Optional base directory for the skill
            skill_name: Optional skill name (for legacy single-file format)

        Returns:
            Parsed Skill object
        """
        frontmatter, remaining = parse_yaml_frontmatter(content)

        name = frontmatter.get('name', skill_name or '')
        if not name:
            name = Path(file_path).stem
            if base_dir:
                name = Path(base_dir).name

        description = frontmatter.get('description', '')
        if not description and remaining:
            description = extract_description_fallback(remaining, name)

        when_to_use = frontmatter.get('when_to_use')
        if when_to_use:
            when_to_use = when_to_use.strip('"\'')

        allowed_tools = frontmatter.get('allowed-tools', [])
        if isinstance(allowed_tools, str):
            allowed_tools = [t.strip() for t in allowed_tools.strip('[]').split(',')]

        model = frontmatter.get('model')
        effort = frontmatter.get('effort')
        context = frontmatter.get('context')
        agent = frontmatter.get('agent')
        version = frontmatter.get('version')

        user_invocable = frontmatter.get('user-invocable', True)
        if isinstance(user_invocable, str):
            user_invocable = user_invocable.lower() != 'false'

        disable_model_invocation = frontmatter.get('disable-model-invocation', False)
        if isinstance(disable_model_invocation, str):
            disable_model_invocation = disable_model_invocation.lower() == 'true'

        paths = frontmatter.get('paths', [])
        if isinstance(paths, str):
            paths = [p.strip() for p in paths.strip('[]').split(',')]

        arguments_raw = frontmatter.get('arguments', [])
        arguments = []
        if isinstance(arguments_raw, list):
            for arg in arguments_raw:
                if isinstance(arg, dict):
                    arguments.append(arg)
                elif isinstance(arg, str):
                    arg_match = re.match(r'-\s*name:\s*(\S+)', arg)
                    if arg_match:
                        arguments.append({'name': arg_match.group(1)})

        return Skill(
            name=name,
            description=description,
            when_to_use=when_to_use,
            allowed_tools=allowed_tools,
            model=model,
            effort=effort,
            context=context,
            agent=agent,
            paths=paths,
            version=version,
            user_invocable=user_invocable,
            disable_model_invocation=disable_model_invocation,
            arguments=arguments,
            hooks=frontmatter.get('hooks'),
            instructions="",
            content=content,
            file_path=file_path,
            base_dir=base_dir,
            loaded_from='skills',
            _full_loaded=False,
        )


_global_manager: Optional[SkillManager] = None


def get_skill_manager() -> SkillManager:
    """Get the global skill manager instance."""
    global _global_manager
    if _global_manager is None:
        _global_manager = SkillManager()
    return _global_manager


def discover_skills(workspace: Optional[str] = None) -> List[Skill]:
    """Discover all skills in the skills directory."""
    return get_skill_manager().discover_skills(workspace)


def load_skill(name: str) -> Optional[Skill]:
    """Load a specific skill by name (full content)."""
    return get_skill_manager().load_skill(name)


def list_skills(workspace: Optional[str] = None) -> List[Skill]:
    """List all available skills (frontmatter only for discovery)."""
    return get_skill_manager().list_skills(workspace)


def get_skill(name: str) -> Optional[Skill]:
    """Get a skill by name without loading full content."""
    return get_skill_manager().get_skill(name)