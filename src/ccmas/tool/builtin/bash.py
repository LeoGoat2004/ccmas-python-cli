"""
Bash tool for executing shell commands.

This tool provides safe shell command execution with proper error handling.
"""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
from typing import Any, Dict, Optional

from ccmas.tool.base import Tool, ToolCallArgs, ToolExecutionResult


class BashTool(Tool):
    """
    Tool for executing shell commands.

    Provides safe execution of shell commands with timeout support,
    working directory control, and proper error handling.
    """

    @property
    def name(self) -> str:
        """Get the tool name."""
        return "bash"

    @property
    def description(self) -> str:
        """Get the tool description."""
        return """Execute a bash shell command.

This tool runs shell commands and returns the output. It supports:
- Command execution with timeout
- Working directory specification
- Environment variable handling
- Proper error capture

Use this tool to run system commands, scripts, or any shell operations."""

    @property
    def parameters(self) -> Dict[str, Any]:
        """Get the JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute",
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds (default: 120)",
                    "default": 120,
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory for the command (optional)",
                },
                "env": {
                    "type": "object",
                    "description": "Environment variables to set (optional)",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["command"],
        }

    async def execute(self, args: ToolCallArgs) -> ToolExecutionResult:
        """
        Execute a bash command.

        Args:
            args: Tool call arguments containing the command and options

        Returns:
            ToolExecutionResult with command output
        """
        import time

        start_time = time.time()

        command = args.arguments.get("command")
        if not command:
            output = self._create_error_output(
                args.tool_call_id, "Error: 'command' argument is required"
            )
            return self._create_result(
                args.tool_call_id, output, 0.0, {"error": "missing_command"}
            )

        timeout = args.arguments.get("timeout", 120)
        cwd = args.arguments.get("cwd")
        env = args.arguments.get("env", {})

        # Prepare environment
        process_env = os.environ.copy()
        process_env.update(env)

        # Determine shell based on OS
        if platform.system() == "Windows":
            # Use PowerShell on Windows
            shell_path = shutil.which("powershell") or shutil.which("pwsh")
            if shell_path:
                # PowerShell command
                full_command = [shell_path, "-Command", command]
            else:
                # Fallback to cmd
                full_command = ["cmd", "/c", command]
        else:
            # Unix-like systems
            full_command = ["/bin/bash", "-c", command]

        try:
            # Run the command
            process = await asyncio.create_subprocess_exec(
                *full_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=process_env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                output = self._create_error_output(
                    args.tool_call_id,
                    f"Error: Command timed out after {timeout} seconds",
                )
                execution_time = (time.time() - start_time) * 1000
                return self._create_result(
                    args.tool_call_id,
                    output,
                    execution_time,
                    {"error": "timeout", "timeout_seconds": timeout},
                )

            # Decode output
            stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
            stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

            execution_time = (time.time() - start_time) * 1000

            if process.returncode == 0:
                # Success
                result_content = stdout_str
                if stderr_str:
                    result_content += f"\n[stderr]\n{stderr_str}"
                output = self._create_success_output(args.tool_call_id, result_content)
                return self._create_result(
                    args.tool_call_id,
                    output,
                    execution_time,
                    {"return_code": process.returncode},
                )
            else:
                # Command failed
                error_content = f"Command failed with exit code {process.returncode}\n"
                if stdout_str:
                    error_content += f"[stdout]\n{stdout_str}\n"
                if stderr_str:
                    error_content += f"[stderr]\n{stderr_str}"
                output = self._create_error_output(args.tool_call_id, error_content)
                return self._create_result(
                    args.tool_call_id,
                    output,
                    execution_time,
                    {"return_code": process.returncode, "error": "command_failed"},
                )

        except FileNotFoundError as e:
            execution_time = (time.time() - start_time) * 1000
            output = self._create_error_output(
                args.tool_call_id, f"Error: Shell not found: {str(e)}"
            )
            return self._create_result(
                args.tool_call_id,
                output,
                execution_time,
                {"error": "shell_not_found"},
            )
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            output = self._create_error_output(
                args.tool_call_id, f"Error executing command: {str(e)}"
            )
            return self._create_result(
                args.tool_call_id,
                output,
                execution_time,
                {"error": "execution_error", "exception": str(e)},
            )
