"""
SendMessage tool for inter-teammate communication.

This module provides the SendMessageTool which allows agents to send
messages to other teammates in a swarm. It integrates with the mailbox
system for reliable message delivery.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ccmas.tool.base import Tool, ToolCallArgs, ToolExecutionResult
from ccmas.types.tool import ToolOutput

from .mailbox import Message, MessageType, send_message

logger = logging.getLogger(__name__)


class SendMessageTool(Tool):
    """
    Tool for sending messages to teammates.

    This tool enables agents to communicate with other teammates in a swarm
    by sending messages through the mailbox system. It supports various
    message types including tasks, questions, and broadcasts.

    Example usage:
        ```python
        tool = SendMessageTool()
        result = await tool.execute(ToolCallArgs(
            tool_call_id="call_123",
            arguments={
                "recipient": "researcher@my-team",
                "message_type": "task",
                "content": "Research Python async patterns",
                "payload": {"priority": "high"}
            }
        ))
        ```

    Tool parameters:
        - recipient: Target teammate ID (e.g., "researcher@my-team")
        - message_type: Type of message (task, question, status, broadcast, custom)
        - content: Main message content/text
        - payload: Optional additional data (dict)
        - correlation_id: Optional ID for request/response correlation
        - priority: Message priority (0-10, higher = more urgent)
    """

    @property
    def name(self) -> str:
        """Get tool name."""
        return "send_message"

    @property
    def description(self) -> str:
        """Get tool description."""
        return (
            "Send a message to another teammate in the swarm. "
            "Use this to delegate tasks, ask questions, or broadcast information "
            "to team members. Messages are delivered asynchronously through the "
            "mailbox system."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        """Get JSON Schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "recipient": {
                    "type": "string",
                    "description": (
                        "The recipient teammate ID (e.g., 'researcher@my-team'). "
                        "Use 'broadcast' to send to all teammates."
                    ),
                },
                "message_type": {
                    "type": "string",
                    "enum": ["task", "question", "status", "broadcast", "custom"],
                    "description": "The type of message to send",
                },
                "content": {
                    "type": "string",
                    "description": "The main content of the message",
                },
                "payload": {
                    "type": "object",
                    "description": "Optional additional data to include with the message",
                },
                "correlation_id": {
                    "type": "string",
                    "description": "Optional correlation ID for request/response patterns",
                },
                "priority": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 10,
                    "default": 0,
                    "description": "Message priority (0-10, higher = more urgent)",
                },
            },
            "required": ["recipient", "message_type", "content"],
        }

    async def execute(self, args: ToolCallArgs) -> ToolExecutionResult:
        """
        Execute the send_message tool.

        Args:
            args: Tool call arguments containing:
                - recipient: Target teammate ID
                - message_type: Type of message
                - content: Message content
                - payload: Optional additional data
                - correlation_id: Optional correlation ID
                - priority: Message priority

        Returns:
            ToolExecutionResult indicating success or failure
        """
        start_time = logging.getLogger().manager.disable  # Use for timing
        import time

        start_time = time.time()

        try:
            # Extract arguments
            arguments = args.arguments
            recipient = arguments.get("recipient")
            message_type_str = arguments.get("message_type", "custom")
            content = arguments.get("content", "")
            payload = arguments.get("payload", {})
            correlation_id = arguments.get("correlation_id")
            priority = arguments.get("priority", 0)

            # Validate required arguments
            if not recipient:
                output = self._create_error_output(
                    args.tool_call_id,
                    "Missing required argument: 'recipient'",
                )
                return self._create_result(
                    args.tool_call_id,
                    output,
                    (time.time() - start_time) * 1000,
                )

            # Parse message type
            try:
                message_type = MessageType(message_type_str)
            except ValueError:
                valid_types = [t.value for t in MessageType]
                output = self._create_error_output(
                    args.tool_call_id,
                    f"Invalid message_type '{message_type_str}'. "
                    f"Valid types: {', '.join(valid_types)}",
                )
                return self._create_result(
                    args.tool_call_id,
                    output,
                    (time.time() - start_time) * 1000,
                )

            # Get sender from context (if available)
            from ccmas.context.agent_context import get_agent_context

            context = get_agent_context()
            sender = None
            if context:
                sender = context.agent_id

            # Build payload with content
            full_payload = {"content": content, **payload}

            # Create message
            message = Message(
                type=message_type,
                sender=sender,
                recipient=recipient if recipient != "broadcast" else None,
                payload=full_payload,
                correlation_id=correlation_id,
                priority=priority,
            )

            # Handle broadcast
            if recipient == "broadcast" or message_type == MessageType.BROADCAST:
                message.type = MessageType.BROADCAST
                # TODO: Implement broadcast to all teammates
                logger.info(f"Broadcasting message from {sender}")

            # Send message
            success = await send_message(message, recipient if recipient != "broadcast" else None)

            if success:
                output = self._create_success_output(
                    args.tool_call_id,
                    f"Message sent successfully to {recipient}",
                    metadata={
                        "message_id": message.id,
                        "recipient": recipient,
                        "message_type": message_type.value,
                    },
                )
            else:
                output = self._create_error_output(
                    args.tool_call_id,
                    f"Failed to send message to {recipient}. "
                    "Recipient mailbox may not exist or be full.",
                )

            execution_time_ms = (time.time() - start_time) * 1000
            return self._create_result(args.tool_call_id, output, execution_time_ms)

        except Exception as e:
            logger.error(f"Error in send_message tool: {e}")
            execution_time_ms = (time.time() - start_time) * 1000
            output = self._create_error_output(
                args.tool_call_id,
                f"Error sending message: {str(e)}",
            )
            return self._create_result(args.tool_call_id, output, execution_time_ms)

    def _create_success_output(
        self,
        tool_call_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ToolOutput:
        """Create a successful tool output."""
        return ToolOutput(
            tool_call_id=tool_call_id,
            content=content,
            is_error=False,
            status="success",
            metadata=metadata or {},
        )

    def _create_error_output(
        self,
        tool_call_id: str,
        error_message: str,
    ) -> ToolOutput:
        """Create an error tool output."""
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
        """Create a tool execution result."""
        return ToolExecutionResult(
            tool_call_id=tool_call_id,
            tool_name=self.name,
            output=output,
            execution_time_ms=execution_time_ms,
            metadata=metadata or {},
        )


class ReceiveMessageTool(Tool):
    """
    Tool for receiving messages from mailbox.

    This tool allows agents to check their mailbox for incoming messages
    from other teammates.

    Example usage:
        ```python
        tool = ReceiveMessageTool()
        result = await tool.execute(ToolCallArgs(
            tool_call_id="call_123",
            arguments={
                "timeout": 5.0,
                "message_type": "task"
            }
        ))
        ```

    Tool parameters:
        - timeout: Maximum time to wait for a message (seconds)
        - message_type: Filter by message type (optional)
    """

    @property
    def name(self) -> str:
        """Get tool name."""
        return "receive_message"

    @property
    def description(self) -> str:
        """Get tool description."""
        return (
            "Receive a message from your mailbox. "
            "Use this to check for incoming messages from other teammates. "
            "You can optionally filter by message type and specify a timeout."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        """Get JSON Schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "timeout": {
                    "type": "number",
                    "default": 0,
                    "description": (
                        "Maximum time to wait for a message in seconds. "
                        "Use 0 for non-blocking check."
                    ),
                },
                "message_type": {
                    "type": "string",
                    "enum": ["task", "question", "status", "broadcast", "custom"],
                    "description": "Optional filter by message type",
                },
            },
        }

    async def execute(self, args: ToolCallArgs) -> ToolExecutionResult:
        """
        Execute the receive_message tool.

        Args:
            args: Tool call arguments

        Returns:
            ToolExecutionResult with the received message or timeout
        """
        import time

        start_time = time.time()

        try:
            arguments = args.arguments
            timeout = arguments.get("timeout", 0)
            message_type_str = arguments.get("message_type")

            # Get agent ID from context
            from ccmas.context.agent_context import get_agent_context

            context = get_agent_context()
            if not context:
                output = self._create_error_output(
                    args.tool_call_id,
                    "No agent context found. Cannot receive messages.",
                )
                return self._create_result(
                    args.tool_call_id,
                    output,
                    (time.time() - start_time) * 1000,
                )

            agent_id = context.agent_id

            # Parse message type filter
            message_type = None
            if message_type_str:
                try:
                    message_type = MessageType(message_type_str)
                except ValueError:
                    valid_types = [t.value for t in MessageType]
                    output = self._create_error_output(
                        args.tool_call_id,
                        f"Invalid message_type '{message_type_str}'. "
                        f"Valid types: {', '.join(valid_types)}",
                    )
                    return self._create_result(
                        args.tool_call_id,
                        output,
                        (time.time() - start_time) * 1000,
                    )

            # Receive message
            from .mailbox import receive_message

            message = await receive_message(
                agent_id=agent_id,
                timeout=timeout if timeout > 0 else None,
                message_type=message_type,
            )

            if message:
                output = self._create_success_output(
                    args.tool_call_id,
                    f"Received {message.type.value} message from {message.sender}",
                    metadata={
                        "message": message.to_dict(),
                    },
                )
            else:
                output = self._create_success_output(
                    args.tool_call_id,
                    "No message received (timeout or empty mailbox)",
                    metadata={"timeout": timeout},
                )

            execution_time_ms = (time.time() - start_time) * 1000
            return self._create_result(args.tool_call_id, output, execution_time_ms)

        except Exception as e:
            logger.error(f"Error in receive_message tool: {e}")
            execution_time_ms = (time.time() - start_time) * 1000
            output = self._create_error_output(
                args.tool_call_id,
                f"Error receiving message: {str(e)}",
            )
            return self._create_result(args.tool_call_id, output, execution_time_ms)

    def _create_success_output(
        self,
        tool_call_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ToolOutput:
        """Create a successful tool output."""
        return ToolOutput(
            tool_call_id=tool_call_id,
            content=content,
            is_error=False,
            status="success",
            metadata=metadata or {},
        )

    def _create_error_output(
        self,
        tool_call_id: str,
        error_message: str,
    ) -> ToolOutput:
        """Create an error tool output."""
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
        """Create a tool execution result."""
        return ToolExecutionResult(
            tool_call_id=tool_call_id,
            tool_name=self.name,
            output=output,
            execution_time_ms=execution_time_ms,
            metadata=metadata or {},
        )
