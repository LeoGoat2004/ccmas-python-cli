"""
Permission module for CCMAS.

This module provides permission handling for tools, file operations,
and command execution with support for various permission modes.
"""

# Permission modes and results
from ccmas.permission.mode import (
    PermissionAction,
    PermissionContext,
    PermissionMode,
    PermissionResult,
)

# Permission checker
from ccmas.permission.checker import (
    PermissionChecker,
    PermissionRule,
    create_permission_checker,
)

# Permission bubbling
from ccmas.permission.bubble import (
    BubblePermissionHandler,
    BubbleRequest,
    BubbleResponse,
    PermissionBubbleQueue,
    bubble_permission,
    create_bubble_handler,
)

__all__ = [
    # Modes and results
    "PermissionMode",
    "PermissionAction",
    "PermissionResult",
    "PermissionContext",
    # Checker
    "PermissionChecker",
    "PermissionRule",
    "create_permission_checker",
    # Bubbling
    "BubbleRequest",
    "BubbleResponse",
    "BubblePermissionHandler",
    "PermissionBubbleQueue",
    "bubble_permission",
    "create_bubble_handler",
]
