"""
Permission bubble mechanism.

This module implements the permission bubbling system that allows
permission requests to escalate from subagents to parent agents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from pydantic import BaseModel, Field

from ccmas.permission.mode import (
    PermissionAction,
    PermissionContext,
    PermissionMode,
    PermissionResult,
)

if TYPE_CHECKING:
    from ccmas.types.agent import AgentContext


@dataclass
class BubbleRequest:
    """
    Permission bubble request.

    Represents a permission request that needs to bubble up to a parent agent.
    """

    request_id: str
    tool_name: Optional[str] = None
    file_path: Optional[str] = None
    operation: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    source_agent_id: Optional[str] = None
    target_agent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BubbleResponse:
    """
    Permission bubble response.

    Represents the response from a parent agent for a bubbled permission request.
    """

    request_id: str
    result: PermissionResult
    responded_by: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BubblePermissionHandler:
    """
    Handler for permission bubbling.

    Manages the bubbling of permission requests from subagents to parent agents,
    maintaining a queue of pending requests and tracking responses.
    """

    def __init__(
        self,
        agent_context: Optional["AgentContext"] = None,
        on_bubble: Optional[Callable[[BubbleRequest], BubbleResponse]] = None,
    ):
        """
        Initialize the bubble permission handler.

        Args:
            agent_context: The agent context for determining parent relationships
            on_bubble: Callback function for handling bubble requests
        """
        self.agent_context = agent_context
        self.on_bubble = on_bubble
        self._pending_requests: Dict[str, BubbleRequest] = {}
        self._responses: Dict[str, BubbleResponse] = {}
        self._request_counter = 0

    def can_bubble(self) -> bool:
        """
        Check if permission bubbling is possible.

        Returns:
            True if there is a parent agent to bubble to
        """
        if self.agent_context is None:
            return False

        # Check if we have a parent session ID
        if hasattr(self.agent_context, 'parent_session_id'):
            return self.agent_context.parent_session_id is not None

        return False

    def create_bubble_request(
        self,
        tool_name: Optional[str] = None,
        file_path: Optional[str] = None,
        operation: Optional[str] = None,
        arguments: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BubbleRequest:
        """
        Create a new bubble request.

        Args:
            tool_name: Name of the tool requiring permission
            file_path: Path of the file requiring permission
            operation: Operation type
            arguments: Tool arguments
            reason: Reason for the permission request
            metadata: Additional metadata

        Returns:
            BubbleRequest instance
        """
        self._request_counter += 1
        request_id = f"bubble_{self._request_counter}"

        request = BubbleRequest(
            request_id=request_id,
            tool_name=tool_name,
            file_path=file_path,
            operation=operation,
            arguments=arguments,
            reason=reason,
            source_agent_id=getattr(self.agent_context, 'agent_id', None),
            target_agent_id=None,  # Will be set by the parent
            metadata=metadata or {},
        )

        self._pending_requests[request_id] = request
        return request

    def send_bubble_request(self, request: BubbleRequest) -> PermissionResult:
        """
        Send a bubble request to the parent agent.

        Args:
            request: The bubble request to send

        Returns:
            PermissionResult from the parent agent
        """
        if not self.can_bubble():
            return PermissionResult.deny(
                reason="Cannot bubble: no parent agent available",
                mode=PermissionMode.BUBBLE,
            )

        if self.on_bubble is None:
            return PermissionResult.deny(
                reason="Cannot bubble: no bubble handler configured",
                mode=PermissionMode.BUBBLE,
            )

        try:
            response = self.on_bubble(request)
            self._responses[request.request_id] = response
            return response.result
        except Exception as e:
            return PermissionResult.deny(
                reason=f"Bubble request failed: {str(e)}",
                mode=PermissionMode.BUBBLE,
                metadata={"error": str(e)},
            )

    def handle_bubble_response(self, response: BubbleResponse) -> None:
        """
        Handle a response to a bubble request.

        Args:
            response: The bubble response
        """
        self._responses[response.request_id] = response

        # Remove from pending if present
        if response.request_id in self._pending_requests:
            del self._pending_requests[response.request_id]

    def get_pending_requests(self) -> List[BubbleRequest]:
        """
        Get all pending bubble requests.

        Returns:
            List of pending BubbleRequest instances
        """
        return list(self._pending_requests.values())

    def get_response(self, request_id: str) -> Optional[BubbleResponse]:
        """
        Get the response for a specific request.

        Args:
            request_id: The request ID to look up

        Returns:
            BubbleResponse if available, None otherwise
        """
        return self._responses.get(request_id)

    def clear_pending(self) -> None:
        """Clear all pending requests."""
        self._pending_requests.clear()


def bubble_permission(
    context: PermissionContext,
    tool_name: Optional[str] = None,
    file_path: Optional[str] = None,
    operation: Optional[str] = None,
    arguments: Optional[Dict[str, Any]] = None,
    reason: Optional[str] = None,
    handler: Optional[BubblePermissionHandler] = None,
) -> PermissionResult:
    """
    Bubble a permission request to a parent agent.

    This function creates a bubble request and sends it to the parent agent
    for handling. If no handler is provided or bubbling is not possible,
    it returns a denial result.

    Args:
        context: The permission context
        tool_name: Name of the tool requiring permission
        file_path: Path of the file requiring permission
        operation: Operation type
        arguments: Tool arguments
        reason: Reason for the permission request
        handler: Optional bubble handler to use

    Returns:
        PermissionResult from the parent agent or denial if not possible
    """
    # Check if bubbling is appropriate
    if context.mode != PermissionMode.BUBBLE:
        return PermissionResult.deny(
            reason=f"Bubble mode not active (current: {context.mode.value})",
            mode=context.mode,
        )

    # Use provided handler or create a default one
    bubble_handler = handler or BubblePermissionHandler()

    # Check if bubbling is possible
    if not bubble_handler.can_bubble():
        return PermissionResult.deny(
            reason="Cannot bubble permission request: no parent agent",
            mode=context.mode,
        )

    # Create and send the bubble request
    request = bubble_handler.create_bubble_request(
        tool_name=tool_name,
        file_path=file_path,
        operation=operation,
        arguments=arguments,
        reason=reason,
    )

    return bubble_handler.send_bubble_request(request)


class PermissionBubbleQueue:
    """
    Queue for managing permission bubble requests.

    Maintains a queue of pending bubble requests and provides
    methods for processing them in order.
    """

    def __init__(self, max_size: int = 100):
        """
        Initialize the bubble queue.

        Args:
            max_size: Maximum number of pending requests
        """
        self.max_size = max_size
        self._queue: List[BubbleRequest] = []
        self._handlers: Dict[str, Callable[[BubbleRequest], BubbleResponse]] = {}

    def enqueue(self, request: BubbleRequest) -> bool:
        """
        Add a request to the queue.

        Args:
            request: The bubble request to add

        Returns:
            True if added successfully, False if queue is full
        """
        if len(self._queue) >= self.max_size:
            return False
        self._queue.append(request)
        return True

    def dequeue(self) -> Optional[BubbleRequest]:
        """
        Remove and return the next request from the queue.

        Returns:
            The next BubbleRequest or None if queue is empty
        """
        if not self._queue:
            return None
        return self._queue.pop(0)

    def peek(self) -> Optional[BubbleRequest]:
        """
        Get the next request without removing it.

        Returns:
            The next BubbleRequest or None if queue is empty
        """
        return self._queue[0] if self._queue else None

    def register_handler(
        self,
        request_type: str,
        handler: Callable[[BubbleRequest], BubbleResponse],
    ) -> None:
        """
        Register a handler for a specific request type.

        Args:
            request_type: Type of request (e.g., 'tool', 'file')
            handler: Handler function
        """
        self._handlers[request_type] = handler

    def process_next(self) -> Optional[BubbleResponse]:
        """
        Process the next request in the queue.

        Returns:
            BubbleResponse if processed, None if queue is empty
        """
        request = self.dequeue()
        if request is None:
            return None

        # Determine request type
        request_type = "tool" if request.tool_name else "file"

        # Get appropriate handler
        handler = self._handlers.get(request_type)
        if handler is None:
            # Default denial if no handler
            return BubbleResponse(
                request_id=request.request_id,
                result=PermissionResult.deny(
                    reason=f"No handler for request type: {request_type}",
                    mode=PermissionMode.BUBBLE,
                ),
            )

        return handler(request)

    def process_all(self) -> List[BubbleResponse]:
        """
        Process all requests in the queue.

        Returns:
            List of BubbleResponse instances
        """
        responses = []
        while self._queue:
            response = self.process_next()
            if response:
                responses.append(response)
        return responses

    def clear(self) -> None:
        """Clear the queue."""
        self._queue.clear()

    def __len__(self) -> int:
        """Get the number of pending requests."""
        return len(self._queue)

    def is_empty(self) -> bool:
        """Check if the queue is empty."""
        return len(self._queue) == 0

    def is_full(self) -> bool:
        """Check if the queue is full."""
        return len(self._queue) >= self.max_size


def create_bubble_handler(
    agent_context: Optional["AgentContext"] = None,
    on_bubble: Optional[Callable[[BubbleRequest], BubbleResponse]] = None,
) -> BubblePermissionHandler:
    """
    Create a bubble permission handler.

    Args:
        agent_context: The agent context
        on_bubble: Callback for handling bubble requests

    Returns:
        Configured BubblePermissionHandler instance
    """
    return BubblePermissionHandler(
        agent_context=agent_context,
        on_bubble=on_bubble,
    )
