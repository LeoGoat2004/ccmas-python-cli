"""
Context summarizer for compressing message history.

This module provides context summarization functionality to reduce the number
of messages sent to the LLM while preserving important context.
"""

from typing import List, Tuple

from ..types.message import Message
from .types import SessionSummary


DEFAULT_SUMMARY_PROMPT = """请对以下对话进行简洁的摘要。摘要应该：
1. 保留对话的主要话题和目标
2. 记住已完成的重要操作和结果
3. 记录遇到的关键问题及解决方案
4. 保留任何重要的用户偏好或要求

请用简洁的语言生成摘要，以便后续对话可以基于此摘要继续。"""


class ContextSummarizer:
    """
    Summarizer for compressing message history.

    This class handles context compression by:
    1. Determining when summarization is needed based on message count
    2. Generating concise summaries of older messages
    3. Returning compressed message list with summary replacing older messages
    """

    def __init__(self, max_messages: int = 50, summary_prompt: str = DEFAULT_SUMMARY_PROMPT):
        """
        Initialize the context summarizer.

        Args:
            max_messages: Maximum number of messages before summarization is triggered.
                          Default is 50.
            summary_prompt: Prompt template used for generating summaries.
                           Should guide the summarizer to preserve important context.
        """
        self.max_messages = max_messages
        self.summary_prompt = summary_prompt

    def should_summarize(self, messages: List[Message]) -> bool:
        """
        Determine if messages should be summarized.

        Summarization is triggered when the total number of messages exceeds
        the configured maximum threshold.

        Args:
            messages: List of messages to check.

        Returns:
            True if messages should be summarized, False otherwise.
        """
        return len(messages) > self.max_messages

    def summarize_messages(self, messages: List[Message]) -> Tuple[str, List[Message]]:
        """
        Summarize older messages and return compressed message list.

        This method:
        1. Preserves the most recent messages (last few)
        2. Combines earlier messages into a summary
        3. Returns the summary text and the compressed message list

        Args:
            messages: List of messages to summarize.

        Returns:
            A tuple containing:
            - summary_text: The generated summary of older messages
            - compressed_messages: Messages with older ones replaced by summary
        """
        if len(messages) <= self.max_messages:
            return "", messages

        # Calculate how many recent messages to preserve
        # We preserve the last (max_messages // 2) messages to keep recent context
        preserve_count = self.max_messages // 2
        recent_messages = messages[-preserve_count:]
        older_messages = messages[:-preserve_count]

        # Generate summary of older messages
        summary_text = self.generate_summary(older_messages)

        # Create summary message - mark it as a compact summary
        from ..types.message import UserMessage

        summary_message = UserMessage(
            content=summary_text,
            is_compact_summary=True,
            is_meta=True,
        )

        # Combine summary with recent messages
        compressed_messages = [summary_message] + recent_messages

        return summary_text, compressed_messages

    def generate_summary(self, messages: List[Message]) -> str:
        """
        Generate a summary text from a list of messages.

        This method formats messages into a text representation suitable
        for summarization by an LLM.

        Args:
            messages: List of messages to summarize.

        Returns:
            A text summary of the messages.
        """
        if not messages:
            return "（无历史消息）"

        from ..types.message import UserMessage, AssistantMessage, ToolMessage, SystemMessage

        formatted_parts = []

        for msg in messages:
            if isinstance(msg, SystemMessage):
                role = "系统"
                content = msg.content
            elif isinstance(msg, UserMessage):
                role = "用户"
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
            elif isinstance(msg, AssistantMessage):
                role = "助手"
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
            elif isinstance(msg, ToolMessage):
                role = f"工具({msg.name or 'unknown'})"
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
            else:
                role = "未知"
                content = str(msg)

            formatted_parts.append(f"{role}: {content}")

        return "\n".join(formatted_parts)
