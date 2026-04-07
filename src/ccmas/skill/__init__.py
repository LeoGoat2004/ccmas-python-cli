"""
Skill module for CCMAS.

This module provides the skill system for managing and invoking skills.
"""

from ccmas.skill.manager import (
    Skill,
    SkillManager,
    discover_skills,
    get_skill,
    get_skill_manager,
    list_skills,
    load_skill,
)
from ccmas.skill.tool import (
    SkillParser,
    SkillTool,
    get_available_skills,
    invoke_skill,
)

__all__ = [
    "Skill",
    "SkillManager",
    "SkillTool",
    "SkillParser",
    "discover_skills",
    "get_skill",
    "get_skill_manager",
    "list_skills",
    "load_skill",
    "invoke_skill",
    "get_available_skills",
    "register_skill_tools",
]


def register_skill_tools():
    """Register skill tools in the global tool registry."""
    from ccmas.tool.registry import register_tool

    register_tool(SkillTool())