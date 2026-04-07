"""
Edit tool for editing file contents.

This tool provides file editing operations including replacement,
insertion, and deletion of lines.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from ccmas.tool.base import Tool, ToolCallArgs, ToolExecutionResult


class EditTool(Tool):
    """
    Tool for editing file contents.

    Provides line-based file editing with support for:
    - Replacing specified lines
    - Inserting content at specific positions
    - Deleting specified lines
    - Creating backups before editing
    """

    @property
    def name(self) -> str:
        """Get the tool name."""
        return "edit"

    @property
    def description(self) -> str:
        """Get the tool description."""
        return """Edit a file by replacing, inserting, or deleting lines.

This tool modifies file contents by performing line-based operations:
- Replace: Replace specific line(s) with new content
- Insert: Insert content at a specific line position
- Delete: Remove specific line(s)

The file path must be an absolute path. Use with caution as changes are
applied directly to the file."""

    @property
    def parameters(self) -> Dict[str, Any]:
        """Get the JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The absolute path to the file to edit",
                },
                "operation": {
                    "type": "string",
                    "enum": ["replace", "insert", "delete"],
                    "description": "The type of edit operation to perform",
                },
                "start_line": {
                    "type": "number",
                    "description": "The starting line number for the operation (1-based, inclusive)",
                },
                "end_line": {
                    "type": "number",
                    "description": "The ending line number for replace/delete operations (1-based, inclusive). If not provided, only start_line is affected.",
                },
                "new_content": {
                    "type": "string",
                    "description": "The new content to insert or replace with",
                },
            },
            "required": ["file_path", "operation"],
        }

    async def execute(self, args: ToolCallArgs) -> ToolExecutionResult:
        """
        Execute file editing.

        Args:
            args: Tool call arguments containing file path and edit parameters

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

        operation = args.arguments.get("operation")
        if not operation:
            output = self._create_error_output(
                args.tool_call_id, "Error: 'operation' argument is required"
            )
            return self._create_result(
                args.tool_call_id, output, 0.0, {"error": "missing_operation"}
            )

        if operation not in ["replace", "insert", "delete"]:
            output = self._create_error_output(
                args.tool_call_id,
                f"Error: Invalid operation '{operation}'. Must be 'replace', 'insert', or 'delete'",
            )
            return self._create_result(
                args.tool_call_id, output, 0.0, {"error": "invalid_operation"}
            )

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

            # Perform the edit operation
            result = await self._edit_file_async(
                file_path=file_path,
                operation=operation,
                start_line=args.arguments.get("start_line"),
                end_line=args.arguments.get("end_line"),
                new_content=args.arguments.get("new_content"),
            )

            execution_time = (time.time() - start_time) * 1000

            if result["success"]:
                output = self._create_success_output(
                    args.tool_call_id,
                    f"Successfully performed {operation} on {file_path}\n{result.get('summary', '')}",
                )

                return self._create_result(
                    args.tool_call_id, output, execution_time, result.get("metadata", {})
                )
            else:
                output = self._create_error_output(
                    args.tool_call_id, result.get("error", "Unknown error")
                )
                return self._create_result(
                    args.tool_call_id,
                    output,
                    execution_time,
                    {"error": result.get("error_type", "edit_error")},
                )

        except PermissionError:
            execution_time = (time.time() - start_time) * 1000
            output = self._create_error_output(
                args.tool_call_id, f"Error: Permission denied editing file: {file_path}"
            )
            return self._create_result(
                args.tool_call_id,
                output,
                execution_time,
                {"error": "permission_denied"},
            )
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            output = self._create_error_output(
                args.tool_call_id, f"Error editing file: {str(e)}"
            )
            return self._create_result(
                args.tool_call_id,
                output,
                execution_time,
                {"error": "edit_error", "exception": str(e)},
            )

    async def _edit_file_async(
        self,
        file_path: str,
        operation: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        new_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Edit file contents asynchronously.

        Args:
            file_path: Path to the file
            operation: The operation to perform
            start_line: Starting line number (1-based)
            end_line: Ending line number (1-based)
            new_content: New content for replace/insert

        Returns:
            Result dictionary with success status and details
        """
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._edit_file_sync,
            file_path,
            operation,
            start_line,
            end_line,
            new_content,
        )

    def _edit_file_sync(
        self,
        file_path: str,
        operation: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        new_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Edit file contents synchronously.

        Args:
            file_path: Path to the file
            operation: The operation to perform
            start_line: Starting line number (1-based)
            end_line: Ending line number (1-based)
            new_content: New content for replace/insert

        Returns:
            Result dictionary with success status and details
        """
        # Read file
        encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
        lines: List[str] = []

        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    lines = f.readlines()
                break
            except UnicodeDecodeError:
                continue

        # If all encodings fail, read as binary
        if not lines:
            with open(file_path, "rb") as f:
                content = f.read().decode("utf-8", errors="replace")
                lines = content.splitlines(keepends=True)

        total_lines = len(lines)

        # Validate line numbers
        if start_line is not None:
            if start_line < 1 or start_line > total_lines:
                return {
                    "success": False,
                    "error": f"Error: start_line {start_line} is out of range (file has {total_lines} lines)",
                    "error_type": "invalid_line_number",
                }

        if end_line is not None:
            if end_line < 1 or end_line > total_lines:
                return {
                    "success": False,
                    "error": f"Error: end_line {end_line} is out of range (file has {total_lines} lines)",
                    "error_type": "invalid_line_number",
                }

        if start_line is not None and end_line is not None:
            if start_line > end_line:
                return {
                    "success": False,
                    "error": f"Error: start_line ({start_line}) cannot be greater than end_line ({end_line})",
                    "error_type": "invalid_range",
                }

        # Perform operation
        if operation == "replace":
            if start_line is None:
                return {
                    "success": False,
                    "error": "Error: 'start_line' is required for replace operation",
                    "error_type": "missing_parameter",
                }

            if new_content is None:
                return {
                    "success": False,
                    "error": "Error: 'new_content' is required for replace operation",
                    "error_type": "missing_parameter",
                }

            # Convert to 0-based index
            start_idx = start_line - 1
            end_idx = end_line if end_line else start_line

            # Ensure we have newlines in new_content
            new_lines = new_content.splitlines(keepends=True)
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines[-1] += "\n"
            if not new_lines:
                new_lines = ["\n"]

            # Replace lines
            replaced_lines = lines[start_idx:end_idx]
            lines[start_idx:end_idx] = new_lines

            summary = f"Replaced lines {start_line}-{end_idx} with {len(new_lines)} line(s)"

        elif operation == "insert":
            if start_line is None:
                return {
                    "success": False,
                    "error": "Error: 'start_line' is required for insert operation",
                    "error_type": "missing_parameter",
                }

            if new_content is None:
                return {
                    "success": False,
                    "error": "Error: 'new_content' is required for insert operation",
                    "error_type": "missing_parameter",
                }

            # Convert to 0-based index (insert BEFORE the specified line)
            insert_idx = start_line - 1

            # Ensure we have newlines in new_content
            new_lines = new_content.splitlines(keepends=True)
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines[-1] += "\n"
            if not new_lines:
                new_lines = ["\n"]

            # Insert lines
            for i, new_line in enumerate(new_lines):
                lines.insert(insert_idx + i, new_line)

            num_lines_inserted = len(new_lines)
            summary = f"Inserted {num_lines_inserted} line(s) before line {start_line}"

        elif operation == "delete":
            if start_line is None:
                return {
                    "success": False,
                    "error": "Error: 'start_line' is required for delete operation",
                    "error_type": "missing_parameter",
                }

            # Convert to 0-based index
            start_idx = start_line - 1
            end_idx = end_line if end_line else start_line

            # Delete lines
            deleted_lines = lines[start_idx:end_idx]
            del lines[start_idx:end_idx]

            summary = f"Deleted lines {start_line}-{end_idx} ({len(deleted_lines)} line(s))"

        else:
            return {
                "success": False,
                "error": f"Unknown operation: {operation}",
                "error_type": "invalid_operation",
            }

        # Write file
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            f.writelines(lines)

        # Ensure trailing newline
        if lines and not lines[-1].endswith("\n"):
            with open(file_path, "a", encoding="utf-8") as f:
                f.write("\n")

        return {
            "success": True,
            "summary": summary,
            "metadata": {
                "operation": operation,
                "total_lines": len(lines),
                "file_path": file_path,
            },
        }
