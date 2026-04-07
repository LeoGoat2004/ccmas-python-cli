"""
In-process teammate implementation.

This module provides the InProcessTeammate class for running teammates
within the same process. It uses contextvars for context isolation,
allowing multiple teammates to run concurrently without state conflicts.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, TypeVar, Union

from ccmas.context.agent_context import (
    TeammateAgentContext,
    agent_context_var,
)
from ccmas.context.teammate_context import (
    TeammateContextManager,
    TeammateContextOptions,
    create_teammate_context,
)
from ccmas.types.message import Message as LLMMessage

from .mailbox import Mailbox, Message, MessageType, get_or_create_mailbox, remove_mailbox

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class InProcessTeammateConfig:
    """Configuration for an in-process teammate."""

    # Agent ID (e.g., "researcher@my-team")
    agent_id: str
    # Display name (e.g., "researcher")
    agent_name: str
    # Team name
    team_name: str
    # System prompt/personality
    system_prompt: str = ""
    # Whether plan mode is required
    plan_mode_required: bool = False
    # Parent session ID (team lead's session)
    parent_session_id: str = ""
    # Whether this is the team lead
    is_team_lead: bool = False
    # UI color
    agent_color: Optional[str] = None
    # Tools available to this teammate
    tools: List[str] = field(default_factory=list)
    # LLM model to use
    model: str = "default"
    # Max iterations per task
    max_iterations: int = 50
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


class InProcessTeammate:
    """
    In-process teammate for swarm coordination.

    In-process teammates run within the same process as the team lead,
    using contextvars for context isolation. This allows for:
    - Fast communication (no IPC overhead)
    - Shared memory access
    - Lightweight concurrency

    Each teammate has:
    - Its own context (via contextvars)
    - Its own mailbox for message receiving
    - Its own task loop for processing messages

    Example:
        config = InProcessTeammateConfig(
            agent_id="researcher@my-team",
            agent_name="researcher",
            team_name="my-team",
            system_prompt="You are a research specialist...",
        )

        teammate = InProcessTeammate(config)
        await teammate.start()

        # Send a task
        await teammate.send_task({
            "description": "Research Python async patterns",
        })

        # Stop the teammate
        await teammate.stop()
    """

    def __init__(self, config: InProcessTeammateConfig):
        """
        Initialize in-process teammate.

        Args:
            config: Teammate configuration
        """
        self.config = config
        self._context: Optional[TeammateAgentContext] = None
        self._context_manager: Optional[TeammateContextManager] = None
        self._mailbox: Optional[Mailbox] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._stop_event = asyncio.Event()

        # Message handlers
        self._handlers: Dict[MessageType, Callable[[Message], Coroutine]] = {
            MessageType.TASK: self._handle_task,
            MessageType.STATUS: self._handle_status,
            MessageType.QUESTION: self._handle_question,
            MessageType.BROADCAST: self._handle_broadcast,
            MessageType.SYSTEM: self._handle_system,
        }

    @property
    def agent_id(self) -> str:
        """Get agent ID."""
        return self.config.agent_id

    @property
    def is_running(self) -> bool:
        """Check if teammate is running."""
        return self._running

    async def start(self) -> None:
        """
        Start the teammate.

        Creates the context, mailbox, and starts the message processing loop.
        """
        if self._running:
            logger.warning(f"Teammate {self.agent_id} is already running")
            return

        logger.info(f"Starting in-process teammate: {self.agent_id}")

        # Create context
        context_options = TeammateContextOptions(
            agent_id=self.config.agent_id,
            agent_name=self.config.agent_name,
            team_name=self.config.team_name,
            plan_mode_required=self.config.plan_mode_required,
            parent_session_id=self.config.parent_session_id,
            is_team_lead=self.config.is_team_lead,
            agent_color=self.config.agent_color,
        )
        self._context = create_teammate_context(context_options)

        # Create mailbox
        self._mailbox = get_or_create_mailbox(self.agent_id)

        # Start message processing loop
        self._running = True
        self._stop_event.clear()
        self._task = asyncio.create_task(self._message_loop())

        logger.info(f"Teammate {self.agent_id} started successfully")

    async def stop(self, timeout: float = 5.0) -> None:
        """
        Stop the teammate.

        Args:
            timeout: Maximum time to wait for graceful shutdown
        """
        if not self._running:
            return

        logger.info(f"Stopping teammate: {self.agent_id}")

        self._running = False
        self._stop_event.set()

        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"Teammate {self.agent_id} did not stop gracefully, cancelling")
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

        # Clean up mailbox
        if self._mailbox:
            remove_mailbox(self.agent_id)
            self._mailbox = None

        logger.info(f"Teammate {self.agent_id} stopped")

    async def send_message(self, message: Message) -> bool:
        """
        Send a message to this teammate.

        Args:
            message: The message to send

        Returns:
            True if sent successfully
        """
        if not self._mailbox:
            return False

        try:
            await self._mailbox.put(message)
            return True
        except Exception as e:
            logger.error(f"Failed to send message to {self.agent_id}: {e}")
            return False

    async def send_task(self, task_data: Dict[str, Any], sender: Optional[str] = None) -> bool:
        """
        Send a task to this teammate.

        Args:
            task_data: Task description and parameters
            sender: Optional sender ID

        Returns:
            True if sent successfully
        """
        message = Message(
            type=MessageType.TASK,
            sender=sender,
            recipient=self.agent_id,
            payload=task_data,
        )
        return await self.send_message(message)

    def run_in_context(self, fn: Callable[[], T]) -> T:
        """
        Run a function within this teammate's context.

        Args:
            fn: Function to run

        Returns:
            Result of the function
        """
        if not self._context:
            raise RuntimeError("Teammate context not initialized")

        with TeammateContextManager(self._context):
            return fn()

    async def run_in_context_async(self, coro: Coroutine[Any, Any, T]) -> T:
        """
        Run a coroutine within this teammate's context.

        Args:
            coro: Coroutine to run

        Returns:
            Result of the coroutine
        """
        if not self._context:
            raise RuntimeError("Teammate context not initialized")

        async with TeammateContextManager(self._context):
            return await coro

    async def _message_loop(self) -> None:
        """Main message processing loop."""
        logger.info(f"Message loop started for {self.agent_id}")

        while self._running:
            try:
                # Wait for message or stop signal
                message = await self._get_message_or_stop()

                if message is None:
                    continue

                # Process message
                await self._process_message(message)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in message loop for {self.agent_id}: {e}")

        logger.info(f"Message loop ended for {self.agent_id}")

    async def _get_message_or_stop(self) -> Optional[Message]:
        """
        Get next message or return None if stopping.

        Returns:
            Message or None
        """
        if not self._mailbox:
            return None

        # Use a short timeout to check stop_event periodically
        try:
            message = await asyncio.wait_for(
                self._mailbox.get(),
                timeout=0.5,
            )
            return message
        except asyncio.TimeoutError:
            return None

    async def _process_message(self, message: Message) -> None:
        """
        Process a received message.

        Args:
            message: The message to process
        """
        handler = self._handlers.get(message.type)

        if handler:
            try:
                # Run handler in teammate context
                async with TeammateContextManager(self._context):
                    await handler(message)
            except Exception as e:
                logger.error(f"Error handling message {message.type} in {self.agent_id}: {e}")
        else:
            logger.warning(f"No handler for message type {message.type} in {self.agent_id}")

    async def _handle_task(self, message: Message) -> None:
        """
        Handle task assignment.

        Args:
            message: Task message
        """
        logger.info(f"Teammate {self.agent_id} received task: {message.payload}")

        # TODO: Implement task execution logic
        # This would typically:
        # 1. Parse the task
        # 2. Execute using the agent loop
        # 3. Send completion message back

        # Send completion notification
        completion = Message(
            type=MessageType.TASK_COMPLETE,
            sender=self.agent_id,
            recipient=message.sender,
            payload={
                "task_id": message.payload.get("id"),
                "status": "completed",
                "result": {},
            },
            correlation_id=message.correlation_id,
        )

        # Send back to sender if possible
        if message.sender:
            from .mailbox import send_message

            await send_message(completion)

    async def _handle_status(self, message: Message) -> None:
        """
        Handle status request.

        Args:
            message: Status message
        """
        # Respond with current status
        response = Message(
            type=MessageType.STATUS,
            sender=self.agent_id,
            recipient=message.sender,
            payload={
                "status": "active" if self._running else "inactive",
                "mailbox_size": self._mailbox.size() if self._mailbox else 0,
            },
            correlation_id=message.correlation_id,
        )

        if message.sender:
            from .mailbox import send_message

            await send_message(response)

    async def _handle_question(self, message: Message) -> None:
        """
        Handle question from another teammate.

        Args:
            message: Question message
        """
        # TODO: Implement question answering logic
        pass

    async def _handle_broadcast(self, message: Message) -> None:
        """
        Handle broadcast message.

        Args:
            message: Broadcast message
        """
        # Process broadcast (e.g., team-wide announcements)
        logger.info(f"Teammate {self.agent_id} received broadcast: {message.payload}")

    async def _handle_system(self, message: Message) -> None:
        """
        Handle system message.

        Args:
            message: System message
        """
        # Handle system commands (e.g., shutdown, reconfigure)
        command = message.payload.get("command")

        if command == "shutdown":
            await self.stop()
        elif command == "ping":
            # Respond to ping
            response = Message(
                type=MessageType.SYSTEM,
                sender=self.agent_id,
                recipient=message.sender,
                payload={"command": "pong"},
                correlation_id=message.correlation_id,
            )
            if message.sender:
                from .mailbox import send_message

                await send_message(response)
