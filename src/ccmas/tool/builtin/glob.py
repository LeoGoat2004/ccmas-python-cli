"""
Glob tool for searching files by pattern.

This tool provides file pattern matching using glob patterns.
"""

from __future__ import annotations

import glob as glob_module
import os
import time
from typing import Any, Dict, List

from ccmas.tool.base import Tool, ToolCallArgs, ToolExecutionResult


class GlobTool(Tool):
    """
    Tool for searching files by glob patterns.

    Provides file pattern matching with support for:
    - Basic glob patterns (*, ?)
    - Recursive directory matching (**)
    - Multiple pattern matching
    - File/directory type filtering
    """

    @property
    def name(self) -> str:
        """Get the tool name."""
        return "glob"

    @property
    def description(self) -> str:
        """Get the tool description."""
        return """Search for files matching a glob pattern.

This tool finds files by matching glob patterns:
- * matches any characters within a path segment
- ? matches any single character
- ** matches any characters across directories (recursive)
- [...] matches any character within brackets

Examples:
- **/*.py - all Python files recursively
- src/**/*.ts - all TypeScript files in src directory
- test_*.py - all Python files starting with test_

The path should be an absolute path or relative to the current working directory."""

    @property
    def parameters(self) -> Dict[str, Any]:
        """Get the JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "The glob pattern to match files against",
                },
                "base_dir": {
                    "type": "string",
                    "description": "The base directory to search in (optional, defaults to current working directory)",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to search recursively (default: true if pattern contains **)",
                    "default": True,
                },
                "max_results": {
                    "type": "number",
                    "description": "Maximum number of results to return (default: 1000)",
                    "default": 1000,
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, args: ToolCallArgs) -> ToolExecutionResult:
        """
        Execute file pattern matching.

        Args:
            args: Tool call arguments containing the pattern and options

        Returns:
            ToolExecutionResult with matched files
        """
        start_time = time.time()

        pattern = args.arguments.get("pattern")
        if not pattern:
            output = self._create_error_output(
                args.tool_call_id, "Error: 'pattern' argument is required"
            )
            return self._create_result(
                args.tool_call_id, output, 0.0, {"error": "missing_pattern"}
            )

        base_dir = args.arguments.get("base_dir")
        recursive = args.arguments.get("recursive", True)
        max_results = args.arguments.get("max_results", 1000)

        try:
            # Perform glob search
            matches = await self._glob_async(
                pattern=pattern,
                base_dir=base_dir,
                recursive=recursive,
                max_results=max_results,
            )

            execution_time = (time.time() - start_time) * 1000

            # Format output
            if matches:
                result_text = f"Found {len(matches)} matching file(s):\n\n"
                for match in matches:
                    result_text += f"{match}\n"
            else:
                result_text = "No files matching the pattern were found."

            metadata = {
                "pattern": pattern,
                "match_count": len(matches),
                "max_results": max_results,
            }
            if base_dir:
                metadata["base_dir"] = base_dir

            output = self._create_success_output(args.tool_call_id, result_text)
            return self._create_result(args.tool_call_id, output, execution_time, metadata)

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            output = self._create_error_output(
                args.tool_call_id, f"Error searching for files: {str(e)}"
            )
            return self._create_result(
                args.tool_call_id,
                output,
                execution_time,
                {"error": "glob_error", "exception": str(e)},
            )

    async def _glob_async(
        self,
        pattern: str,
        base_dir: str = None,
        recursive: bool = True,
        max_results: int = 1000,
    ) -> List[str]:
        """
        Perform glob search asynchronously.

        Args:
            pattern: The glob pattern
            base_dir: Base directory to search in
            recursive: Whether to search recursively
            max_results: Maximum number of results

        Returns:
            List of matching file paths
        """
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._glob_sync, pattern, base_dir, recursive, max_results
        )

    def _glob_sync(
        self,
        pattern: str,
        base_dir: str = None,
        recursive: bool = True,
        max_results: int = 1000,
    ) -> List[str]:
        """
        Perform glob search synchronously.

        Args:
            pattern: The glob pattern
            base_dir: Base directory to search in
            recursive: Whether to search recursively
            max_results: Maximum number of results

        Returns:
            List of matching file paths
        """
        # Determine if recursive based on pattern
        is_recursive = "**" in pattern

        # Handle base_dir
        if base_dir:
            if not os.path.isabs(base_dir):
                base_dir = os.path.abspath(base_dir)
            # Prepend base_dir to pattern
            if not pattern.startswith(os.sep):
                pattern = os.path.join(base_dir, pattern)
        else:
            # Make pattern absolute
            if not os.path.isabs(pattern):
                pattern = os.path.abspath(pattern)

        # Perform glob search
        if is_recursive:
            # For recursive patterns, use glob with recursive=True
            matches = glob_module.glob(pattern, recursive=True, include_hidden=False)
        else:
            matches = glob_module.glob(pattern, recursive=False, include_hidden=False)

        # Filter to only files (not directories)
        file_matches = []
        for match in matches:
            if os.path.isfile(match):
                file_matches.append(match)
            # Skip directories

        # Sort matches for consistent output
        file_matches.sort()

        # Apply max_results limit
        if len(file_matches) > max_results:
            file_matches = file_matches[:max_results]

        return file_matches
