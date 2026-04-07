"""
Message types for OpenAI API format.

This module defines message types compatible with OpenAI's chat completion API,
supporting user, assistant, and tool messages with proper validation.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class MessageRole(str, Enum):
    """Message role enumeration."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ContentBlockType(str, Enum):
    """Content block type enumeration."""

    TEXT = "text"
    IMAGE_URL = "image_url"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"


class TextContentBlock(BaseModel):
    """Text content block."""

    type: Literal["text"] = "text"
    text: str


class ImageURLContentBlock(BaseModel):
    """Image URL content block."""

    type: Literal["image_url"] = "image_url"
    image_url: Dict[str, str]


class ToolCall(BaseModel):
    """
    Tool call definition.

    Represents a tool/function call made by the assistant.
    """

    id: str = Field(default_factory=lambda: f"call_{uuid4().hex[:24]}")
    type: Literal["function"] = "function"
    function: Dict[str, Any] = Field(
        default_factory=lambda: {"name": "", "arguments": "{}"}
    )

    @field_validator("function")
    @classmethod
    def validate_function(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate function has required fields."""
        if "name" not in v:
            raise ValueError("function must have 'name' field")
        return v


class ToolUseContentBlock(BaseModel):
    """Tool use content block (for assistant messages)."""

    type: Literal["tool_use"] = "tool_use"
    id: str = Field(default_factory=lambda: f"toolu_{uuid4().hex[:24]}")
    name: str
    input: Dict[str, Any] = Field(default_factory=dict)


class ToolResultContentBlock(BaseModel):
    """Tool result content block (for tool messages)."""

    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: Union[str, List[Dict[str, Any]]]
    is_error: bool = False


# Union type for all content blocks
ContentBlock = Union[
    TextContentBlock,
    ImageURLContentBlock,
    ToolUseContentBlock,
    ToolResultContentBlock,
]


class BaseMessage(BaseModel):
    """
    Base message class.

    All message types inherit from this base class.
    """

    uuid: UUID = Field(default_factory=uuid4)
    timestamp: str = Field(default_factory=lambda: __import__("datetime").datetime.now().isoformat())

    class Config:
        """Pydantic config."""

        use_enum_values = True


class UserMessage(BaseMessage):
    """
    User message.

    Represents a message from the user to the assistant.
    """

    type: Literal["user"] = "user"
    role: Literal["user"] = "user"
    content: Union[str, List[ContentBlock]]
    name: Optional[str] = None
    is_meta: bool = False
    is_visible_in_transcript_only: bool = False
    is_virtual: bool = False
    is_compact_summary: Optional[bool] = None
    tool_use_result: Optional[Any] = None
    permission_mode: Optional[str] = None

    def to_openai_format(self) -> Dict[str, Any]:
        """
        Convert to OpenAI API format.

        Returns:
            Dict in OpenAI message format
        """
        result: Dict[str, Any] = {
            "role": "user",
            "content": self.content,
        }
        if self.name:
            result["name"] = self.name
        return result


class AssistantMessage(BaseMessage):
    """
    Assistant message.

    Represents a message from the assistant.
    """

    type: Literal["assistant"] = "assistant"
    role: Literal["assistant"] = "assistant"
    content: Optional[Union[str, List[ContentBlock]]] = None
    name: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    request_id: Optional[str] = None
    stop_reason: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None

    def to_openai_format(self) -> Dict[str, Any]:
        """
        Convert to OpenAI API format.

        Returns:
            Dict in OpenAI message format
        """
        result: Dict[str, Any] = {
            "role": "assistant",
        }
        if self.content:
            result["content"] = self.content
        if self.name:
            result["name"] = self.name
        if self.tool_calls:
            result["tool_calls"] = [tc.model_dump() for tc in self.tool_calls]
        return result


class ToolMessage(BaseMessage):
    """
    Tool message.

    Represents a tool result message.
    """

    type: Literal["tool"] = "tool"
    role: Literal["tool"] = "tool"
    tool_call_id: str
    content: Union[str, List[ContentBlock]]
    name: Optional[str] = None

    def to_openai_format(self) -> Dict[str, Any]:
        """
        Convert to OpenAI API format.

        Returns:
            Dict in OpenAI message format
        """
        result: Dict[str, Any] = {
            "role": "tool",
            "tool_call_id": self.tool_call_id,
            "content": self.content,
        }
        if self.name:
            result["name"] = self.name
        return result


class SystemMessage(BaseMessage):
    """
    System message.

    Represents a system-level message.
    """

    type: Literal["system"] = "system"
    role: Literal["system"] = "system"
    content: str
    subtype: Optional[str] = None
    compact_metadata: Optional[Dict[str, Any]] = None

    def to_openai_format(self) -> Dict[str, Any]:
        """
        Convert to OpenAI API format.

        Returns:
            Dict in OpenAI message format
        """
        result: Dict[str, Any] = {
            "role": "system",
            "content": self.content,
        }
        if self.subtype:
            result["subtype"] = self.subtype
        if self.compact_metadata:
            result["compact_metadata"] = self.compact_metadata
        return result


# Union type for all messages
Message = Union[UserMessage, AssistantMessage, ToolMessage, SystemMessage]


class MessageConverter:
    """
    Message converter for OpenAI API format.

    Provides utilities to convert messages to OpenAI-compatible format.
    """

    @staticmethod
    def to_openai_messages(messages: List[Message]) -> List[Dict[str, Any]]:
        """
        Convert a list of messages to OpenAI API format.

        Args:
            messages: List of messages to convert

        Returns:
            List of messages in OpenAI format
        """
        result = []
        for msg in messages:
            if isinstance(msg, (UserMessage, AssistantMessage, ToolMessage, SystemMessage)):
                result.append(msg.to_openai_format())
            else:
                raise ValueError(f"Unknown message type: {type(msg)}")
        return result

    @staticmethod
    def from_openai_format(data: Dict[str, Any]) -> Message:
        """
        Create a message from OpenAI API format.

        Args:
            data: Message data in OpenAI format

        Returns:
            Appropriate message instance
        """
        role = data.get("role")

        if role == "user":
            return UserMessage(
                content=data.get("content", ""),
                name=data.get("name"),
            )
        elif role == "assistant":
            tool_calls = None
            if "tool_calls" in data:
                tool_calls = [ToolCall(**tc) for tc in data["tool_calls"]]
            return AssistantMessage(
                content=data.get("content"),
                name=data.get("name"),
                tool_calls=tool_calls,
            )
        elif role == "tool":
            return ToolMessage(
                tool_call_id=data.get("tool_call_id", ""),
                content=data.get("content", ""),
                name=data.get("name"),
            )
        elif role == "system":
            return SystemMessage(
                content=data.get("content", ""),
            )
        else:
            raise ValueError(f"Unknown role: {role}")


def create_user_message(
    content: Union[str, List[ContentBlock]],
    name: Optional[str] = None,
    is_meta: bool = False,
) -> UserMessage:
    """
    Create a user message.

    Args:
        content: Message content
        name: Optional name for the user
        is_meta: Whether this is a meta message

    Returns:
        UserMessage instance
    """
    return UserMessage(
        content=content,
        name=name,
        is_meta=is_meta,
    )


def create_assistant_message(
    content: Optional[Union[str, List[ContentBlock]]] = None,
    tool_calls: Optional[List[ToolCall]] = None,
    name: Optional[str] = None,
) -> AssistantMessage:
    """
    Create an assistant message.

    Args:
        content: Message content
        tool_calls: Optional tool calls
        name: Optional name for the assistant

    Returns:
        AssistantMessage instance
    """
    return AssistantMessage(
        content=content,
        tool_calls=tool_calls,
        name=name,
    )


def create_tool_message(
    tool_call_id: str,
    content: Union[str, List[ContentBlock]],
    name: Optional[str] = None,
) -> ToolMessage:
    """
    Create a tool message.

    Args:
        tool_call_id: ID of the tool call this is responding to
        content: Tool result content
        name: Optional tool name

    Returns:
        ToolMessage instance
    """
    return ToolMessage(
        tool_call_id=tool_call_id,
        content=content,
        name=name,
    )
