"""
Tmux backend for teammate management.

This module provides TmuxWorker and TmuxMailbox classes for managing
teammates running in tmux sessions. It uses tmux for terminal multiplexing
and inter-process communication through stdin/stdout.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from uuid import uuid4

logger = logging.getLogger(__name__)

TMUX_COMMAND = "tmux"
SWARM_SOCKET_NAME = "ccmas-swarm"
SWARM_SESSION_NAME = "ccmas-swarm"
SWARM_VIEW_WINDOW_NAME = "swarm-view"
HIDDEN_SESSION_NAME = "ccmas-hidden"

PANE_SHELL_INIT_DELAY_MS = 200


def _run_tmux(args: List[str], socket_name: Optional[str] = None) -> subprocess.CompletedProcess:
    """
    Run a tmux command.

    Args:
        args: Arguments for tmux command
        socket_name: Optional socket name to use

    Returns:
        CompletedProcess result
    """
    cmd = [TMUX_COMMAND]
    if socket_name:
        cmd.extend(["-L", socket_name])
    cmd.extend(args)

    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        logger.error(f"tmux command timed out: {' '.join(cmd)}")
        return subprocess.CompletedProcess(cmd, 1, "", "Command timed out")
    except FileNotFoundError:
        logger.error("tmux command not found - is tmux installed?")
        return subprocess.CompletedProcess(cmd, 1, "", "tmux not found")


async def _run_tmux_async(args: List[str], socket_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Run a tmux command asynchronously.

    Args:
        args: Arguments for tmux command
        socket_name: Optional socket name to use

    Returns:
        Dict with stdout, stderr, code
    """
    cmd = [TMUX_COMMAND]
    if socket_name:
        cmd.extend(["-L", socket_name])
    cmd.extend(args)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        return {
            "stdout": stdout.decode() if stdout else "",
            "stderr": stderr.decode() if stderr else "",
            "code": proc.returncode or 0,
        }
    except asyncio.TimeoutError:
        logger.error(f"tmux command timed out: {' '.join(cmd)}")
        return {"stdout": "", "stderr": "Command timed out", "code": 1}
    except FileNotFoundError:
        logger.error("tmux command not found - is tmux installed?")
        return {"stdout": "", "stderr": "tmux not found", "code": 1}


def is_tmux_available() -> bool:
    """
    Check if tmux is available on the system.

    Returns:
        True if tmux is installed and available
    """
    result = _run_tmux(["-V"])
    return result.returncode == 0


def is_inside_tmux() -> bool:
    """
    Check if currently running inside a tmux session.

    Returns:
        True if running inside tmux
    """
    return os.environ.get("TMUX") is not None


def get_tmux_pane_id() -> Optional[str]:
    """
    Get the current tmux pane ID.

    Returns:
        Pane ID (e.g., '%1') or None
    """
    result = _run_tmux(["display-message", "-p", "#{pane_id}"])
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def get_tmux_session_name() -> Optional[str]:
    """
    Get the current tmux session name.

    Returns:
        Session name or None
    """
    result = _run_tmux(["display-message", "-p", "#{session_name}"])
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def get_tmux_window_index() -> Optional[str]:
    """
    Get the current window index.

    Returns:
        Window index or None
    """
    result = _run_tmux(["display-message", "-p", "#{window_index}"])
    if result.returncode == 0:
        return result.stdout.strip()
    return None


class TmuxWorker:
    """
    Tmux worker process manager.

    Manages worker processes running in tmux sessions. Each worker
    runs in its own tmux pane within a shared session.

    Features:
    - Create/destroy tmux sessions
    - Spawn workers in separate panes
    - Send commands via stdin/stdout
    - Worker lifecycle management

    Example:
        worker = TmuxWorker("researcher@team", session_name="my-session")
        await worker.start()
        await worker.send_command("echo 'hello'")
        response = await worker.recv_response(timeout=5.0)
        await worker.stop()
    """

    def __init__(
        self,
        agent_id: str,
        session_name: Optional[str] = None,
        socket_name: str = SWARM_SOCKET_NAME,
    ):
        """
        Initialize tmux worker.

        Args:
            agent_id: Agent ID (e.g., "researcher@team")
            session_name: Tmux session name (auto-generated if None)
            socket_name: Tmux socket name for isolation
        """
        self.agent_id = agent_id
        self.session_name = session_name or f"ccmas-{agent_id.replace('@', '-')}"
        self.socket_name = socket_name
        self._pane_id: Optional[str] = None
        self._window_target: Optional[str] = None
        self._running = False
        self._process: Optional[asyncio.subprocess.Process] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._response_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._lock = asyncio.Lock()

    @property
    def pane_id(self) -> Optional[str]:
        """Get the tmux pane ID."""
        return self._pane_id

    @property
    def window_target(self) -> str:
        """Get the window target (session:window)."""
        if self._window_target:
            return self._window_target
        return f"{self.session_name}:0"

    @property
    def is_running(self) -> bool:
        """Check if worker is running."""
        return self._running

    async def start(self, command: Optional[str] = None) -> bool:
        """
        Start the tmux worker.

        Creates a new tmux session and pane for this worker.

        Args:
            command: Optional command to run in the worker pane

        Returns:
            True if started successfully
        """
        if self._running:
            logger.warning(f"Worker {self.agent_id} is already running")
            return True

        async with self._lock:
            try:
                session_exists = await self._session_exists()
                if not session_exists:
                    await self._create_session()
                else:
                    await self._create_pane()

                await asyncio.sleep(PANE_SHELL_INIT_DELAY_MS / 1000.0)

                if command:
                    await self.send_command(command)

                self._running = True
                self._reader_task = asyncio.create_task(self._read_responses())

                logger.info(f"Started tmux worker: {self.agent_id}, pane: {self._pane_id}")
                return True

            except Exception as e:
                logger.error(f"Failed to start worker {self.agent_id}: {e}")
                return False

    async def stop(self, timeout: float = 5.0) -> bool:
        """
        Stop the tmux worker.

        Args:
            timeout: Maximum time to wait for shutdown

        Returns:
            True if stopped successfully
        """
        if not self._running:
            return True

        logger.info(f"Stopping tmux worker: {self.agent_id}")

        self._running = False

        if self._reader_task:
            self._reader_task.cancel()
            try:
                await asyncio.wait_for(self._reader_task, timeout=timeout)
            except asyncio.TimeoutError:
                self._reader_task.cancel()
            except asyncio.CancelledError:
                pass

        if self._pane_id:
            result = await _run_tmux_async(
                ["kill-pane", "-t", self._pane_id],
                self.socket_name,
            )
            if result["code"] != 0:
                logger.warning(f"Failed to kill pane: {result['stderr']}")

        self._pane_id = None
        self._running = False

        logger.info(f"Stopped tmux worker: {self.agent_id}")
        return True

    async def send_command(self, command: str) -> bool:
        """
        Send a command to the worker pane.

        Args:
            command: Command to send (will be sent as tmux send-keys)

        Returns:
            True if sent successfully
        """
        if not self._pane_id:
            logger.error(f"No pane ID for worker {self.agent_id}")
            return False

        escaped = shlex.quote(command) if isinstance(command, str) else command
        result = await _run_tmux_async(
            ["send-keys", "-t", self._pane_id, command, "Enter"],
            self.socket_name,
        )

        if result["code"] != 0:
            logger.error(f"Failed to send command to {self._pane_id}: {result['stderr']}")
            return False

        return True

    async def send_message(self, message: Dict[str, Any]) -> bool:
        """
        Send a JSON message to the worker.

        Args:
            message: Message dictionary to send

        Returns:
            True if sent successfully
        """
        json_str = json.dumps(message)
        return await self.send_command(json_str)

    async def recv_response(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Receive a response from the worker.

        Args:
            timeout: Maximum time to wait (None = wait forever)

        Returns:
            Response dictionary or None if timeout
        """
        try:
            if timeout is not None:
                return await asyncio.wait_for(self._response_queue.get(), timeout=timeout)
            return await self._response_queue.get()
        except asyncio.TimeoutError:
            return None

    async def set_border_color(self, color: str) -> bool:
        """
        Set the border color of the worker pane.

        Args:
            color: Color name (red, blue, green, yellow, purple, cyan, etc.)

        Returns:
            True if set successfully
        """
        if not self._pane_id:
            return False

        tmux_color = _get_tmux_color(color)

        await _run_tmux_async(
            ["select-pane", "-t", self._pane_id, "-P", f"bg=default,fg={tmux_color}"],
            self.socket_name,
        )

        await _run_tmux_async(
            ["set-option", "-p", "-t", self._pane_id, "pane-border-style", f"fg={tmux_color}"],
            self.socket_name,
        )

        await _run_tmux_async(
            ["set-option", "-p", "-t", self._pane_id, "pane-active-border-style", f"fg={tmux_color}"],
            self.socket_name,
        )

        return True

    async def set_title(self, title: str, color: Optional[str] = None) -> bool:
        """
        Set the title of the worker pane.

        Args:
            title: Title string
            color: Optional color for the title

        Returns:
            True if set successfully
        """
        if not self._pane_id:
            return False

        await _run_tmux_async(
            ["select-pane", "-t", self._pane_id, "-T", title],
            self.socket_name,
        )

        if color:
            tmux_color = _get_tmux_color(color)
            await _run_tmux_async(
                [
                    "set-option", "-p", "-t", self._pane_id,
                    "pane-border-format",
                    f"#[fg={tmux_color},bold] {{pane_title}} #[default]",
                ],
                self.socket_name,
            )
        else:
            await _run_tmux_async(
                ["set-option", "-p", "-t", self._pane_id, "pane-border-format", "#{pane_title}"],
                self.socket_name,
            )

        return True

    async def _session_exists(self) -> bool:
        """Check if the tmux session exists."""
        result = await _run_tmux_async(["has-session", "-t", self.session_name], self.socket_name)
        return result["code"] == 0

    async def _create_session(self) -> None:
        """Create a new tmux session with a window."""
        window_name = "worker"

        result = await _run_tmux_async(
            [
                "new-session",
                "-d",
                "-s",
                self.session_name,
                "-n",
                window_name,
                "-P",
                "-F",
                "#{pane_id}",
            ],
            self.socket_name,
        )

        if result["code"] != 0:
            raise RuntimeError(f"Failed to create tmux session: {result['stderr']}")

        self._pane_id = result["stdout"].strip()
        self._window_target = f"{self.session_name}:{window_name}"

        logger.debug(f"Created tmux session {self.session_name}, pane {self._pane_id}")

    async def _create_pane(self) -> None:
        """Create a new pane in the existing session."""
        list_result = await _run_tmux_async(
            ["list-panes", "-t", f"{self.session_name}:0", "-F", "#{pane_id}"],
            self.socket_name,
        )

        panes = [p for p in list_result["stdout"].strip().split("\n") if p]
        pane_count = len(panes)

        split_vertically = pane_count % 2 == 1
        split_flag = "-v" if split_vertically else "-h"

        target_pane = panes[-1] if panes else f"{self.session_name}:0"

        result = await _run_tmux_async(
            [
                "split-window",
                "-t",
                target_pane,
                split_flag,
                "-P",
                "-F",
                "#{pane_id}",
            ],
            self.socket_name,
        )

        if result["code"] != 0:
            raise RuntimeError(f"Failed to create pane: {result['stderr']}")

        self._pane_id = result["stdout"].strip()

        logger.debug(f"Created pane {self._pane_id} in session {self.session_name}")

    async def _read_responses(self) -> None:
        """Background task to read responses from the worker."""
        while self._running:
            try:
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error reading responses: {e}")

    def get_pane_target(self) -> str:
        """
        Get the full pane target for tmux commands.

        Returns:
            Pane target in format "session:window.pane"
        """
        if self._pane_id:
            return f"{self.window_target}.{self._pane_id.replace('%', '')}"
        return self.window_target


def _get_tmux_color(color: str) -> str:
    """
    Map agent color to tmux color.

    Args:
        color: Agent color name

    Returns:
        Tmux-compatible color name
    """
    color_map = {
        "red": "red",
        "blue": "blue",
        "green": "green",
        "yellow": "yellow",
        "purple": "magenta",
        "orange": "colour208",
        "pink": "colour205",
        "cyan": "cyan",
    }
    return color_map.get(color.lower(), color)


class TmuxMailbox:
    """
    Tmux-based mailbox for inter-teammate communication.

    This mailbox extends the base Mailbox to work with tmux-based workers.
    Messages are sent via tmux panes and responses are collected through
    the worker's response queue.

    Note: This is a simplified implementation. For full tmux-based
    communication, consider using named pipes or UNIX sockets for
    better reliability.

    Example:
        mailbox = TmuxMailbox("researcher@team", worker)
        await mailbox.put(message)
        response = await mailbox.get(timeout=5.0)
    """

    def __init__(
        self,
        agent_id: str,
        worker: TmuxWorker,
        max_size: int = 1000,
    ):
        """
        Initialize tmux mailbox.

        Args:
            agent_id: Agent ID this mailbox belongs to
            worker: TmuxWorker instance for communication
            max_size: Maximum message queue size
        """
        self.agent_id = agent_id
        self._worker = worker
        self._queue: asyncio.PriorityQueue[tuple[int, int, Dict[str, Any]]] = asyncio.PriorityQueue(
            maxsize=max_size
        )
        self._counter = 0
        self._closed = False
        self._pending_responses: Dict[str, asyncio.Future[Dict[str, Any]]] = {}

    @property
    def is_closed(self) -> bool:
        """Check if mailbox is closed."""
        return self._closed

    def size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()

    def empty(self) -> bool:
        """Check if mailbox is empty."""
        return self._queue.empty()

    async def put(self, message: Dict[str, Any]) -> None:
        """
        Put a message into the mailbox (sent to worker).

        Args:
            message: Message dictionary

        Raises:
            RuntimeError: If mailbox is closed
            asyncio.QueueFull: If mailbox is full
        """
        if self._closed:
            raise RuntimeError(f"Mailbox for {self.agent_id} is closed")

        correlation_id = message.get("correlation_id")
        if correlation_id and correlation_id in self._pending_responses:
            future = self._pending_responses.pop(correlation_id)
            if not future.done():
                future.set_result(message)
            return

        message_with_sender = {
            **message,
            "sender": self.agent_id,
            "id": message.get("id", str(uuid4())),
        }

        await self._worker.send_message(message_with_sender)

        priority = message.get("priority", 0)
        self._counter += 1
        await self._queue.put((-priority, self._counter, message_with_sender))

    async def get(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Get next message from mailbox.

        Args:
            timeout: Maximum time to wait (None = wait forever)

        Returns:
            Message dictionary or None if timeout

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

    async def request(
        self,
        message: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Optional[Dict[str, Any]]:
        """
        Send a request and wait for response.

        Args:
            message: Request message
            timeout: Maximum time to wait

        Returns:
            Response message or None if timeout
        """
        correlation_id = str(uuid4())
        message_with_cid = {
            **message,
            "correlation_id": correlation_id,
        }

        future: asyncio.Future[Dict[str, Any]] = asyncio.get_event_loop().create_future()
        self._pending_responses[correlation_id] = future

        try:
            await self.put(message_with_cid)

            try:
                return await asyncio.wait_for(future, timeout=timeout)
            except asyncio.TimeoutError:
                return None
        finally:
            if correlation_id in self._pending_responses:
                del self._pending_responses[correlation_id]

    async def recv_from_worker(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Receive a message from the worker.

        Args:
            timeout: Maximum time to wait

        Returns:
            Message from worker or None
        """
        response = await self._worker.recv_response(timeout=timeout)
        return response

    def close(self) -> None:
        """Close the mailbox."""
        self._closed = True
        for future in self._pending_responses.values():
            if not future.done():
                future.cancel()
        self._pending_responses.clear()


class TmuxSwarmManager:
    """
    Manager for tmux-based swarm sessions.

    Handles creation and management of the swarm session that contains
    all teammate panes. This provides a unified interface for swarm-level
    operations like rebalancing panes, enabling border status, etc.

    Example:
        manager = TmuxSwarmManager()
        await manager.initialize()
        pane_id = await manager.create_teammate_pane("researcher", "blue")
        await manager.set_pane_title(pane_id, "researcher", "blue")
        await manager.rebalance_panes()
        await manager.shutdown()
    """

    def __init__(self, socket_name: str = SWARM_SOCKET_NAME):
        """
        Initialize swarm manager.

        Args:
            socket_name: Tmux socket name for isolation
        """
        self.socket_name = socket_name
        self._session_name = SWARM_SESSION_NAME
        self._window_name = SWARM_VIEW_WINDOW_NAME
        self._initialized = False
        self._pane_count = 0

    @property
    def is_initialized(self) -> bool:
        """Check if swarm session is initialized."""
        return self._initialized

    async def initialize(self) -> bool:
        """
        Initialize the swarm session.

        Creates the swarm session and swarm-view window if they don't exist.

        Returns:
            True if initialized successfully
        """
        if self._initialized:
            return True

        try:
            session_exists = await self._session_exists()

            if not session_exists:
                result = await _run_tmux_async(
                    [
                        "new-session",
                        "-d",
                        "-s",
                        self._session_name,
                        "-n",
                        self._window_name,
                        "-P",
                        "-F",
                        "#{pane_id}",
                    ],
                    self.socket_name,
                )

                if result["code"] != 0:
                    logger.error(f"Failed to create swarm session: {result['stderr']}")
                    return False

                logger.info(f"Created swarm session: {self._session_name}")

            await self.enable_pane_border_status()
            self._initialized = True
            return True

        except Exception as e:
            logger.error(f"Failed to initialize swarm: {e}")
            return False

    async def create_teammate_pane(
        self,
        teammate_name: str,
        color: str = "blue",
    ) -> Optional[str]:
        """
        Create a new teammate pane in the swarm view.

        Args:
            teammate_name: Name of the teammate
            color: Agent color

        Returns:
            Pane ID or None if failed
        """
        if not self._initialized:
            await self.initialize()

        window_target = f"{self._session_name}:{self._window_name}"

        list_result = await _run_tmux_async(
            ["list-panes", "-t", window_target, "-F", "#{pane_id}"],
            self.socket_name,
        )

        if list_result["code"] != 0:
            panes = []
        else:
            panes = [p for p in list_result["stdout"].strip().split("\n") if p]

        pane_count = len(panes)
        is_first_teammate = pane_count == 1

        if is_first_teammate:
            pane_id = panes[0]
            logger.debug(f"Using existing pane for first teammate: {pane_id}")
        else:
            split_vertically = pane_count % 2 == 1
            target_index = (pane_count - 1) // 2
            target_pane = panes[target_index] if target_index < len(panes) else panes[-1]

            split_flag = "-v" if split_vertically else "-h"

            result = await _run_tmux_async(
                [
                    "split-window",
                    "-t",
                    target_pane,
                    split_flag,
                    "-P",
                    "-F",
                    "#{pane_id}",
                ],
                self.socket_name,
            )

            if result["code"] != 0:
                logger.error(f"Failed to create pane: {result['stderr']}")
                return None

            pane_id = result["stdout"].strip()

        await self.set_pane_border_color(pane_id, color)
        await self.set_pane_title(pane_id, teammate_name, color)
        await self.rebalance_panes()

        self._pane_count += 1
        return pane_id

    async def kill_pane(self, pane_id: str) -> bool:
        """
        Kill a teammate pane.

        Args:
            pane_id: Pane ID to kill

        Returns:
            True if killed successfully
        """
        result = await _run_tmux_async(
            ["kill-pane", "-t", pane_id],
            self.socket_name,
        )
        if result["code"] == 0:
            self._pane_count = max(0, self._pane_count - 1)
        return result["code"] == 0

    async def hide_pane(self, pane_id: str) -> bool:
        """
        Hide a pane by moving it to a hidden session.

        Args:
            pane_id: Pane ID to hide

        Returns:
            True if hidden successfully
        """
        hidden_session_exists = await self._session_exists_in_swarm(HIDDEN_SESSION_NAME)

        if not hidden_session_exists:
            await _run_tmux_async(
                ["new-session", "-d", "-s", HIDDEN_SESSION_NAME],
                self.socket_name,
            )

        result = await _run_tmux_async(
            [
                "break-pane",
                "-d",
                "-s",
                pane_id,
                "-t",
                f"{HIDDEN_SESSION_NAME}:",
            ],
            self.socket_name,
        )

        if result["code"] == 0:
            self._pane_count = max(0, self._pane_count - 1)

        return result["code"] == 0

    async def show_pane(
        self,
        pane_id: str,
        target_window: Optional[str] = None,
    ) -> bool:
        """
        Show a hidden pane.

        Args:
            pane_id: Pane ID to show
            target_window: Target window to join into

        Returns:
            True if shown successfully
        """
        target = target_window or f"{self._session_name}:{self._window_name}"

        result = await _run_tmux_async(
            [
                "join-pane",
                "-h",
                "-s",
                pane_id,
                "-t",
                target,
            ],
            self.socket_name,
        )

        if result["code"] != 0:
            logger.error(f"Failed to show pane: {result['stderr']}")
            return False

        await _run_tmux_async(
            ["select-layout", "-t", target, "main-vertical"],
            self.socket_name,
        )

        return True

    async def set_pane_border_color(self, pane_id: str, color: str) -> bool:
        """
        Set border color for a pane.

        Args:
            pane_id: Pane ID
            color: Color name

        Returns:
            True if set successfully
        """
        tmux_color = _get_tmux_color(color)

        await _run_tmux_async(
            ["select-pane", "-t", pane_id, "-P", f"bg=default,fg={tmux_color}"],
            self.socket_name,
        )

        await _run_tmux_async(
            ["set-option", "-p", "-t", pane_id, "pane-border-style", f"fg={tmux_color}"],
            self.socket_name,
        )

        await _run_tmux_async(
            ["set-option", "-p", "-t", pane_id, "pane-active-border-style", f"fg={tmux_color}"],
            self.socket_name,
        )

        return True

    async def set_pane_title(
        self,
        pane_id: str,
        name: str,
        color: Optional[str] = None,
    ) -> bool:
        """
        Set title for a pane.

        Args:
            pane_id: Pane ID
            name: Title name
            color: Optional color

        Returns:
            True if set successfully
        """
        await _run_tmux_async(
            ["select-pane", "-t", pane_id, "-T", name],
            self.socket_name,
        )

        if color:
            tmux_color = _get_tmux_color(color)
            await _run_tmux_async(
                [
                    "set-option", "-p", "-t", pane_id,
                    "pane-border-format",
                    f"#[fg={tmux_color},bold] {{pane_title}} #[default]",
                ],
                self.socket_name,
            )
        else:
            await _run_tmux_async(
                ["set-option", "-p", "-t", pane_id, "pane-border-format", "#{pane_title}"],
                self.socket_name,
            )

        return True

    async def enable_pane_border_status(self) -> bool:
        """
        Enable pane border status for the swarm window.

        Returns:
            True if enabled successfully
        """
        window_target = f"{self._session_name}:{self._window_name}"

        result = await _run_tmux_async(
            [
                "set-option",
                "-w",
                "-t",
                window_target,
                "pane-border-status",
                "top",
            ],
            self.socket_name,
        )

        return result["code"] == 0

    async def rebalance_panes(self) -> bool:
        """
        Rebalance all panes in the swarm window.

        Returns:
            True if rebalanced successfully
        """
        window_target = f"{self._session_name}:{self._window_name}"

        list_result = await _run_tmux_async(
            ["list-panes", "-t", window_target, "-F", "#{pane_id}"],
            self.socket_name,
        )

        if list_result["code"] != 0:
            return False

        panes = [p for p in list_result["stdout"].strip().split("\n") if p]
        pane_count = len(panes)

        if pane_count <= 1:
            return True

        await _run_tmux_async(
            ["select-layout", "-t", window_target, "tiled"],
            self.socket_name,
        )

        logger.debug(f"Rebalanced {pane_count} panes with tiled layout")
        return True

    async def shutdown(self) -> None:
        """
        Shutdown the swarm session.

        Kills all panes and the session itself.
        """
        if self._session_exists():
            await _run_tmux_async(
                ["kill-session", "-t", self._session_name],
                self.socket_name,
            )

        if self._session_exists_in_swarm(HIDDEN_SESSION_NAME):
            await _run_tmux_async(
                ["kill-session", "-t", HIDDEN_SESSION_NAME],
                self.socket_name,
            )

        self._initialized = False
        self._pane_count = 0

    async def _session_exists(self) -> bool:
        """Check if swarm session exists."""
        result = await _run_tmux_async(
            ["has-session", "-t", self._session_name],
            self.socket_name,
        )
        return result["code"] == 0

    async def _session_exists_in_swarm(self, session_name: str) -> bool:
        """Check if a session exists using swarm socket."""
        result = await _run_tmux_async(
            ["has-session", "-t", session_name],
            self.socket_name,
        )
        return result["code"] == 0
