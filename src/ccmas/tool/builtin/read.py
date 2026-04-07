"""
Read tool for reading file contents.

This tool provides safe file reading with proper error handling.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from ccmas.tool.base import Tool, ToolCallArgs, ToolExecutionResult


class ReadTool(Tool):
    """
    Tool for reading file contents.

    Provides safe file reading with encoding detection, line range support,
    and proper error handling.
    """

    @property
    def name(self) -> str:
        """Get the tool name."""
        return "read"

    @property
    def description(self) -> str:
        """Get the tool description."""
        return """Read the contents of a file.

This tool reads file contents and returns them as a string. It supports:
- Reading files with automatic encoding detection
- Reading specific line ranges
- Handling large files with truncation
- Proper error handling for missing or inaccessible files

The file path must be an absolute path."""

    @property
    def parameters(self) -> Dict[str, Any]:
        """Get the JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The absolute path to the file to read",
                },
                "offset": {
                    "type": "number",
                    "description": "The line number to start reading from (1-based, optional)",
                },
                "limit": {
                    "type": "number",
                    "description": "The number of lines to read (optional)",
                },
            },
            "required": ["file_path"],
        }

    async def execute(self, args: ToolCallArgs) -> ToolExecutionResult:
        """
        Execute file reading.

        Args:
            args: Tool call arguments containing the file path and options

        Returns:
            ToolExecutionResult with file contents
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

        offset = args.arguments.get("offset")
        limit = args.arguments.get("limit")

        try:
            # Check if file exists
            if not os.path.exists(file_path):
                output = self._create_error_output(
                    args.tool_call_id, f"Error: File not found: {file_path}"
                )
                execution_time = (time.time() - start_time) * 1000
                return self._create_result(
                    args.tool_call_id,
                    output,
                    execution_time,
                    {"error": "file_not_found"},
                )

            # Check if it's a file
            if not os.path.isfile(file_path):
                output = self._create_error_output(
                    args.tool_call_id, f"Error: Path is not a file: {file_path}"
                )
                execution_time = (time.time() - start_time) * 1000
                return self._create_result(
                    args.tool_call_id,
                    output,
                    execution_time,
                    {"error": "not_a_file"},
                )

            # Read file with encoding detection
            content = await self._read_file_async(file_path, offset, limit)

            execution_time = (time.time() - start_time) * 1000

            # Get file stats
            file_stat = os.stat(file_path)
            metadata = {
                "file_size": file_stat.st_size,
                "file_path": file_path,
            }
            if offset:
                metadata["offset"] = offset
            if limit:
                metadata["limit"] = limit

            output = self._create_success_output(args.tool_call_id, content)
            return self._create_result(args.tool_call_id, output, execution_time, metadata)

        except PermissionError:
            execution_time = (time.time() - start_time) * 1000
            output = self._create_error_output(
                args.tool_call_id, f"Error: Permission denied reading file: {file_path}"
            )
            return self._create_result(
                args.tool_call_id,
                output,
                execution_time,
                {"error": "permission_denied"},
            )
        except UnicodeDecodeError as e:
            execution_time = (time.time() - start_time) * 1000
            output = self._create_error_output(
                args.tool_call_id,
                f"Error: Unable to decode file as text: {file_path}\n{str(e)}",
            )
            return self._create_result(
                args.tool_call_id,
                output,
                execution_time,
                {"error": "decode_error"},
            )
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            output = self._create_error_output(
                args.tool_call_id, f"Error reading file: {str(e)}"
            )
            return self._create_result(
                args.tool_call_id,
                output,
                execution_time,
                {"error": "read_error", "exception": str(e)},
            )

    async def _read_file_async(
        self,
        file_path: str,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> str:
        """
        Read file contents asynchronously.

        Args:
            file_path: Path to the file
            offset: Starting line number (1-based)
            limit: Maximum number of lines to read

        Returns:
            File contents as string
        """
        import asyncio

        # Run file reading in a thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._read_file_sync, file_path, offset, limit
        )

    def _read_file_sync(
        self,
        file_path: str,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> str:
        """
        Read file contents synchronously.

        Args:
            file_path: Path to the file
            offset: Starting line number (1-based)
            limit: Maximum number of lines to read

        Returns:
            File contents as string
        """
        # Try different encodings
        encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]

        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    if offset is None and limit is None:
                        return f.read()

                    # Read with line range
                    lines = []
                    line_number = 0
                    start_line = (offset - 1) if offset else 0
                    end_line = start_line + limit if limit else None

                    for line in f:
                        if line_number >= start_line:
                            if end_line is not None and line_number >= end_line:
                                break
                            lines.append(line)
                        line_number += 1

                    return "".join(lines)
            except UnicodeDecodeError:
                continue

        # If all encodings fail, read as binary and decode with replacement
        with open(file_path, "rb") as f:
            content = f.read()
            return content.decode("utf-8", errors="replace")
