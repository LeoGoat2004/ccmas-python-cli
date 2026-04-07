"""
Tool-specific prompts for Claude Code CLI.

Reference: src/tools/*/prompt.ts
"""

from typing import Optional


# Tool name constants
BASH_TOOL_NAME = "Bash"
READ_TOOL_NAME = "Read"
WRITE_TOOL_NAME = "Write"
EDIT_TOOL_NAME = "Edit"
GLOB_TOOL_NAME = "Glob"
GREP_TOOL_NAME = "Grep"
AGENT_TOOL_NAME = "Agent"


def get_bash_tool_prompt(
    max_timeout_ms: int = 600000,
    default_timeout_ms: int = 120000,
    sandbox_enabled: bool = False,
) -> str:
    """Get Bash tool prompt.
    
    Args:
        max_timeout_ms: Maximum timeout in milliseconds
        default_timeout_ms: Default timeout in milliseconds
        sandbox_enabled: Whether sandbox is enabled
    
    Returns:
        Bash tool prompt string
    """
    tool_preference_items = [
        f"File search: Use {GLOB_TOOL_NAME} (NOT find or ls)",
        f"Content search: Use {GREP_TOOL_NAME} (NOT grep or rg)",
        f"Read files: Use {READ_TOOL_NAME} (NOT cat/head/tail)",
        f"Edit files: Use {EDIT_TOOL_NAME} (NOT sed/awk)",
        f"Write files: Use {WRITE_TOOL_NAME} (NOT echo >/cat <<EOF)",
        "Communication: Output text directly (NOT echo/printf)",
    ]
    
    avoid_commands = "`find`, `grep`, `cat`, `head`, `tail`, `sed`, `awk`, or `echo`"
    
    multiple_commands_subitems = [
        f"If the commands are independent and can run in parallel, make multiple {BASH_TOOL_NAME} tool calls in a single message. Example: if you need to run \"git status\" and \"git diff\", send a single message with two {BASH_TOOL_NAME} tool calls in parallel.",
        "If the commands depend on each other and must run sequentially, use a single Bash call with '&&' to chain them together.",
        "Use ';' only when you need to run commands sequentially but don't care if earlier commands fail.",
        "DO NOT use newlines to separate commands (newlines are ok in quoted strings).",
    ]
    
    git_subitems = [
        "Prefer to create a new commit rather than amending an existing commit.",
        "Before running destructive operations (e.g., git reset --hard, git push --force, git checkout --), consider whether there is a safer alternative that achieves the same goal. Only use destructive operations when they are truly the best approach.",
        "Never skip hooks (--no-verify) or bypass signing (--no-gpg-sign, -c commit.gpgsign=false) unless the user has explicitly asked for it. If a hook fails, investigate and fix the underlying issue.",
    ]
    
    sleep_subitems = [
        "Do not sleep between commands that can run immediately — just run them.",
        "If your command is long running and you would like to be notified when it finishes — use `run_in_background`. No sleep needed.",
        "Do not retry failing commands in a sleep loop — diagnose the root cause.",
        "If waiting for a background task you started with `run_in_background`, you will be notified when it completes — do not poll.",
        "If you must sleep, keep the duration short (1-5 seconds) to avoid blocking the user.",
    ]
    
    background_note = "You can use the `run_in_background` parameter to run the command in the background. Only use this if you don't need the result immediately and are OK being notified when the command completes later. You do not need to check the output right away - you'll be notified when it finishes. You do not need to use '&' at the end of the command when using this parameter."
    
    instruction_items = [
        "If your command will create new directories or files, first use this tool to run `ls` to verify the parent directory exists and is the correct location.",
        "Always quote file paths that contain spaces with double quotes in your command (e.g., cd \"path with spaces/file.txt\")",
        "Try to maintain your current working directory throughout the session by using absolute paths and avoiding usage of `cd`. You may use `cd` if the User explicitly requests it.",
        f"You may specify an optional timeout in milliseconds (up to {max_timeout_ms}ms / {max_timeout_ms // 60000} minutes). By default, your command will timeout after {default_timeout_ms}ms ({default_timeout_ms // 60000} minutes).",
        background_note,
        "When issuing multiple commands:",
        multiple_commands_subitems,
        "For git commands:",
        git_subitems,
        "Avoid unnecessary `sleep` commands:",
        sleep_subitems,
    ]
    
    # Prepend bullets to items
    def prepend_bullets(items):
        result = []
        for item in items:
            if isinstance(item, list):
                result.extend([f"  - {subitem}" for subitem in item])
            else:
                result.append(f" - {item}")
        return result
    
    sandbox_section = ""
    if sandbox_enabled:
        sandbox_section = """

## Command sandbox
By default, your command will be run in a sandbox. This sandbox controls which directories and network hosts commands may access or modify without an explicit override.

For temporary files, always use the `$TMPDIR` environment variable. TMPDIR is automatically set to the correct sandbox-writable directory in sandbox mode. Do NOT use `/tmp` directly - use `$TMPDIR` instead."""
    
    return f"""Executes a given bash command and returns its output.

The working directory persists between commands, but shell state does not. The shell environment is initialized from the user's profile (bash or zsh).

IMPORTANT: Avoid using this tool to run {avoid_commands} commands, unless explicitly instructed or after you have verified that a dedicated tool cannot accomplish your task. Instead, use the appropriate dedicated tool as this will provide a much better experience for the user:

{chr(10).join(prepend_bullets(tool_preference_items))}
While the {BASH_TOOL_NAME} tool can do similar things, it's better to use the built-in tools as they provide a better user experience and make it easier to review tool calls and give permission.

# Instructions
{chr(10).join(prepend_bullets(instruction_items))}{sandbox_section}
"""


def get_read_tool_prompt(
    max_lines: int = 2000,
    supports_pdf: bool = False,
    supports_images: bool = True,
    supports_notebooks: bool = True,
) -> str:
    """Get Read tool prompt.
    
    Args:
        max_lines: Maximum lines to read by default
        supports_pdf: Whether PDF reading is supported
        supports_images: Whether image reading is supported
        supports_notebooks: Whether Jupyter notebook reading is supported
    
    Returns:
        Read tool prompt string
    """
    pdf_instruction = ""
    if supports_pdf:
        pdf_instruction = """
- This tool can read PDF files (.pdf). For large PDFs (more than 10 pages), you MUST provide the pages parameter to read specific page ranges (e.g., pages: "1-5"). Reading a large PDF without the pages parameter will fail. Maximum 20 pages per request."""
    
    image_instruction = ""
    if supports_images:
        image_instruction = "- This tool allows Claude Code to read images (eg PNG, JPG, etc). When reading an image file the contents are presented visually as Claude Code is a multimodal LLM."
    
    notebook_instruction = ""
    if supports_notebooks:
        notebook_instruction = "- This tool can read Jupyter notebooks (.ipynb files) and returns all cells with their outputs, combining code, text, and visualizations."
    
    return f"""Reads a file from the local filesystem. You can access any file directly by using this tool.
Assume this tool is able to read all files on the machine. If the User provides a path to a file assume that path is valid. It is okay to read a file that does not exist; an error will be returned.

Usage:
- The file_path parameter must be an absolute path, not a relative path
- By default, it reads up to {max_lines} lines starting from the beginning of the file
- You can optionally specify a line offset and limit (especially handy for long files), but it's recommended to read the whole file by not providing these parameters
- Results are returned using cat -n format, with line numbers starting at 1
{image_instruction}{pdf_instruction}{notebook_instruction}
- This tool can only read files, not directories. To read a directory, use an ls command via the {BASH_TOOL_NAME} tool.
- You will regularly be asked to read screenshots. If the user provides a path to a screenshot, ALWAYS use this tool to view the file at the path. This tool will work with all temporary file paths.
- If you read a file that exists but has empty contents you will receive a system reminder warning in place of file contents."""


def get_write_tool_prompt() -> str:
    """Get Write tool prompt.
    
    Returns:
        Write tool prompt string
    """
    return f"""Writes a file to the local filesystem.

Usage:
- This tool will overwrite the existing file if there is one at the provided path.
- If this is an existing file, you MUST use the {READ_TOOL_NAME} tool first to read the file's contents. This tool will fail if you did not read the file first.
- Prefer the Edit tool for modifying existing files — it only sends the diff. Only use this tool to create new files or for complete rewrites.
- NEVER create documentation files (*.md) or README files unless explicitly requested by the User.
- Only use emojis if the user explicitly requests it. Avoid writing emojis to files unless asked."""


def get_edit_tool_prompt() -> str:
    """Get Edit tool prompt.
    
    Returns:
        Edit tool prompt string
    """
    return f"""Edits a file by replacing specific text.

Usage:
- You MUST use the {READ_TOOL_NAME} tool first to read the file's contents before editing.
- The old_str parameter is the exact text to find and replace. It must match exactly.
- The new_str parameter is the text to replace it with.
- The file_path parameter must be an absolute path, not a relative path.
- This tool will only replace the first occurrence of old_str in the file.
- Prefer this tool over {WRITE_TOOL_NAME} for modifying existing files, as it only sends the diff."""


def get_glob_tool_prompt() -> str:
    """Get Glob tool prompt.
    
    Returns:
        Glob tool prompt string
    """
    return """Fast file pattern matching tool that works with any codebase size.

Usage:
- Supports glob patterns like "*.js" or "src/**/*.ts"
- Returns matching file paths sorted by modification time
- Use this tool when you need to find files by name patterns
- When you are doing an open ended search that may require multiple rounds of globbing and grepping, use the Agent tool instead
- You have the capability to call multiple tools in a single response. It is always better to speculatively perform multiple searches as a batch that are potentially useful."""


def get_grep_tool_prompt() -> str:
    """Get Grep tool prompt.
    
    Returns:
        Grep tool prompt string
    """
    return """A powerful search tool built on ripgrep

Usage:
- ALWAYS use Grep for search tasks. NEVER invoke `grep` or `rg` as a Bash command. The Grep tool has been optimized for correct permissions and access.
- Supports full regex syntax (e.g., "log.*Error", "function\\s+\\w+")
- Filter files with glob parameter (e.g., "*.js", "**/*.tsx") or type parameter (e.g., js, py, rust, go, java, etc.)
- Output modes: "content" shows matching lines, "files_with_matches" shows only file paths (default), "count" shows match counts
- Use Agent tool for open-ended searches requiring multiple rounds
- Pattern syntax: Uses ripgrep (not grep) - literal braces need escaping (e.g., `interface{}` to find `interface{}` in Go code)
- Multiline matching: By default patterns match within single lines only. For cross-line patterns set multiline: true."""


def get_agent_tool_prompt_simple() -> str:
    """Get simple Agent tool prompt.
    
    Returns:
        Simple Agent tool prompt string
    """
    return f"""Launch a new agent to handle complex, multi-step tasks autonomously.

The {AGENT_TOOL_NAME} tool launches specialized agents (subprocesses) that autonomously handle complex tasks. Each agent type has specific capabilities and tools available to it.

Usage:
- Specify a subagent_type parameter to select which agent type to use
- If omitted, the general-purpose agent is used
- Always include a short description (3-5 words) summarizing what the agent will do
- When the agent is done, it will return a single message back to you
- The result returned by the agent is not visible to the user - you should send a text message back to the user with a concise summary"""
