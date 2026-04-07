"""
Agent-specific prompts for Claude Code CLI.

Reference: src/tools/AgentTool/prompt.ts
"""

from typing import List, Optional, Set

# Default agent prompt
DEFAULT_AGENT_PROMPT = """You are an agent for Claude Code, Anthropic's official CLI for Claude. Given the user's message, you should use the tools available to complete the task. Complete the task fully—don't gold-plate, but don't leave it half-done. When you complete the task, respond with a concise report covering what was done and any key findings — the caller will relay this to the user, so it only needs the essentials."""


def get_tools_description(agent: dict) -> str:
    """Get tools description for an agent."""
    tools = agent.get("tools", [])
    disallowed_tools = agent.get("disallowed_tools", [])
    
    has_allowlist = tools and len(tools) > 0
    has_denylist = disallowed_tools and len(disallowed_tools) > 0
    
    if has_allowlist and has_denylist:
        # Both defined: filter allowlist by denylist
        deny_set = set(disallowed_tools)
        effective_tools = [t for t in tools if t not in deny_set]
        if not effective_tools:
            return "None"
        return ", ".join(effective_tools)
    elif has_allowlist:
        # Allowlist only
        return ", ".join(tools)
    elif has_denylist:
        # Denylist only
        return f"All tools except {', '.join(disallowed_tools)}"
    
    # No restrictions
    return "All tools"


def format_agent_line(agent: dict) -> str:
    """Format one agent line for the agent listing."""
    agent_type = agent.get("agent_type", agent.get("agentType", "unknown"))
    when_to_use = agent.get("when_to_use", agent.get("whenToUse", ""))
    tools_description = get_tools_description(agent)
    return f"- {agent_type}: {when_to_use} (Tools: {tools_description})"


def get_fork_section(fork_enabled: bool = False) -> str:
    """Get fork section of agent prompt."""
    if not fork_enabled:
        return ""
    
    return """
## When to fork

Fork yourself (omit `subagent_type`) when the intermediate tool output isn't worth keeping in your context. The criterion is qualitative — "will I need this output again" — not task size.
- **Research**: fork open-ended questions. If research can be broken into independent questions, launch parallel forks in one message. A fork beats a fresh subagent for this — it inherits context and shares your cache.
- **Implementation**: prefer to fork implementation work that requires more than a couple of edits. Do research before jumping to implementation.

Forks are cheap because they share your prompt cache. Don't set `model` on a fork — a different model can't reuse the parent's cache. Pass a short `name` (one or two words, lowercase) so the user can see the fork in the teams panel and steer it mid-run.

**Don't peek.** The tool result includes an `output_file` path — do not Read or tail it unless the user explicitly asks for a progress check. You get a completion notification; trust it. Reading the transcript mid-flight pulls the fork's tool noise into your context, which defeats the point of forking.

**Don't race.** After launching, you know nothing about what the fork found. Never fabricate or predict fork results in any format — not as prose, summary, or structured output. The notification arrives as a user-role message in a later turn; it is never something you write yourself. If the user asks a follow-up before the notification lands, tell them the fork is still running — give status, not a guess.

**Writing a fork prompt.** Since the fork inherits your context, the prompt is a *directive* — what to do, not what the situation is. Be specific about scope: what's in, what's out, what another agent is handling. Don't re-explain background.
"""


def get_writing_prompt_section(fork_enabled: bool = False) -> str:
    """Get writing prompt section of agent prompt."""
    return f"""
## Writing the prompt

{f"When spawning a fresh agent (with a `subagent_type`), it starts with zero context. " if fork_enabled else ""}Brief the agent like a smart colleague who just walked into the room — it hasn't seen this conversation, doesn't know what you've tried, doesn't understand why this task matters.
- Explain what you're trying to accomplish and why.
- Describe what you've already learned or ruled out.
- Give enough context about the surrounding problem that the agent can make judgment calls rather than just following a narrow instruction.
- If you need a short response, say so ("report in under 200 words").
- Lookups: hand over the exact command. Investigations: hand over the question — prescribed steps become dead weight when the premise is wrong.

{f"For fresh agents, terse" if fork_enabled else "Terse"} command-style prompts produce shallow, generic work.

**Never delegate understanding.** Don't write "based on your findings, fix the bug" or "based on the research, implement it." Those phrases push synthesis onto the agent instead of doing it yourself. Write prompts that prove you understood: include file paths, line numbers, what specifically to change.
"""


def get_agent_tool_prompt(
    agent_definitions: Optional[List[dict]] = None,
    is_coordinator: bool = False,
    allowed_agent_types: Optional[List[str]] = None,
    fork_enabled: bool = False,
) -> str:
    """Get the Agent tool prompt.
    
    Args:
        agent_definitions: List of agent definitions
        is_coordinator: Whether this is for coordinator mode
        allowed_agent_types: List of allowed agent types to filter
        fork_enabled: Whether fork subagent feature is enabled
    
    Returns:
        The agent tool prompt string
    """
    # Filter agents by allowed types when Agent(x,y) restricts which agents can be spawned
    effective_agents = agent_definitions or []
    if allowed_agent_types:
        effective_agents = [
            a for a in effective_agents
            if a.get("agent_type", a.get("agentType")) in allowed_agent_types
        ]
    
    # Build agent list section
    if effective_agents:
        agent_list_section = f"""Available agent types and the tools they have access to:
{chr(10).join(format_agent_line(agent) for agent in effective_agents)}"""
    else:
        agent_list_section = "Available agent types are listed in <system-reminder> messages in the conversation."
    
    # Shared core prompt
    fork_instruction = (
        "When using the Agent tool, specify a subagent_type to use a specialized agent, or omit it to fork yourself — a fork inherits your full conversation context."
        if fork_enabled
        else "When using the Agent tool, specify a subagent_type parameter to select which agent type to use. If omitted, the general-purpose agent is used."
    )
    
    shared = f"""Launch a new agent to handle complex, multi-step tasks autonomously.

The Agent tool launches specialized agents (subprocesses) that autonomously handle complex tasks. Each agent type has specific capabilities and tools available to it.

{agent_list_section}

{fork_instruction}"""
    
    # Coordinator mode gets the slim prompt
    if is_coordinator:
        return shared
    
    # When NOT to use section (only for non-fork mode)
    when_not_to_use_section = ""
    if not fork_enabled:
        when_not_to_use_section = """
When NOT to use the Agent tool:
- If you want to read a specific file path, use the Read tool or the Glob tool instead of the Agent tool, to find the match more quickly
- If you are searching for a specific class definition like "class Foo", use the Glob tool instead, to find the match more quickly
- If you are searching for code within a specific file or set of 2-3 files, use the Read tool instead of the Agent tool, to find the match more quickly
- Other tasks that are not related to the agent descriptions above
"""
    
    # Build full prompt
    return f"""{shared}
{when_not_to_use_section}

Usage notes:
- Always include a short description (3-5 words) summarizing what the agent will do
- Launch multiple agents concurrently whenever possible, to maximize performance; to do that, use a single message with multiple tool uses
- When the agent is done, it will return a single message back to you. The result returned by the agent is not visible to the user. To show the user the result, you should send a text message back to the user with a concise summary of the result.
- You can optionally run agents in the background using the run_in_background parameter. When an agent runs in the background, you will be automatically notified when it completes — do NOT sleep, poll, or proactively check on its progress. Continue with other work or respond to the user instead.
- **Foreground vs background**: Use foreground (default) when you need the agent's results before you can proceed — e.g., research agents whose findings inform your next steps. Use background when you have genuinely independent work to do in parallel.
- To continue a previously spawned agent, use SendMessage with the agent's ID or name as the `to` field. The agent resumes with its full context preserved. {f"Each fresh Agent invocation with a subagent_type starts without context — provide a complete task description." if fork_enabled else "Each Agent invocation starts fresh — provide a complete task description."}
- The agent's outputs should generally be trusted
- Clearly tell the agent whether you expect it to write code or just to do research (search, file reads, web fetches, etc.){"" if fork_enabled else ", since it is not aware of the user's intent"}
- If the agent description mentions that it should be used proactively, then you should try your best to use it without the user having to ask for it first. Use your judgement.
- If the user specifies that they want you to run agents "in parallel", you MUST send a single message with multiple Agent tool use content blocks. For example, if you need to launch both a build-validator agent and a test-runner agent in parallel, send a single message with both tool calls.
- You can optionally set `isolation: "worktree"` to run the agent in a temporary git worktree, giving it an isolated copy of the repository. The worktree is automatically cleaned up if the agent makes no changes; if changes are made, the worktree path and branch are returned in the result.{get_fork_section(fork_enabled)}{get_writing_prompt_section(fork_enabled)}
"""


def enhance_system_prompt_with_env_details(
    existing_system_prompt: List[str],
    cwd: str,
    is_git: bool = False,
    platform_name: Optional[str] = None,
    shell: Optional[str] = None,
    os_version: Optional[str] = None,
    model_id: Optional[str] = None,
    enabled_tool_names: Optional[Set[str]] = None,
) -> List[str]:
    """Enhance system prompt with environment details.
    
    Args:
        existing_system_prompt: Existing system prompt sections
        cwd: Current working directory
        is_git: Whether in a git repository
        platform_name: Platform name
        shell: Shell name
        os_version: OS version
        model_id: Model ID
        enabled_tool_names: Set of enabled tool names
    
    Returns:
        Enhanced system prompt sections
    """
    notes = """Notes:
- Agent threads always have their cwd reset between bash calls, as a result please only use absolute file paths.
- In your final response, share file paths (always absolute, never relative) that are relevant to the task. Include code snippets only when the exact text is load-bearing (e.g., a bug you found, a function signature the caller asked for) — do not recap code you merely read.
- For clear communication with the user the assistant MUST avoid using emojis.
- Do not use a colon before tool calls. Text like "Let me read the file:" followed by a read tool call should just be "Let me read the file." with a period."""
    
    # Build environment info
    import os
    import platform
    
    if platform_name is None:
        platform_name = platform.system().lower()
    
    if shell is None:
        shell = os.environ.get("SHELL", "unknown")
    
    if os_version is None:
        os_version = f"{platform.system()} {platform.release()}"
    
    env_items = [
        f"Working directory: {cwd}",
        f"Is directory a git repo: {'Yes' if is_git else 'No'}",
        f"Platform: {platform_name}",
        f"Shell: {shell}",
        f"OS Version: {os_version}",
    ]
    
    if model_id:
        env_items.append(f"You are powered by the model {model_id}.")
    
    env_info = "\n".join([
        "Here is useful information about the environment you are running in:",
        "<env>",
        *env_items,
        "</env>",
    ])
    
    return [
        *existing_system_prompt,
        notes,
        env_info,
    ]
