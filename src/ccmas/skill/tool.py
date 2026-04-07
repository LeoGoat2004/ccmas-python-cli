"""
Skill tool for executing skills.

This tool allows the agent to invoke skills using /skill-name syntax.
Implements Claude Code's skill invocation approach:
1. LLM receives skill listing (name + description) to decide which to use
2. On invoke, full SKILL.md content is loaded
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

from ccmas.skill.manager import Skill, get_skill, list_skills, load_skill
from ccmas.tool.base import Tool, ToolCallArgs, ToolExecutionResult


MAX_LISTING_DESC_CHARS = 250
SKILL_BUDGET_CONTEXT_CHARS = 8000


def format_skill_listing(skills: List[Skill], context_window_tokens: Optional[int] = None) -> str:
    """
    Format skills for LLM discovery within budget.

    Follows Claude Code's approach: only names and descriptions for discovery.
    Full content is loaded only when skill is actually invoked.

    Args:
        skills: List of skills to format
        context_window_tokens: Optional context window size for budget calculation

    Returns:
        Formatted skill listing string
    """
    if not skills:
        return "No skills available."

    budget = SKILL_BUDGET_CONTEXT_CHARS
    if context_window_tokens:
        budget = min(budget, int(context_window_tokens * 0.01 * 4))

    entries = []
    for skill in skills:
        desc = skill.display_description
        if len(desc) > MAX_LISTING_DESC_CHARS:
            desc = desc[:MAX_LISTING_DESC_CHARS - 1] + "…"
        entries.append(f"- {skill.name}: {desc}")

    if not entries:
        return "No skills available."

    result = []
    current_len = 0

    for entry in entries:
        entry_len = len(entry) + 1
        if current_len + entry_len <= budget:
            result.append(entry)
            current_len += entry_len
        else:
            break

    if not result:
        result = [f"- {skill.name}" for skill in skills[:10]]

    return "\n".join(result)


class SkillTool(Tool):
    """
    Tool for invoking skills.

    Skills are reusable instruction sets stored in SKILL.md files.
    LLM discovers available skills via listing, then invokes to get full content.
    """

    @property
    def name(self) -> str:
        """Get the tool name."""
        return "skill"

    @property
    def description(self) -> str:
        """Get the tool description."""
        return """Execute a skill within the main conversation

When users ask you to perform tasks, check if any of the available skills match. Skills provide specialized capabilities and domain knowledge.

When users reference a "slash command" or "/<something>" (e.g., "/commit", "/review-pr"), they are referring to a skill. Use this tool to invoke it.

How to invoke:
- Use this tool with the skill name and optional arguments
- Examples:
  - skill: "pdf" - invoke the pdf skill
  - skill: "commit", args: "-m 'Fix bug'" - invoke with arguments
  - skill: "review-pr", args: "123" - invoke with arguments

Important:
- Available skills are listed in system-reminder messages in the conversation
- When a skill matches the user's request, this is a BLOCKING REQUIREMENT: invoke the relevant Skill tool BEFORE generating any other response about the task
- NEVER mention a skill without actually calling this tool
- Do not invoke a skill that is already running
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        """Get the JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "skill": {
                    "type": "string",
                    "description": "The skill name. E.g., 'commit', 'review-pr', or 'pdf'",
                },
                "args": {
                    "type": "string",
                    "description": "Optional arguments for the skill",
                },
            },
            "required": ["skill"],
        }

    async def execute(self, args: ToolCallArgs) -> ToolExecutionResult:
        """
        Execute skill invocation.

        Args:
            args: Tool call arguments containing skill and optional args

        Returns:
            ToolExecutionResult with skill content
        """
        start_time = time.time()

        skill_name = args.arguments.get("skill")
        if not skill_name:
            output = self._create_error_output(
                args.tool_call_id, "Error: 'skill' argument is required"
            )
            return self._create_result(
                args.tool_call_id, output, 0.0, {"error": "missing_skill_name"}
            )

        skill = load_skill(skill_name)
        if not skill:
            available = [s.name for s in list_skills()]
            available_str = ", ".join(available) if available else "none"
            output = self._create_error_output(
                args.tool_call_id,
                f"Error: Skill '{skill_name}' not found. Available skills: {available_str}",
            )
            execution_time = (time.time() - start_time) * 1000
            return self._create_result(
                args.tool_call_id,
                output,
                execution_time,
                {"error": "skill_not_found", "skill_name": skill_name},
            )

        skill_args = args.arguments.get("args", "")
        content = self._format_skill_output(skill, skill_args)

        execution_time = (time.time() - start_time) * 1000
        output = self._create_success_output(args.tool_call_id, content)
        return self._create_result(
            args.tool_call_id,
            output,
            execution_time,
            {
                "skill_name": skill.name,
                "skill_description": skill.description,
                "allowed_tools": skill.allowed_tools,
                "model": skill.model,
            },
        )

    def _format_skill_output(self, skill: Skill, args: str = "") -> str:
        """
        Format skill output for display/injection.

        Args:
            skill: The skill to format
            args: Optional arguments passed to the skill

        Returns:
            Formatted skill content ready for injection into conversation
        """
        lines = []

        if skill.base_dir:
            lines.append(f"Base directory for this skill: {skill.base_dir}")
            lines.append("")

        lines.append(f"# {skill.name}")
        lines.append("")

        if skill.description:
            lines.append(f"**Description:** {skill.description}")
            lines.append("")

        if args:
            lines.append(f"**Arguments:** {args}")
            lines.append("")

        if skill.instructions:
            lines.append("## Instructions")
            lines.append("")
            lines.append(skill.instructions)

        return "\n".join(lines)


class SkillParser:
    """Parser for skill commands in /skill-name format."""

    SKILL_PATTERN = re.compile(r"^/([a-zA-Z0-9_-]+)$")

    @classmethod
    def parse(cls, text: str) -> Optional[str]:
        """Parse skill command from text."""
        match = cls.SKILL_PATTERN.match(text.strip())
        if match:
            return match.group(1)
        return None

    @classmethod
    def extract_skills(cls, text: str) -> List[str]:
        """Extract all skill invocations from text."""
        skills: List[str] = []
        for match in cls.SKILL_PATTERN.finditer(text):
            skill_name = match.group(1)
            if skill_name not in skills:
                skills.append(skill_name)
        return skills


def invoke_skill(skill_name: str) -> Optional[Skill]:
    """Invoke a skill by name."""
    return load_skill(skill_name)


def get_available_skills() -> List[Skill]:
    """Get all available skills."""
    return list_skills()


def get_skill_listing_for_prompt(workspace: Optional[str] = None) -> str:
    """
    Get formatted skill listing for LLM system prompt.

    This is called to include skill listing in the system prompt so LLM
    can discover available skills.

    Args:
        workspace: Optional workspace path

    Returns:
        Formatted skill listing
    """
    skills = list_skills(workspace)
    return format_skill_listing(skills)