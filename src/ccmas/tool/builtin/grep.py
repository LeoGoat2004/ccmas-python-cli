"""
Grep tool for searching file contents.

This tool provides content search within files using regular expressions.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from ccmas.tool.base import Tool, ToolCallArgs, ToolExecutionResult


class GrepTool(Tool):
    """
    Tool for searching file contents.

    Provides text search within files using regular expressions:
    - Search files matching a glob pattern
    - Filter by file extensions
    - Show line numbers and context
    - Support for regex patterns
    """

    @property
    def name(self) -> str:
        """Get the tool name."""
        return "grep"

    @property
    def description(self) -> str:
        """Get the tool description."""
        return """Search for content in files using regular expressions.

This tool searches file contents for patterns:
- Uses regular expressions for powerful pattern matching
- Optionally filter by file glob pattern (e.g., *.py)
- Returns matching lines with line numbers
- Shows context lines around matches
- Supports case-sensitive and case-insensitive search

The path should be an absolute path or relative to the current working directory."""

    @property
    def parameters(self) -> Dict[str, Any]:
        """Get the JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "The regular expression pattern to search for",
                },
                "path": {
                    "type": "string",
                    "description": "The path to search in (file or directory)",
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Optional glob pattern to filter files (e.g., *.py, *.js)",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Whether the search is case-sensitive (default: true)",
                    "default": True,
                },
                "context": {
                    "type": "number",
                    "description": "Number of lines of context to show before and after matches (default: 0)",
                    "default": 0,
                },
                "max_results": {
                    "type": "number",
                    "description": "Maximum number of matching lines to return (default: 100)",
                    "default": 100,
                },
                "include_hidden": {
                    "type": "boolean",
                    "description": "Whether to include hidden files (default: false)",
                    "default": False,
                },
            },
            "required": ["pattern", "path"],
        }

    async def execute(self, args: ToolCallArgs) -> ToolExecutionResult:
        """
        Execute content search.

        Args:
            args: Tool call arguments containing search parameters

        Returns:
            ToolExecutionResult with search results
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

        path = args.arguments.get("path")
        if not path:
            output = self._create_error_output(
                args.tool_call_id, "Error: 'path' argument is required"
            )
            return self._create_result(
                args.tool_call_id, output, 0.0, {"error": "missing_path"}
            )

        # Validate pattern
        try:
            re.compile(pattern)
        except re.error as e:
            output = self._create_error_output(
                args.tool_call_id, f"Error: Invalid regex pattern: {str(e)}"
            )
            return self._create_result(
                args.tool_call_id, output, 0.0, {"error": "invalid_pattern"}
            )

        try:
            # Perform grep search
            results = await self._grep_async(
                pattern=pattern,
                path=path,
                file_pattern=args.arguments.get("file_pattern"),
                case_sensitive=args.arguments.get("case_sensitive", True),
                context=args.arguments.get("context", 0),
                max_results=args.arguments.get("max_results", 100),
                include_hidden=args.arguments.get("include_hidden", False),
            )

            execution_time = (time.time() - start_time) * 1000

            # Format output
            if results["matches"]:
                result_text = f"Found {results['total_matches']} match(es) in {results['files_searched']} file(s):\n\n"
                for file_path, lines in results["matches"].items():
                    result_text += f"{file_path}:\n"
                    for line_info in lines:
                        result_text += f"  {line_info['line_number']}: {line_info['content']}\n"
                    result_text += "\n"
            else:
                result_text = "No matches found."

            metadata = {
                "pattern": pattern,
                "path": path,
                "total_matches": results["total_matches"],
                "files_searched": results["files_searched"],
                "files_with_matches": len(results["matches"]),
            }

            output = self._create_success_output(args.tool_call_id, result_text)
            return self._create_result(args.tool_call_id, output, execution_time, metadata)

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            output = self._create_error_output(
                args.tool_call_id, f"Error searching for content: {str(e)}"
            )
            return self._create_result(
                args.tool_call_id,
                output,
                execution_time,
                {"error": "grep_error", "exception": str(e)},
            )

    async def _grep_async(
        self,
        pattern: str,
        path: str,
        file_pattern: Optional[str] = None,
        case_sensitive: bool = True,
        context: int = 0,
        max_results: int = 100,
        include_hidden: bool = False,
    ) -> Dict[str, Any]:
        """
        Perform grep search asynchronously.

        Args:
            pattern: Regular expression pattern
            path: Path to search in
            file_pattern: Optional glob pattern for files
            case_sensitive: Whether search is case-sensitive
            context: Lines of context around matches
            max_results: Maximum number of matches
            include_hidden: Whether to include hidden files

        Returns:
            Dictionary with search results
        """
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._grep_sync,
            pattern,
            path,
            file_pattern,
            case_sensitive,
            context,
            max_results,
            include_hidden,
        )

    def _grep_sync(
        self,
        pattern: str,
        path: str,
        file_pattern: Optional[str] = None,
        case_sensitive: bool = True,
        context: int = 0,
        max_results: int = 100,
        include_hidden: bool = False,
    ) -> Dict[str, Any]:
        """
        Perform grep search synchronously.

        Args:
            pattern: Regular expression pattern
            path: Path to search in
            file_pattern: Optional glob pattern for files
            case_sensitive: Whether search is case-sensitive
            context: Lines of context around matches
            max_results: Maximum number of matches
            include_hidden: Whether to include hidden files

        Returns:
            Dictionary with search results
        """
        # Compile regex
        flags = 0 if case_sensitive else re.IGNORECASE
        regex = re.compile(pattern, flags)

        # Determine files to search
        files_to_search = self._get_files_to_search(
            path, file_pattern, include_hidden
        )

        matches: Dict[str, List[Dict[str, Any]]] = {}
        total_matches = 0
        files_searched = 0

        for file_path in files_to_search:
            files_searched += 1

            # Skip if we've reached max_results
            if total_matches >= max_results:
                break

            file_matches = self._search_file(
                file_path, regex, context, max_results - total_matches
            )

            if file_matches:
                matches[file_path] = file_matches
                total_matches += len(file_matches)

        return {
            "matches": matches,
            "total_matches": total_matches,
            "files_searched": files_searched,
        }

    def _get_files_to_search(
        self, path: str, file_pattern: Optional[str], include_hidden: bool
    ) -> List[str]:
        """
        Get list of files to search.

        Args:
            path: Path to search in
            file_pattern: Optional glob pattern
            include_hidden: Whether to include hidden files

        Returns:
            List of file paths to search
        """
        import glob as glob_module

        files = []

        if os.path.isfile(path):
            files = [path]
        elif os.path.isdir(path):
            # Determine pattern
            if file_pattern:
                pattern = os.path.join(path, "**", file_pattern)
                files = glob_module.glob(pattern, recursive=True, include_hidden=include_hidden)
            else:
                # Search all files in directory
                for root, dirs, filenames in os.walk(path):
                    # Filter hidden directories if needed
                    if not include_hidden:
                        dirs[:] = [d for d in dirs if not d.startswith(".")]

                    for filename in filenames:
                        if not include_hidden and filename.startswith("."):
                            continue
                        files.append(os.path.join(root, filename))

        return files

    def _search_file(
        self,
        file_path: str,
        regex: re.Pattern,
        context: int = 0,
        max_matches: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Search a single file for pattern matches.

        Args:
            file_path: Path to the file
            regex: Compiled regular expression
            context: Lines of context around matches
            max_matches: Maximum matches to return

        Returns:
            List of match information dictionaries
        """
        matches = []

        try:
            # Try different encodings
            encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
            content = None

            for encoding in encodings:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        content = f.readlines()
                    break
                except UnicodeDecodeError:
                    continue

            if content is None:
                # Read as binary and decode with replacement
                with open(file_path, "rb") as f:
                    binary_content = f.read()
                    content = binary_content.decode("utf-8", errors="replace").splitlines(keepends=True)

            # Search each line
            for line_number, line in enumerate(content, start=1):
                match = regex.search(line)
                if match:
                    matches.append({
                        "line_number": line_number,
                        "content": line.rstrip("\n\r"),
                        "match_start": match.start(),
                        "match_end": match.end(),
                    })

                    if len(matches) >= max_matches:
                        break

        except Exception:
            # Skip files that can't be read
            pass

        return matches
