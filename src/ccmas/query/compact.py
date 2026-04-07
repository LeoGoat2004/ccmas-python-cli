"""AutoCompact conversation compression core for CCMAS."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Literal, Optional, Union
from uuid import UUID, uuid4


POST_COMPACT_MAX_FILES_TO_RESTORE = 5
POST_COMPACT_TOKEN_BUDGET = 50_000
POST_COMPACT_MAX_TOKENS_PER_FILE = 5_000
POST_COMPACT_MAX_TOKENS_PER_SKILL = 5_000
POST_COMPACT_SKILLS_TOKEN_BUDGET = 25_000

MAX_COMPACT_STREAMING_RETRIES = 2
PTL_RETRY_MARKER = "[earlier conversation truncated for compaction retry]"

ERROR_MESSAGE_NOT_ENOUGH_MESSAGES = "Not enough messages to compact."
ERROR_MESSAGE_PROMPT_TOO_LONG = "Conversation too long. Press esc twice to go up a few messages and try again."
ERROR_MESSAGE_USER_ABORT = "API Error: Request was aborted."
ERROR_MESSAGE_INCOMPLETE_RESPONSE = "Compaction interrupted · This may be due to network issues — please try again."

COMPACT_MAX_OUTPUT_TOKENS = 4096


@dataclass
class CompactMetadata:
    compact_type: str = "auto"
    pre_compact_token_count: int = 0
    last_message_uuid: Optional[str] = None
    pre_compact_discovered_tools: Optional[List[str]] = None
    preserved_segment: Optional[Dict[str, str]] = None
    user_feedback: Optional[str] = None
    messages_summarized: Optional[int] = None


@dataclass
class CompactionResult:
    boundary_marker: Dict[str, Any]
    summary_messages: List[Dict[str, Any]]
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    hook_results: List[Dict[str, Any]] = field(default_factory=list)
    messages_to_keep: Optional[List[Dict[str, Any]]] = None
    user_display_message: Optional[str] = None
    pre_compact_token_count: Optional[int] = None
    post_compact_token_count: Optional[int] = None
    true_post_compact_token_count: Optional[int] = None
    compaction_usage: Optional[Dict[str, int]] = None


def estimate_tokens(text: str) -> int:
    """
    Estimate token count from text.

    Uses approximately 4 characters per token as a rough estimation.

    Args:
        text: Input text string

    Returns:
        Estimated token count
    """
    if not text:
        return 0
    return len(text) // 4


def estimate_tokens_for_messages(messages: List[Dict[str, Any]]) -> int:
    """
    Estimate total token count for a list of messages.

    Args:
        messages: List of message dictionaries

    Returns:
        Estimated total token count
    """
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        total += estimate_tokens(block.get("text", ""))
                    elif block.get("type") == "tool_use":
                        total += estimate_tokens(str(block.get("input", {})))
                    elif block.get("type") == "tool_result":
                        result_content = block.get("content", "")
                        if isinstance(result_content, str):
                            total += estimate_tokens(result_content)
                        elif isinstance(result_content, list):
                            for item in result_content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    total += estimate_tokens(item.get("text", ""))
        elif isinstance(content, str):
            total += estimate_tokens(content)
        if msg.get("type") == "system":
            total += estimate_tokens(content)
    return total


def strip_images_from_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Strip image blocks from user messages before sending for compaction.

    Images are not needed for generating a conversation summary and can
    cause the compaction API call itself to hit the prompt-too-long limit.

    Args:
        messages: List of message dictionaries

    Returns:
        Messages with image blocks replaced by [image] text markers
    """
    result = []
    for message in messages:
        if message.get("type") != "user":
            result.append(message)
            continue

        content = message.get("content", "")
        if not isinstance(content, list):
            result.append(message)
            continue

        has_media = False
        new_content = []
        for block in content:
            if block.get("type") == "image":
                has_media = True
                new_content.append({"type": "text", "text": "[image]"})
            elif block.get("type") == "document":
                has_media = True
                new_content.append({"type": "text", "text": "[document]"})
            elif block.get("type") == "tool_result" and isinstance(block.get("content"), list):
                tool_content = block.get("content", [])
                new_tool_content = []
                tool_has_media = False
                for item in tool_content:
                    if item.get("type") == "image":
                        tool_has_media = True
                        new_tool_content.append({"type": "text", "text": "[image]"})
                    elif item.get("type") == "document":
                        tool_has_media = True
                        new_tool_content.append({"type": "text", "text": "[document]"})
                    else:
                        new_tool_content.append(item)
                if tool_has_media:
                    has_media = True
                    new_content.append({**block, "content": new_tool_content})
                else:
                    new_content.append(block)
            else:
                new_content.append(block)

        if not has_media:
            result.append(message)
        else:
            result.append({**message, "content": new_content})

    return result


def create_compact_boundary(
    is_auto: bool = True,
    pre_compact_token_count: int = 0,
    last_message_uuid: Optional[str] = None,
    user_feedback: Optional[str] = None,
    messages_summarized: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Create a compact boundary system message.

    This marks the boundary between the summarized older conversation
    and the recent messages that are kept verbatim.

    Args:
        is_auto: Whether this is an automatic compaction
        pre_compact_token_count: Token count before compaction
        last_message_uuid: UUID of the last message before compaction
        user_feedback: Optional user feedback for partial compaction
        messages_summarized: Number of messages summarized

    Returns:
        System message dictionary representing the compact boundary
    """
    compact_type = "auto" if is_auto else "manual"

    return {
        "type": "system",
        "subtype": "compact_boundary",
        "uuid": str(uuid4()),
        "timestamp": datetime.now().isoformat(),
        "compact_metadata": {
            "compact_type": compact_type,
            "pre_compact_token_count": pre_compact_token_count,
            "last_message_uuid": last_message_uuid,
            "user_feedback": user_feedback,
            "messages_summarized": messages_summarized,
        },
    }


def format_compact_summary(summary: str) -> str:
    """
    Format the raw compact summary text.

    Removes analysis tags and normalizes the summary format.

    Args:
        summary: Raw summary text from LLM

    Returns:
        Formatted summary string
    """
    if not summary:
        return ""

    formatted = summary
    formatted = re.sub(r"<analysis>[\s\S]*?</analysis>", "", formatted)

    summary_match = re.search(r"<summary>([\s\S]*?)</summary>", formatted)
    if summary_match:
        content = summary_match.group(1) or ""
        formatted = re.sub(
            r"<summary>[\s\S]*?</summary>",
            f"Summary:\n{content.strip()}",
            formatted
        )

    formatted = re.sub(r"\n\n+", "\n\n", formatted)

    return formatted.strip()


def get_compact_user_summary_message(
    summary: str,
    suppress_follow_up_questions: bool = False,
    transcript_path: Optional[str] = None,
) -> str:
    """
    Create the user summary message content.

    Args:
        summary: The formatted summary text
        suppress_follow_up_questions: Whether to suppress follow-up questions
        transcript_path: Optional path to full transcript

    Returns:
        Summary message content string
    """
    formatted_summary = format_compact_summary(summary)

    base_summary = f"""This session is being continued from a previous conversation that ran out of context. The summary below covers the earlier portion of the conversation.

{formatted_summary}"""

    if transcript_path:
        base_summary += f"\n\nIf you need specific details from before compaction (like exact code snippets, error messages, or content you generated), read the full transcript at: {transcript_path}"

    if suppress_follow_up_questions:
        continuation = f"""{base_summary}
Continue the conversation from where it left off without asking the user any further questions. Resume directly — do not acknowledge the summary, do not recap what was happening, do not preface with "I'll continue" or similar. Pick up the last task as if the break never happened."""
        return continuation

    return base_summary


def create_summary_message(
    summary: str,
    suppress_follow_up_questions: bool = False,
    transcript_path: Optional[str] = None,
    is_visible_in_transcript_only: bool = True,
    is_compact_summary: bool = True,
) -> Dict[str, Any]:
    """
    Create a summary user message.

    Args:
        summary: The summary text
        suppress_follow_up_questions: Whether to suppress follow-up questions
        transcript_path: Optional path to transcript
        is_visible_in_transcript_only: Whether visible only in transcript
        is_compact_summary: Whether this is a compact summary message

    Returns:
        User message dictionary
    """
    content = get_compact_user_summary_message(
        summary,
        suppress_follow_up_questions,
        transcript_path,
    )

    return {
        "type": "user",
        "role": "user",
        "uuid": str(uuid4()),
        "timestamp": datetime.now().isoformat(),
        "content": content,
        "is_compact_summary": is_compact_summary,
        "is_visible_in_transcript_only": is_visible_in_transcript_only,
    }


def get_compact_prompt(custom_instructions: Optional[str] = None) -> str:
    """
    Get the full compact prompt for summarization.

    Args:
        custom_instructions: Optional custom instructions to include

    Returns:
        Full compact prompt string
    """
    no_tools_preamble = """CRITICAL: Respond with TEXT ONLY. Do NOT call any tools.

- Do NOT use Read, Bash, Grep, Glob, Edit, Write, or ANY other tool.
- You already have all the context you need in the conversation above.
- Tool calls will be REJECTED and will waste your only turn — you will fail the task.
- Your entire response must be plain text: an <analysis> block followed by a <summary> block.

"""

    base_prompt = """Your task is to create a detailed summary of the conversation so far, paying close attention to the user's explicit requests and your previous actions.
This summary should be thorough in capturing technical details, code patterns, and architectural decisions that would be essential for continuing development work without losing context.

Before providing your final summary, wrap your analysis in <analysis> tags to organize your thoughts. In your analysis process:

1. Chronologically analyze each message and section of the conversation. For each section thoroughly identify:
   - The user's explicit requests and intents
   - Your approach to addressing the user's requests
   - Key decisions, technical concepts and code patterns
   - Specific details like file names, full code snippets, function signatures, file edits
   - Errors that you ran into and how you fixed them
   - Pay special attention to specific user feedback that you received
2. Double-check for technical accuracy and completeness.

Your summary should include the following sections:

1. Primary Request and Intent: Capture all of the user's explicit requests and intents in detail
2. Key Technical Concepts: List all important technical concepts, technologies, and frameworks discussed.
3. Files and Code Sections: Enumerate specific files and code sections examined, modified, or created.
4. Errors and fixes: List all errors that you ran into, and how you fixed them.
5. Problem Solving: Document problems solved and any ongoing troubleshooting efforts.
6. All user messages: List ALL user messages that are not tool results.
7. Pending Tasks: Outline any pending tasks that you have explicitly been asked to work on.
8. Current Work: Describe in detail precisely what was being worked on immediately before this summary request.
9. Optional Next Step: List the next step that you will take that is related to the most recent work.

<example>
<analysis>
[Your thought process]
</analysis>

<summary>
1. Primary Request and Intent:
   [Detailed description]

2. Key Technical Concepts:
   - [Concept 1]
   - [Concept 2]

3. Files and Code Sections:
   - [File Name 1]
      - [Summary]
      - [Code Snippet]

4. Errors and fixes:
    - [Error description]: [How fixed]

5. Problem Solving:
   [Description]

6. All user messages:
    - [Message]

7. Pending Tasks:
    - [Task]

8. Current Work:
   [Description]

9. Optional Next Step:
   [Step]
</summary>
</example>

Please provide your summary based on the conversation so far.
"""

    no_tools_trailer = "\n\nREMINDER: Do NOT call any tools. Respond with plain text only."

    prompt = no_tools_preamble + base_prompt

    if custom_instructions and custom_instructions.strip():
        prompt += f"\n\nAdditional Instructions:\n{custom_instructions}"

    prompt += no_tools_trailer

    return prompt


def truncate_head_for_ptl_retry(
    messages: List[Dict[str, Any]],
    ptl_response_text: str,
    token_gap: Optional[int] = None,
) -> Optional[List[Dict[str, Any]]]:
    """
    Drop oldest API-round groups from messages when prompt-too-long occurs.

    This is a last-resort escape hatch when the compact request itself
    hits prompt-too-long. Falls back to dropping 20% of groups when
    the gap is unparseable.

    Args:
        messages: List of messages
        ptl_response_text: The prompt-too-long error response text
        token_gap: Optional token gap to cover

    Returns:
        Truncated messages list, or None if cannot truncate
    """
    if messages[0].get("type") == "user" and messages[0].get("is_meta") and messages[0].get("content") == PTL_RETRY_MARKER:
        messages = messages[1:]

    groups = group_messages_by_api_round(messages)
    if len(groups) < 2:
        return None

    if token_gap is not None:
        accumulated = 0
        drop_count = 0
        for g in groups:
            accumulated += estimate_tokens_for_messages(g)
            drop_count += 1
            if accumulated >= token_gap:
                break
    else:
        drop_count = max(1, len(groups) // 5)

    drop_count = min(drop_count, len(groups) - 1)
    if drop_count < 1:
        return None

    sliced = []
    for i in range(drop_count, len(groups)):
        sliced.extend(groups[i])

    if sliced and sliced[0].get("type") == "assistant":
        meta_user_message = {
            "type": "user",
            "role": "user",
            "uuid": str(uuid4()),
            "timestamp": datetime.now().isoformat(),
            "content": PTL_RETRY_MARKER,
            "is_meta": True,
        }
        sliced = [meta_user_message] + sliced

    return sliced


def group_messages_by_api_round(messages: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """
    Group messages by API round for PTL retry logic.

    Args:
        messages: List of messages

    Returns:
        List of message groups
    """
    if not messages:
        return []

    groups: List[List[Dict[str, Any]]] = []
    current_group: List[Dict[str, Any]] = []

    for msg in messages:
        if msg.get("type") == "user" and not current_group:
            current_group.append(msg)
        elif msg.get("type") == "assistant":
            current_group.append(msg)
        elif msg.get("type") == "tool":
            current_group.append(msg)
        else:
            if current_group:
                groups.append(current_group)
            current_group = [msg] if msg.get("type") == "user" else []

    if current_group:
        groups.append(current_group)

    return groups


def compact_messages(
    messages: List[Dict[str, Any]],
    recent_count: int = 20,
    custom_instructions: Optional[str] = None,
    summarize_callback: Optional[Callable[[str], str]] = None,
    suppress_follow_up_questions: bool = False,
    transcript_path: Optional[str] = None,
) -> CompactionResult:
    """
    Compact messages by summarizing older messages and preserving recent ones.

    This is the main entry point for AutoCompact. It:
    1. Strips images from messages to reduce token count
    2. Keeps the most recent N messages verbatim
    3. Summarizes the older messages using LLM
    4. Creates a compact boundary marker

    Args:
        messages: Complete list of conversation messages
        recent_count: Number of recent messages to keep verbatim (default: 20)
        custom_instructions: Optional custom instructions for summarization
        summarize_callback: Callback function that takes prompt and returns summary
        suppress_follow_up_questions: Whether to suppress follow-up questions in summary
        transcript_path: Optional path to transcript file

    Returns:
        CompactionResult containing boundary marker, summary messages, and metadata

    Raises:
        ValueError: If not enough messages to compact
    """
    if len(messages) == 0:
        raise ValueError(ERROR_MESSAGE_NOT_ENOUGH_MESSAGES)

    pre_compact_token_count = estimate_tokens_for_messages(messages)

    messages_to_keep = messages[-recent_count:] if recent_count > 0 else []
    messages_to_summarize = messages[:-recent_count] if recent_count > 0 else messages

    boundary_marker = create_compact_boundary(
        is_auto=True,
        pre_compact_token_count=pre_compact_token_count,
        last_message_uuid=messages[-1].get("uuid") if messages else None,
    )

    summary_text = ""
    if messages_to_summarize and summarize_callback:
        messages_for_summary = strip_images_from_messages(messages_to_summarize)

        prompt = get_compact_prompt(custom_instructions)

        combined_messages = messages_for_summary + [
            {
                "type": "user",
                "role": "user",
                "content": prompt,
            }
        ]

        try:
            summary_text = summarize_callback(prompt)
        except Exception:
            summary_text = ""

    summary_message = create_summary_message(
        summary=summary_text,
        suppress_follow_up_questions=suppress_follow_up_questions,
        transcript_path=transcript_path,
    )

    return CompactionResult(
        boundary_marker=boundary_marker,
        summary_messages=[summary_message],
        messages_to_keep=messages_to_keep,
        pre_compact_token_count=pre_compact_token_count,
        true_post_compact_token_count=estimate_tokens_for_messages(
            [boundary_marker, summary_message] + messages_to_keep
        ),
    )


def build_post_compact_messages(result: CompactionResult) -> List[Dict[str, Any]]:
    """
    Build the final messages list after compaction.

    Order: boundary marker, summary messages, messages to keep, attachments, hook results

    Args:
        result: CompactionResult from compact_messages

    Returns:
        Ordered list of messages for continued conversation
    """
    return [
        result.boundary_marker,
        *result.summary_messages,
        *(result.messages_to_keep or []),
        *result.attachments,
        *result.hook_results,
    ]


def merge_hook_instructions(
    user_instructions: Optional[str],
    hook_instructions: Optional[str],
) -> Optional[str]:
    """
    Merge user-supplied custom instructions with hook-provided instructions.

    User instructions come first; hook instructions are appended.

    Args:
        user_instructions: User-provided instructions
        hook_instructions: Hook-provided instructions

    Returns:
        Merged instructions or None
    """
    if not hook_instructions:
        return user_instructions or None
    if not user_instructions:
        return hook_instructions
    return f"{user_instructions}\n\n{hook_instructions}"


def get_partial_compact_prompt(
    custom_instructions: Optional[str] = None,
    direction: str = "from",
) -> str:
    """
    Get the partial compact prompt for summarizing a portion of conversation.

    Args:
        custom_instructions: Optional custom instructions
        direction: 'from' or 'up_to' - direction of partial compaction

    Returns:
        Partial compact prompt string
    """
    partial_prompt = f"""Your task is to create a detailed summary of the RECENT portion of the conversation — the messages that {'follow' if direction == 'from' else 'precede'} the selected point.

Before providing your final summary, wrap your analysis in <analysis> tags.

Your summary should include:
1. Primary Request and Intent
2. Key Technical Concepts
3. Files and Code Sections
4. Errors and fixes
5. Problem Solving
6. All user messages
7. Pending Tasks
8. Current Work
9. Optional Next Step

Follow the same <analysis>/<summary> format.
"""

    no_tools_preamble = """CRITICAL: Respond with TEXT ONLY. Do NOT call any tools.

- Do NOT use Read, Bash, Grep, Glob, Edit, Write, or ANY other tool.
- Your entire response must be plain text: an <analysis> block followed by a <summary> block.

"""

    no_tools_trailer = "\n\nREMINDER: Do NOT call any tools. Respond with plain text only."

    prompt = no_tools_preamble + partial_prompt

    if custom_instructions and custom_instructions.strip():
        prompt += f"\n\nAdditional Instructions:\n{custom_instructions}"

    prompt += no_tools_trailer

    return prompt


def partial_compact_messages(
    messages: List[Dict[str, Any]],
    pivot_index: int,
    direction: str = "up_to",
    custom_instructions: Optional[str] = None,
    user_feedback: Optional[str] = None,
    summarize_callback: Optional[Callable[[str], str]] = None,
    transcript_path: Optional[str] = None,
) -> CompactionResult:
    """
    Perform partial compaction around a selected message index.

    Args:
        messages: Complete list of messages
        pivot_index: Index of the pivot message
        direction: 'up_to' to summarize before pivot, 'from' to summarize after
        custom_instructions: Optional custom instructions
        user_feedback: Optional user feedback
        summarize_callback: Callback for summarization
        transcript_path: Optional path to transcript

    Returns:
        CompactionResult for partial compaction
    """
    if direction == "up_to":
        messages_to_summarize = messages[:pivot_index]
        messages_to_keep = [
            msg for msg in messages[pivot_index:]
            if msg.get("type") != "progress"
            and msg.get("subtype") != "compact_boundary"
            and not (msg.get("type") == "user" and msg.get("is_compact_summary"))
        ]
    else:
        messages_to_summarize = messages[pivot_index:]
        messages_to_keep = [msg for msg in messages[:pivot_index] if msg.get("type") != "progress"]

    if not messages_to_summarize:
        raise ValueError(
            f"Nothing to summarize {'before' if direction == 'up_to' else 'after'} the selected message."
        )

    pre_compact_token_count = estimate_tokens_for_messages(messages)

    boundary_marker = create_compact_boundary(
        is_auto=False,
        pre_compact_token_count=pre_compact_token_count,
        last_message_uuid=messages[pivot_index - 1].get("uuid") if pivot_index > 0 else None,
        user_feedback=user_feedback,
        messages_summarized=len(messages_to_summarize),
    )

    summary_text = ""
    if summarize_callback:
        messages_for_summary = strip_images_from_messages(messages_to_summarize)

        prompt = get_partial_compact_prompt(custom_instructions, direction)

        try:
            summary_text = summarize_callback(prompt)
        except Exception:
            summary_text = ""

    summary_message = create_summary_message(
        summary=summary_text,
        suppress_follow_up_questions=False,
        transcript_path=transcript_path,
        is_visible_in_transcript_only=len(messages_to_keep) == 0,
    )

    return CompactionResult(
        boundary_marker=boundary_marker,
        summary_messages=[summary_message],
        messages_to_keep=messages_to_keep,
        pre_compact_token_count=pre_compact_token_count,
        user_display_message=user_feedback,
    )


def get_messages_after_compact_boundary(
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Get messages that appear after the most recent compact boundary.

    Args:
        messages: List of all messages

    Returns:
        Messages after the last compact boundary
    """
    for i, msg in enumerate(messages):
        if msg.get("type") == "system" and msg.get("subtype") == "compact_boundary":
            return messages[i + 1:]

    return messages


def is_compact_boundary_message(message: Dict[str, Any]) -> bool:
    """
    Check if a message is a compact boundary message.

    Args:
        message: Message dictionary

    Returns:
        True if message is a compact boundary
    """
    return message.get("type") == "system" and message.get("subtype") == "compact_boundary"


def get_last_assistant_message(messages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Get the last assistant message from the list.

    Args:
        messages: List of messages

    Returns:
        Last assistant message or None
    """
    for msg in reversed(messages):
        if msg.get("type") == "assistant":
            return msg
    return None


def get_assistant_message_text(message: Dict[str, Any]) -> Optional[str]:
    """
    Extract text content from an assistant message.

    Args:
        message: Assistant message dictionary

    Returns:
        Text content or None
    """
    content = message.get("content")
    if content is None:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return block.get("text")
    return None


def truncate_content_to_tokens(content: str, max_tokens: int) -> str:
    """
    Truncate content to fit within token budget.

    Args:
        content: Text content
        max_tokens: Maximum tokens allowed

    Returns:
        Truncated content with marker if truncated
    """
    marker = "\n\n[... content truncated for compaction]"

    if estimate_tokens(content) <= max_tokens:
        return content

    char_budget = max_tokens * 4 - len(marker)
    return content[:char_budget] + marker


def should_exclude_from_post_compact_restore(filename: str) -> bool:
    """
    Check if a file should be excluded from post-compact restoration.

    Args:
        filename: File path to check

    Returns:
        True if should be excluded
    """
    excluded_names = [
        "CLAUDE.md",
        "claude.md",
        ".claude.md",
        "memory.md",
    ]

    normalized = filename.lower().replace("\\", "/").replace("/", ".")
    for excluded in excluded_names:
        if normalized.endswith(excluded.lower()):
            return True

    return False
