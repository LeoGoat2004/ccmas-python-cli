"""
Prompt module for CCMAS CLI.

This module provides prompt building functionality for system prompts,
agent prompts, and tool-specific prompts.
"""

from .system import (
    build_system_prompt,
    get_actions_section,
    get_doing_tasks_section,
    get_env_info,
    get_intro_section,
    get_output_efficiency_section,
    get_system_section,
    get_tone_style_section,
    get_using_tools_section,
    prepend_bullets,
)

from .agent import (
    DEFAULT_AGENT_PROMPT,
    enhance_system_prompt_with_env_details,
    format_agent_line,
    get_agent_tool_prompt,
    get_fork_section,
    get_writing_prompt_section,
)

from .tools import (
    AGENT_TOOL_NAME,
    BASH_TOOL_NAME,
    EDIT_TOOL_NAME,
    GLOB_TOOL_NAME,
    GREP_TOOL_NAME,
    READ_TOOL_NAME,
    WRITE_TOOL_NAME,
    get_agent_tool_prompt_simple,
    get_bash_tool_prompt,
    get_edit_tool_prompt,
    get_glob_tool_prompt,
    get_grep_tool_prompt,
    get_read_tool_prompt,
    get_write_tool_prompt,
)

__all__ = [
    # System prompts
    "build_system_prompt",
    "get_actions_section",
    "get_doing_tasks_section",
    "get_env_info",
    "get_intro_section",
    "get_output_efficiency_section",
    "get_system_section",
    "get_tone_style_section",
    "get_using_tools_section",
    "prepend_bullets",
    # Agent prompts
    "DEFAULT_AGENT_PROMPT",
    "enhance_system_prompt_with_env_details",
    "format_agent_line",
    "get_agent_tool_prompt",
    "get_fork_section",
    "get_writing_prompt_section",
    # Tool prompts
    "AGENT_TOOL_NAME",
    "BASH_TOOL_NAME",
    "EDIT_TOOL_NAME",
    "GLOB_TOOL_NAME",
    "GREP_TOOL_NAME",
    "READ_TOOL_NAME",
    "WRITE_TOOL_NAME",
    "get_agent_tool_prompt_simple",
    "get_bash_tool_prompt",
    "get_edit_tool_prompt",
    "get_glob_tool_prompt",
    "get_grep_tool_prompt",
    "get_read_tool_prompt",
    "get_write_tool_prompt",
]
