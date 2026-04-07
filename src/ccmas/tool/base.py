"""
Tool base classes and interfaces.

This module defines the abstract base class for tools and related types
for tool execution in the CCMAS system.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ccmas.types.tool import ToolDefinition, ToolOutput


class ToolCallArgs(BaseModel):
    """
    Tool call arguments.

    Represents the arguments passed when calling a tool.
    """

    tool_call_id: str = Field(..., description="The unique ID of this tool call")
    arguments: Dict[str, Any] = Field(
        default_factory=dict, description="The arguments to pass to the tool"
    )


class ToolExecutionResult(BaseModel):
    """
    Result of a tool execution.

    Contains the output and metadata about the execution.
    """

    tool_call_id: str = Field(..., description="The ID of the tool call")
    tool_name: str = Field(..., description="The name of the tool that was executed")
    output: ToolOutput = Field(..., description="The output from the tool")
    execution_time_ms: float = Field(
        default=0.0, description="Time taken to execute the tool in milliseconds"
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


class Tool(ABC):
    """
    Abstract base class for tools.

    All tools in the CCMAS system must inherit from this class and implement
    the required methods.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Get the name of the tool.

        Returns:
            The tool name
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Get the description of the tool.

        Returns:
            The tool description
        """
        pass

    @property
    def parameters(self) -> Dict[str, Any]:
        """
        Get the JSON Schema for the tool parameters.

        Returns:
            JSON Schema dict for parameters
        """
        return {"type": "object", "properties": {}, "required": []}

    def get_definition(self) -> ToolDefinition:
        """
        Get the tool definition.

        Returns:
            ToolDefinition instance
        """
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )

    @abstractmethod
    async def execute(self, args: ToolCallArgs) -> ToolExecutionResult:
        """
        Execute the tool with the given arguments.

        Args:
            args: The tool call arguments

        Returns:
            ToolExecutionResult containing the output and metadata
        """
        pass

    def _create_success_output(
        self,
        tool_call_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ToolOutput:
        """
        Create a successful tool output.

        Args:
            tool_call_id: The ID of the tool call
            content: The output content
            metadata: Optional metadata

        Returns:
            ToolOutput instance
        """
        return ToolOutput(
            tool_call_id=tool_call_id,
            content=content,
            is_error=False,
            status="success",
        )

    def _create_error_output(
        self,
        tool_call_id: str,
        error_message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ToolOutput:
        """
        Create an error tool output.

        Args:
            tool_call_id: The ID of the tool call
            error_message: The error message
            metadata: Optional metadata

        Returns:
            ToolOutput instance
        """
        return ToolOutput(
            tool_call_id=tool_call_id,
            content=error_message,
            is_error=True,
            status="error",
        )

    def _create_result(
        self,
        tool_call_id: str,
        output: ToolOutput,
        execution_time_ms: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ToolExecutionResult:
        """
        Create a tool execution result.

        Args:
            tool_call_id: The ID of the tool call
            output: The tool output
            execution_time_ms: Execution time in milliseconds
            metadata: Optional metadata

        Returns:
            ToolExecutionResult instance
        """
        return ToolExecutionResult(
            tool_call_id=tool_call_id,
            tool_name=self.name,
            output=output,
            execution_time_ms=execution_time_ms,
            metadata=metadata or {},
        )


def build_tool(tool_class: type[Tool]) -> Tool:
    """
    Build a tool instance from a tool class.

    Args:
        tool_class: The tool class to instantiate

    Returns:
        Tool instance
    """
    return tool_class()
