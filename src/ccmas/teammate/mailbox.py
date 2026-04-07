"""
Message mailbox system for inter-teammate communication.

This module provides a mailbox system that enables asynchronous message
passing between teammates in a swarm. Each teammate has its own mailbox
for receiving messages, and can send messages to other teammates by
addressing them by their agent ID.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, TypeVar
from uuid import UUID, uuid4

T = TypeVar("T")


class MessageType(str, Enum):
    """Message type enumeration."""

    # Task assignment from team lead
    TASK = "task"
    # Task completion notification
    TASK_COMPLETE = "task_complete"
    # Status update
    STATUS = "status"
    # Question to another teammate
    QUESTION = "question"
    # Answer to a question
    ANSWER = "answer"
    # Broadcast to all teammates
    BROADCAST = "broadcast"
    # System message
    SYSTEM = "system"
    # Custom message
    CUSTOM = "custom"


@dataclass
class Message:
    """
    Message for inter-teammate communication.

    Messages are the primary mechanism for teammates to communicate
    with each other in a swarm. They support various message types
    and can carry arbitrary payload data.
    """

    # Unique message ID
    id: str = field(default_factory=lambda: str(uuid4()))
    # Message type
    type: MessageType = MessageType.CUSTOM
    # Sender agent ID (None for system messages)
    sender: Optional[str] = None
    # Recipient agent ID (None for broadcast messages)
    recipient: Optional[str] = None
    # Message payload (type-specific data)
    payload: Dict[str, Any] = field(default_factory=dict)
    # Message timestamp (ISO format)
    timestamp: str = field(
        default_factory=lambda: __import__("datetime").datetime.now().isoformat()
    )
    # Correlation ID for request/response patterns
    correlation_id: Optional[str] = None
    # Priority (higher = more urgent)
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "sender": self.sender,
            "recipient": self.recipient,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create message from dictionary."""
        return cls(
            id=data.get("id", str(uuid4())),
            type=MessageType(data.get("type", "custom")),
            sender=data.get("sender"),
            recipient=data.get("recipient"),
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp"),
            correlation_id=data.get("correlation_id"),
            priority=data.get("priority", 0),
        )

    def is_broadcast(self) -> bool:
        """Check if this is a broadcast message."""
        return self.recipient is None or self.type == MessageType.BROADCAST

    def is_system(self) -> bool:
        """Check if this is a system message."""
        return self.type == MessageType.SYSTEM or self.sender is None


class Mailbox:
    """
    Message mailbox for a teammate.

    Each teammate has a mailbox that serves as its incoming message queue.
    The mailbox supports:
    - Asynchronous message delivery
    - Priority-based message ordering
    - Message filtering by type or sender
    - Request/response correlation

    Example:
        mailbox = Mailbox(agent_id="researcher@team")

        # Send a message
        await mailbox.put(message)

        # Receive next message
        msg = await mailbox.get()

        # Receive with timeout
        msg = await mailbox.get(timeout=5.0)
    """

    def __init__(self, agent_id: str, max_size: int = 1000):
        """
        Initialize mailbox.

        Args:
            agent_id: The agent ID this mailbox belongs to
            max_size: Maximum number of messages in queue (0 = unlimited)
        """
        self.agent_id = agent_id
        self._queue: asyncio.PriorityQueue[tuple[int, int, Message]] = asyncio.PriorityQueue(
            maxsize=max_size
        )
        self._counter = 0  # For maintaining FIFO order within same priority
        self._closed = False
        self._pending_responses: Dict[str, asyncio.Future[Message]] = {}

    @property
    def is_closed(self) -> bool:
        """Check if mailbox is closed."""
        return self._closed

    async def put(self, message: Message) -> None:
        """
        Put a message into the mailbox.

        Args:
            message: The message to deliver

        Raises:
            RuntimeError: If mailbox is closed
            asyncio.QueueFull: If mailbox is full
        """
        if self._closed:
            raise RuntimeError(f"Mailbox for {self.agent_id} is closed")

        # Check if this is a response to a pending request
        if message.correlation_id and message.correlation_id in self._pending_responses:
            future = self._pending_responses.pop(message.correlation_id)
            if not future.done():
                future.set_result(message)
            return

        # Add to priority queue (negative priority for higher = first)
        self._counter += 1
        await self._queue.put((-message.priority, self._counter, message))

    async def get(self, timeout: Optional[float] = None) -> Optional[Message]:
        """
        Get next message from mailbox.

        Args:
            timeout: Maximum time to wait (None = wait forever)

        Returns:
            Message or None if timeout

        Raises:
            RuntimeError: If mailbox is closed and empty
        """
        if self._closed and self._queue.empty():
            raise RuntimeError(f"Mailbox for {self.agent_id} is closed")

        try:
            if timeout is not None:
                priority, counter, message = await asyncio.wait_for(
                    self._queue.get(), timeout=timeout
                )
            else:
                priority, counter, message = await self._queue.get()
            return message
        except asyncio.TimeoutError:
            return None

    async def get_filtered(
        self,
        message_type: Optional[MessageType] = None,
        sender: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Optional[Message]:
        """
        Get next message matching filters.

        Args:
            message_type: Filter by message type
            sender: Filter by sender
            timeout: Maximum time to wait

        Returns:
            Matching message or None if timeout
        """
        deadline = None
        if timeout is not None:
            deadline = asyncio.get_event_loop().time() + timeout

        while True:
            remaining = None
            if deadline is not None:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    return None

            message = await self.get(timeout=remaining)
            if message is None:
                return None

            # Check filters
            if message_type is not None and message.type != message_type:
                # Put back and continue (this is inefficient but simple)
                await self.put(message)
                continue

            if sender is not None and message.sender != sender:
                await self.put(message)
                continue

            return message

    async def request(
        self,
        message: Message,
        timeout: float = 30.0,
    ) -> Optional[Message]:
        """
        Send a request and wait for response.

        Args:
            message: The request message (will have correlation_id set)
            timeout: Maximum time to wait for response

        Returns:
            Response message or None if timeout
        """
        correlation_id = str(uuid4())
        message.correlation_id = correlation_id

        # Create future for response
        future: asyncio.Future[Message] = asyncio.get_event_loop().create_future()
        self._pending_responses[correlation_id] = future

        try:
            # Send the request
            await self.put(message)

            # Wait for response
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            # Clean up if still pending
            if correlation_id in self._pending_responses:
                del self._pending_responses[correlation_id]

    def close(self) -> None:
        """Close the mailbox."""
        self._closed = True
        # Cancel all pending response futures
        for future in self._pending_responses.values():
            if not future.done():
                future.cancel()
        self._pending_responses.clear()

    def size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()

    def empty(self) -> bool:
        """Check if mailbox is empty."""
        return self._queue.empty()


# Global mailbox registry
_mailboxes: Dict[str, Mailbox] = {}


def get_or_create_mailbox(agent_id: str, max_size: int = 1000) -> Mailbox:
    """
    Get existing mailbox or create new one.

    Args:
        agent_id: The agent ID
        max_size: Maximum mailbox size

    Returns:
        Mailbox instance
    """
    if agent_id not in _mailboxes:
        _mailboxes[agent_id] = Mailbox(agent_id, max_size)
    return _mailboxes[agent_id]


def get_mailbox(agent_id: str) -> Optional[Mailbox]:
    """
    Get existing mailbox.

    Args:
        agent_id: The agent ID

    Returns:
        Mailbox or None if not found
    """
    return _mailboxes.get(agent_id)


def remove_mailbox(agent_id: str) -> bool:
    """
    Remove a mailbox.

    Args:
        agent_id: The agent ID

    Returns:
        True if removed, False if not found
    """
    if agent_id in _mailboxes:
        _mailboxes[agent_id].close()
        del _mailboxes[agent_id]
        return True
    return False


def clear_mailboxes() -> None:
    """Clear all mailboxes."""
    for mailbox in _mailboxes.values():
        mailbox.close()
    _mailboxes.clear()


async def send_message(
    message: Message,
    recipient_id: Optional[str] = None,
) -> bool:
    """
    Send a message to a teammate.

    Args:
        message: The message to send
        recipient_id: Override recipient (optional)

    Returns:
        True if sent successfully, False otherwise
    """
    target_id = recipient_id or message.recipient
    if not target_id:
        return False

    mailbox = get_mailbox(target_id)
    if mailbox is None:
        return False

    try:
        await mailbox.put(message)
        return True
    except Exception:
        return False


async def receive_message(
    agent_id: str,
    timeout: Optional[float] = None,
    message_type: Optional[MessageType] = None,
) -> Optional[Message]:
    """
    Receive a message from mailbox.

    Args:
        agent_id: The agent ID to receive for
        timeout: Maximum time to wait
        message_type: Filter by message type

    Returns:
        Message or None if timeout/no message
    """
    mailbox = get_mailbox(agent_id)
    if mailbox is None:
        return None

    if message_type:
        return await mailbox.get_filtered(message_type=message_type, timeout=timeout)
    return await mailbox.get(timeout=timeout)
