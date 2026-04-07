"""Conversation summarizer for CCMAS."""

import re
from dataclasses import dataclass
from typing import Optional, Callable


POST_COMPACT_MAX_FILES_TO_RESTORE = 5
POST_COMPACT_TOKEN_BUDGET = 50_000
POST_COMPACT_MAX_TOKENS_PER_FILE = 5_000
POST_COMPACT_MAX_TOKENS_PER_SKILL = 5_000
POST_COMPACT_SKILLS_TOKEN_BUDGET = 25_000


ERROR_MESSAGE_NOT_ENOUGH_MESSAGES = "Not enough messages to compact."
ERROR_MESSAGE_PROMPT_TOO_LONG = "Conversation too long."
ERROR_MESSAGE_USER_ABORT = "API Error: Request was aborted."
ERROR_MESSAGE_INCOMPLETE_RESPONSE = "Compaction interrupted."


@dataclass
class CompactionResult:
    boundary_marker: dict
    summary_messages: list[dict]
    attachments: list[dict]
    hook_results: list[dict]
    messages_to_keep: Optional[list[dict]] = None
    user_display_message: Optional[str] = None
    pre_compact_token_count: Optional[int] = None
    post_compact_token_count: Optional[int] = None
    true_post_compact_token_count: Optional[int] = None
    compaction_usage: Optional[dict] = None


def format_compact_summary(summary: str) -> str:
    formatted = summary

    formatted = re.sub(r'<analysis>[\s\S]*?</analysis>', '', formatted)

    summary_match = re.search(r'<summary>([\s\S]*?)</summary>', formatted)
    if summary_match:
        content = summary_match.group(1) or ''
        formatted = re.sub(
            r'<summary>[\s\S]*?</summary>',
            f"Summary:\n{content.strip()}",
            formatted
        )

    formatted = re.sub(r'\n\n+', '\n\n', formatted)

    return formatted.strip()


def get_compact_user_summary_message(
    summary: str,
    suppress_follow_up_questions: bool = False,
    transcript_path: Optional[str] = None,
    recent_messages_preserved: bool = False,
) -> str:
    formatted_summary = format_compact_summary(summary)

    base_summary = f"""This session is being continued from a previous conversation that ran out of context. The summary below covers the earlier portion of the conversation.

{formatted_summary}"""

    if transcript_path:
        base_summary += f"\n\nIf you need specific details from before compaction (like exact code snippets, error messages, or content you generated), read the full transcript at: {transcript_path}"

    if recent_messages_preserved:
        base_summary += "\n\nRecent messages are preserved verbatim."

    if suppress_follow_up_questions:
        continuation = f"""{base_summary}
Continue the conversation from where it left off without asking the user any further questions. Resume directly — do not acknowledge the summary, do not recap what was happening, do not preface with "I'll continue" or similar. Pick up the last task as if the break never happened."""
        return continuation

    return base_summary


def strip_images_from_messages(messages: list[dict]) -> list[dict]:
    result = []
    for message in messages:
        if message.get('type') != 'user':
            result.append(message)
            continue

        content = message.get('message', {}).get('content')
        if not isinstance(content, list):
            result.append(message)
            continue

        has_media = False
        new_content = []
        for block in content:
            if block.get('type') == 'image':
                has_media = True
                new_content.append({'type': 'text', 'text': '[image]'})
            elif block.get('type') == 'document':
                has_media = True
                new_content.append({'type': 'text', 'text': '[document]'})
            elif block.get('type') == 'tool_result' and isinstance(block.get('content'), list):
                tool_content = block.get('content', [])
                new_tool_content = []
                tool_has_media = False
                for item in tool_content:
                    if item.get('type') == 'image':
                        tool_has_media = True
                        new_tool_content.append({'type': 'text', 'text': '[image]'})
                    elif item.get('type') == 'document':
                        tool_has_media = True
                        new_tool_content.append({'type': 'text', 'text': '[document]'})
                    else:
                        new_tool_content.append(item)
                if tool_has_media:
                    has_media = True
                    new_content.append({**block, 'content': new_tool_content})
                else:
                    new_content.append(block)
            else:
                new_content.append(block)

        if not has_media:
            result.append(message)
        else:
            result.append({
                **message,
                'message': {
                    **message.get('message', {}),
                    'content': new_content,
                }
            })

    return result


def rough_token_count_estimation(text: str) -> int:
    return len(text) // 4


def rough_token_count_for_messages(messages: list[dict]) -> int:
    total = 0
    for msg in messages:
        content = msg.get('message', {}).get('content', '')
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get('type') == 'text':
                        total += rough_token_count_estimation(block.get('text', ''))
                    elif block.get('type') == 'tool_use':
                        total += rough_token_count_estimation(str(block.get('input', {})))
        elif isinstance(content, str):
            total += rough_token_count_estimation(content)
    return total


class CompactPrompt:
    NO_TOOLS_PREAMBLE = """CRITICAL: Respond with TEXT ONLY. Do NOT call any tools.

- Do NOT use Read, Bash, Grep, Glob, Edit, Write, or ANY other tool.
- You already have all the context you need in the conversation above.
- Tool calls will be REJECTED and will waste your only turn — you will fail the task.
- Your entire response must be plain text: an <analysis> block followed by a <summary> block.

"""

    BASE_COMPACT_PROMPT = """Your task is to create a detailed summary of the conversation so far, paying close attention to the user's explicit requests and your previous actions.
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

    NO_TOOLS_TRAILER = "\n\nREMINDER: Do NOT call any tools. Respond with plain text only."

    @classmethod
    def get_compact_prompt(cls, custom_instructions: Optional[str] = None) -> str:
        prompt = cls.NO_TOOLS_PREAMBLE + cls.BASE_COMPACT_PROMPT

        if custom_instructions and custom_instructions.strip():
            prompt += f"\n\nAdditional Instructions:\n{custom_instructions}"

        prompt += cls.NO_TOOLS_TRAILER

        return prompt

    @classmethod
    def get_partial_compact_prompt(cls, custom_instructions: Optional[str] = None, direction: str = 'from') -> str:
        partial_prompt = """Your task is to create a detailed summary of the RECENT portion of the conversation — the messages that follow earlier retained context.

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
        prompt = cls.NO_TOOLS_PREAMBLE + partial_prompt

        if custom_instructions and custom_instructions.strip():
            prompt += f"\n\nAdditional Instructions:\n{custom_instructions}"

        prompt += cls.NO_TOOLS_TRAILER

        return prompt


def summarize_messages(
    messages: list[dict],
    custom_instructions: Optional[str] = None,
    api_callback: Optional[Callable[[str], str]] = None,
) -> str:
    if api_callback is None:
        return ""

    prompt = CompactPrompt.get_compact_prompt(custom_instructions)
    summary_text = api_callback(prompt)

    return format_compact_summary(summary_text)


def create_compact_boundary_message(
    is_auto: bool = False,
    pre_compact_token_count: int = 0,
    last_uuid: Optional[str] = None,
) -> dict:
    return {
        'type': 'system',
        'subtype': 'compact_boundary',
        'is_auto': is_auto,
        'pre_compact_token_count': pre_compact_token_count,
        'last_message_uuid': last_uuid,
    }
