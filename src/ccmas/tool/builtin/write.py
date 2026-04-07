"""
Write tool for writing file contents.

This tool provides safe file writing with proper error handling.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict

from ccmas.tool.base import Tool, ToolCallArgs, ToolExecutionResult


class WriteTool(Tool):
    """
    Tool for writing file contents.

    Provides safe file writing with directory creation, backup support,
    and proper error handling.
    """

    @property
    def name(self) -> str:
        """Get the tool name."""
        return "write"

    @property
    def description(self) -> str:
        """Get the tool description."""
        return """Write content to a file.

This tool writes content to a file, creating the file if it doesn't exist
or overwriting it if it does. It supports:
- Creating parent directories if needed
- UTF-8 encoding
- Proper error handling

The file path must be an absolute path. Use with caution as this will
overwrite existing files."""

    @property
    def parameters(self) -> Dict[str, Any]:
        """Get the JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The absolute path to the file to write",
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file",
                },
                "create_dirs": {
                    "type": "boolean",
                    "description": "Whether to create parent directories if they don't exist (default: true)",
                    "default": True,
                },
            },
            "required": ["file_path", "content"],
        }

    async def execute(self, args: ToolCallArgs) -> ToolExecutionResult:
        """
        Execute file writing.

        Args:
            args: Tool call arguments containing the file path and content

        Returns:
            ToolExecutionResult with operation status
        """
        start_time = time.time()

        file_path = args.arguments.get("file_path")
        if not file_path:
            output = self._create_error_output(
                args.tool_call_id, "Error: 'file_path' argument is required"
            )
            return self._create_result(
                args.tool_call_id, output, 0.0, {"error": "missing_file_path"}
            )

        content = args.arguments.get("content")
        if content is None:
            output = self._create_error_output(
                args.tool_call_id, "Error: 'content' argument is required"
            )
            return self._create_result(
                args.tool_call_id, output, 0.0, {"error": "missing_content"}
            )

        create_dirs = args.arguments.get("create_dirs", True)

        try:
            # Create parent directories if needed
            parent_dir = os.path.dirname(file_path)
            if parent_dir and create_dirs and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)

            # Check if file exists (for metadata)
            file_existed = os.path.exists(file_path)

            # Write file asynchronously
            await self._write_file_async(file_path, content)

            execution_time = (time.time() - start_time) * 1000

            # Get file stats
            file_stat = os.stat(file_path)
            metadata = {
                "file_path": file_path,
                "bytes_written": file_stat.st_size,
                "file_existed": file_existed,
                "created_dirs": create_dirs and parent_dir and not os.path.exists(parent_dir),
            }

            output = self._create_success_output(
                args.tool_call_id,
                f"Successfully wrote {file_stat.st_size} bytes to {file_path}",
            )

            return self._create_result(args.tool_call_id, output, execution_time, metadata)

        except PermissionError:
            execution_time = (time.time() - start_time) * 1000
            output = self._create_error_output(
                args.tool_call_id, f"Error: Permission denied writing to file: {file_path}"
            )
            return self._create_result(
                args.tool_call_id,
                output,
                execution_time,
                {"error": "permission_denied"},
            )
        except IsADirectoryError:
            execution_time = (time.time() - start_time) * 1000
            output = self._create_error_output(
                args.tool_call_id, f"Error: Path is a directory, not a file: {file_path}"
            )
            return self._create_result(
                args.tool_call_id,
                output,
                execution_time,
                {"error": "is_directory"},
            )
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            output = self._create_error_output(
                args.tool_call_id, f"Error writing file: {str(e)}"
            )
            return self._create_result(
                args.tool_call_id,
                output,
                execution_time,
                {"error": "write_error", "exception": str(e)},
            )

    async def _write_file_async(self, file_path: str, content: str) -> None:
        """
        Write file contents asynchronously.

        Args:
            file_path: Path to the file
            content: Content to write
        """
        import asyncio

        # Run file writing in a thread pool
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._write_file_sync, file_path, content)

    def _write_file_sync(self, file_path: str, content: str) -> None:
        """
        Write file contents synchronously.

        Args:
            file_path: Path to the file
            content: Content to write
        """
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
