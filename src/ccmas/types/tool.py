"""
Tool type definitions.

This module defines types for tool definitions, inputs, outputs, and results,
supporting both OpenAI function calling and Anthropic tool use formats.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


class ToolType(str, Enum):
    """Tool type enumeration."""

    FUNCTION = "function"


class ToolDefinition(BaseModel):
    """
    Tool definition.

    Defines a tool that can be called by the assistant.
    Compatible with both OpenAI and Anthropic tool formats.
    """

    name: str = Field(..., description="The name of the tool")
    description: Optional[str] = Field(
        default=None, description="A description of what the tool does"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}},
        description="JSON Schema for the tool parameters",
    )
    type: Literal["function"] = Field(
        default="function", description="The type of tool"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate tool name is not empty."""
        if not v or not v.strip():
            raise ValueError("Tool name cannot be empty")
        return v.strip()

    def to_openai_format(self) -> Dict[str, Any]:
        """
        Convert to OpenAI tool format.

        Returns:
            Dict in OpenAI tool format
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description or "",
                "parameters": self.parameters,
            },
        }

    def to_anthropic_format(self) -> Dict[str, Any]:
        """
        Convert to Anthropic tool format.

        Returns:
            Dict in Anthropic tool format
        """
        return {
            "name": self.name,
            "description": self.description or "",
            "input_schema": self.parameters,
        }


class ToolInput(BaseModel):
    """
    Tool input.

    Represents the input for a tool call.
    """

    tool_call_id: str = Field(..., description="The ID of the tool call")
    name: str = Field(..., description="The name of the tool to call")
    arguments: Dict[str, Any] = Field(
        default_factory=dict, description="The arguments to pass to the tool"
    )

    @field_validator("arguments", mode="before")
    @classmethod
    def parse_arguments(cls, v: Any) -> Dict[str, Any]:
        """Parse arguments if provided as a JSON string."""
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return v if isinstance(v, dict) else {}


class ToolOutput(BaseModel):
    """
    Tool output.

    Represents the output from a tool execution.
    """

    tool_call_id: str = Field(..., description="The ID of the tool call this output is for")
    content: Union[str, List[Dict[str, Any]]] = Field(
        ..., description="The output content from the tool"
    )
    is_error: bool = Field(
        default=False, description="Whether the tool execution resulted in an error"
    )
    status: Literal["success", "error"] = Field(
        default="success", description="The status of the tool execution"
    )

    def to_openai_format(self) -> Dict[str, Any]:
        """
        Convert to OpenAI tool message format.

        Returns:
            Dict in OpenAI tool message format
        """
        content_str = self.content if isinstance(self.content, str) else str(self.content)
        return {
            "role": "tool",
            "tool_call_id": self.tool_call_id,
            "content": content_str,
        }

    def to_anthropic_format(self) -> Dict[str, Any]:
        """
        Convert to Anthropic tool result format.

        Returns:
            Dict in Anthropic tool result format
        """
        return {
            "type": "tool_result",
            "tool_use_id": self.tool_call_id,
            "content": self.content,
            "is_error": self.is_error,
        }


class ToolResult(BaseModel):
    """
    Tool result.

    Represents the complete result of a tool execution,
    including metadata about the execution.
    """

    tool_call_id: str = Field(..., description="The ID of the tool call")
    tool_name: str = Field(..., description="The name of the tool that was executed")
    output: ToolOutput = Field(..., description="The output from the tool")
    execution_time_ms: Optional[float] = Field(
        default=None, description="Time taken to execute the tool in milliseconds"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata about the execution"
    )

    @property
    def is_success(self) -> bool:
        """Check if the tool execution was successful."""
        return not self.output.is_error

    @property
    def is_error(self) -> bool:
        """Check if the tool execution resulted in an error."""
        return self.output.is_error


class ToolPermission(BaseModel):
    """
    Tool permission configuration.

    Defines permissions for tool usage.
    """

    allow: bool = Field(default=True, description="Whether to allow the tool")
    ask: bool = Field(default=False, description="Whether to ask for permission before using")
    deny: bool = Field(default=False, description="Whether to deny the tool")
    reason: Optional[str] = Field(
        default=None, description="Reason for the permission decision"
    )


class ToolRegistry(BaseModel):
    """
    Tool registry for managing available tools.

    Provides a central place to register and retrieve tool definitions.
    """

    tools: Dict[str, ToolDefinition] = Field(
        default_factory=dict, description="Registered tools by name"
    )
    permissions: Dict[str, ToolPermission] = Field(
        default_factory=dict, description="Tool permissions by name"
    )

    def register(self, tool: ToolDefinition) -> None:
        """
        Register a tool.

        Args:
            tool: The tool definition to register
        """
        self.tools[tool.name] = tool

    def unregister(self, name: str) -> Optional[ToolDefinition]:
        """
        Unregister a tool.

        Args:
            name: The name of the tool to unregister

        Returns:
            The unregistered tool, or None if not found
        """
        return self.tools.pop(name, None)

    def get(self, name: str) -> Optional[ToolDefinition]:
        """
        Get a tool by name.

        Args:
            name: The name of the tool

        Returns:
            The tool definition, or None if not found
        """
        return self.tools.get(name)

    def get_all(self) -> List[ToolDefinition]:
        """
        Get all registered tools.

        Returns:
            List of all tool definitions
        """
        return list(self.tools.values())

    def to_openai_tools(self) -> List[Dict[str, Any]]:
        """
        Convert all tools to OpenAI format.

        Returns:
            List of tools in OpenAI format
        """
        return [tool.to_openai_format() for tool in self.tools.values()]

    def to_anthropic_tools(self) -> List[Dict[str, Any]]:
        """
        Convert all tools to Anthropic format.

        Returns:
            List of tools in Anthropic format
        """
        return [tool.to_anthropic_format() for tool in self.tools.values()]

    def set_permission(self, name: str, permission: ToolPermission) -> None:
        """
        Set permission for a tool.

        Args:
            name: The name of the tool
            permission: The permission to set
        """
        self.permissions[name] = permission

    def get_permission(self, name: str) -> ToolPermission:
        """
        Get permission for a tool.

        Args:
            name: The name of the tool

        Returns:
            The permission for the tool (defaults to allow if not set)
        """
        return self.permissions.get(name, ToolPermission())

    def is_allowed(self, name: str) -> bool:
        """
        Check if a tool is allowed.

        Args:
            name: The name of the tool

        Returns:
            True if the tool is allowed, False otherwise
        """
        permission = self.get_permission(name)
        return permission.allow and not permission.deny


def create_tool_definition(
    name: str,
    description: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
) -> ToolDefinition:
    """
    Create a tool definition.

    Args:
        name: The name of the tool
        description: A description of what the tool does
        parameters: JSON Schema for the tool parameters

    Returns:
        ToolDefinition instance
    """
    return ToolDefinition(
        name=name,
        description=description,
        parameters=parameters or {"type": "object", "properties": {}},
    )


def create_tool_input(
    tool_call_id: str,
    name: str,
    arguments: Optional[Dict[str, Any]] = None,
) -> ToolInput:
    """
    Create a tool input.

    Args:
        tool_call_id: The ID of the tool call
        name: The name of the tool
        arguments: The arguments to pass to the tool

    Returns:
        ToolInput instance
    """
    return ToolInput(
        tool_call_id=tool_call_id,
        name=name,
        arguments=arguments or {},
    )


def create_tool_output(
    tool_call_id: str,
    content: Union[str, List[Dict[str, Any]]],
    is_error: bool = False,
) -> ToolOutput:
    """
    Create a tool output.

    Args:
        tool_call_id: The ID of the tool call
        content: The output content
        is_error: Whether the execution resulted in an error

    Returns:
        ToolOutput instance
    """
    return ToolOutput(
        tool_call_id=tool_call_id,
        content=content,
        is_error=is_error,
    )


def create_tool_result(
    tool_call_id: str,
    tool_name: str,
    output: ToolOutput,
    execution_time_ms: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> ToolResult:
    """
    Create a tool result.

    Args:
        tool_call_id: The ID of the tool call
        tool_name: The name of the tool
        output: The output from the tool
        execution_time_ms: Time taken to execute
        metadata: Additional metadata

    Returns:
        ToolResult instance
    """
    return ToolResult(
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        output=output,
        execution_time_ms=execution_time_ms,
        metadata=metadata or {},
    )
