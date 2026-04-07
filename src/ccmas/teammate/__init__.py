"""
Teammate module for CCMAS.

This module provides functionality for creating and managing teammates
in a multi-agent swarm system. It supports both in-process teammates
(for concurrent execution within the same process) and process-based
teammates (for isolation and resource management).

Key components:
- Mailbox: Message queue system for inter-teammate communication
- InProcessTeammate: In-process teammate implementation using contextvars
- spawn_teammate(): Factory function for creating teammates
- SendMessageTool: Tool for sending messages to teammates
"""

from __future__ import annotations

from .in_process import InProcessTeammate
from .mailbox import Mailbox, Message, MessageType, send_message, receive_message
from .send_message import SendMessageTool
from .spawn import TeammateBackend, TeammateConfig, spawn_teammate

__all__ = [
    # Mailbox system
    "Mailbox",
    "Message",
    "MessageType",
    "send_message",
    "receive_message",
    # In-process teammate
    "InProcessTeammate",
    # Spawning
    "TeammateBackend",
    "TeammateConfig",
    "spawn_teammate",
    # Tools
    "SendMessageTool",
]
