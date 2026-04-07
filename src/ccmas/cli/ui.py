"""
CLI UI rendering.

This module provides UI rendering utilities for the CCMAS CLI,
using the Rich library for beautiful terminal output.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Union

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.theme import Theme
from rich.live import Live

from ccmas.types.message import (
    AssistantMessage,
    Message,
    ToolCall,
    ToolMessage,
    UserMessage,
)


# Custom theme for CCMAS
CCMAS_THEME = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "red bold",
        "success": "green",
        "user": "blue",
        "assistant": "green",
        "tool": "magenta",
        "system": "dim",
        "highlight": "yellow bold",
        "prompt": "cyan bold",
    }
)


class ConsoleRenderer:
    """
    Console renderer for CLI output.
    
    Provides methods for rendering various types of messages,
    tool calls, progress indicators, and other UI elements.
    """
    
    def __init__(
        self,
        color_output: bool = True,
        show_timing: bool = True,
        show_token_usage: bool = True,
    ):
        """
        Initialize the console renderer.
        
        Args:
            color_output: Enable colored output
            show_timing: Show timing information
            show_token_usage: Show token usage information
        """
        self.console = Console(
            theme=CCMAS_THEME,
            force_terminal=color_output,
            no_color=not color_output,
        )
        self.show_timing = show_timing
        self.show_token_usage = show_token_usage
        self._start_time: Optional[float] = None
    
    def start_session(self) -> None:
        """Start a new session and record start time."""
        self._start_time = time.time()
    
    def render_welcome(self) -> None:
        """Render welcome message."""
        welcome_text = """
[bold cyan]CCMAS - Multi-Agent System[/bold cyan]
[dim]A powerful multi-agent system command-line tool[/dim]

Type [bold]help[/bold] for available commands
Type [bold]exit[/bold] or [bold]quit[/bold] to exit
"""
        self.console.print(Panel(welcome_text, border_style="cyan"))
    
    def render_message(
        self,
        message: Message,
        show_metadata: bool = False,
    ) -> None:
        """
        Render a message to the console.
        
        Args:
            message: Message to render
            show_metadata: Whether to show message metadata
        """
        if isinstance(message, UserMessage):
            self._render_user_message(message)
        elif isinstance(message, AssistantMessage):
            self._render_assistant_message(message, show_metadata)
        elif isinstance(message, ToolMessage):
            self._render_tool_message(message)
        else:
            self.console.print(f"[dim]{message}[/dim]")
    
    def _render_user_message(self, message: UserMessage) -> None:
        """Render a user message."""
        self.console.print()
        self.console.print("[bold blue]You:[/bold blue]")
        
        content = message.content
        if isinstance(content, str):
            self.console.print(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    self.console.print(block.get("text", ""))
                else:
                    self.console.print(str(block))
        self.console.print()
    
    def _render_assistant_message(
        self,
        message: AssistantMessage,
        show_metadata: bool = False,
    ) -> None:
        """Render an assistant message."""
        self.console.print()
        self.console.print("[bold green]Assistant:[/bold green]")
        
        # Render content
        if message.content:
            if isinstance(message.content, str):
                # Try to render as markdown
                try:
                    md = Markdown(message.content)
                    self.console.print(md)
                except Exception:
                    self.console.print(message.content)
            elif isinstance(message.content, list):
                for block in message.content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        try:
                            md = Markdown(text)
                            self.console.print(md)
                        except Exception:
                            self.console.print(text)
        
        # Render tool calls if present
        if message.tool_calls:
            for tool_call in message.tool_calls:
                self.render_tool_call(tool_call)
        
        # Show metadata if requested
        if show_metadata and (self.show_timing or self.show_token_usage):
            metadata_parts = []
            
            if self.show_token_usage and message.usage:
                prompt_tokens = message.usage.get("prompt_tokens", 0)
                completion_tokens = message.usage.get("completion_tokens", 0)
                total_tokens = message.usage.get("total_tokens", 0)
                metadata_parts.append(
                    f"Tokens: {prompt_tokens} prompt + {completion_tokens} completion = {total_tokens} total"
                )
            
            if self.show_timing and self._start_time:
                elapsed = time.time() - self._start_time
                metadata_parts.append(f"Time: {elapsed:.2f}s")
            
            if metadata_parts:
                self.console.print()
                self.console.print(f"[dim]{' | '.join(metadata_parts)}[/dim]")
        
        self.console.print()
    
    def _render_tool_message(self, message: ToolMessage) -> None:
        """Render a tool message."""
        self.console.print()
        self.console.print(f"[bold magenta]Tool Result ({message.name or 'unknown'}):[/bold magenta]")
        
        content = message.content
        if isinstance(content, str):
            # Try to parse as JSON for pretty printing
            try:
                import json
                data = json.loads(content)
                self._render_json(data)
            except (json.JSONDecodeError, ImportError):
                self.console.print(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    self._render_json(block)
                else:
                    self.console.print(str(block))
        
        self.console.print()
    
    def render_tool_call(
        self,
        tool_call: ToolCall,
        show_arguments: bool = True,
    ) -> None:
        """
        Render a tool call.
        
        Args:
            tool_call: Tool call to render
            show_arguments: Whether to show tool arguments
        """
        self.console.print()
        
        # Tool name
        tool_name = tool_call.function.get("name", "unknown")
        self.console.print(f"[bold magenta]Tool Call:[/bold magenta] [cyan]{tool_name}[/cyan]")
        
        # Tool arguments
        if show_arguments:
            arguments = tool_call.function.get("arguments", "{}")
            try:
                import json
                args_dict = json.loads(arguments) if isinstance(arguments, str) else arguments
                if args_dict:
                    self.console.print("[dim]Arguments:[/dim]")
                    self._render_json(args_dict)
            except (json.JSONDecodeError, ImportError):
                self.console.print(f"[dim]Arguments: {arguments}[/dim]")
        
        self.console.print()
    
    def render_progress(
        self,
        description: str = "Processing...",
        transient: bool = True,
    ) -> Progress:
        """
        Create and return a progress indicator.
        
        Args:
            description: Description text
            transient: Whether to remove progress when done
        
        Returns:
            Progress instance
        """
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=transient,
            console=self.console,
        )
    
    def render_spinner(
        self,
        text: str = "Thinking...",
    ) -> Live:
        """
        Create a spinner for long-running operations.
        
        Args:
            text: Text to display with spinner
        
        Returns:
            Live instance with spinner
        """
        from rich.spinner import Spinner
        
        spinner = Spinner("dots", text=text)
        return Live(spinner, console=self.console, transient=True)
    
    def render_error(self, message: str) -> None:
        """
        Render an error message.
        
        Args:
            message: Error message to render
        """
        self.console.print()
        self.console.print(Panel(
            f"[error]{message}[/error]",
            title="[bold red]Error[/bold red]",
            border_style="red",
        ))
        self.console.print()
    
    def render_warning(self, message: str) -> None:
        """
        Render a warning message.
        
        Args:
            message: Warning message to render
        """
        self.console.print()
        self.console.print(Panel(
            f"[warning]{message}[/warning]",
            title="[bold yellow]Warning[/bold yellow]",
            border_style="yellow",
        ))
        self.console.print()
    
    def render_success(self, message: str) -> None:
        """
        Render a success message.
        
        Args:
            message: Success message to render
        """
        self.console.print()
        self.console.print(f"[success][OK] {message}[/success]")
        self.console.print()
    
    def render_info(self, message: str) -> None:
        """
        Render an info message.
        
        Args:
            message: Info message to render
        """
        self.console.print(f"[info]Info: {message}[/info]")
    
    def render_table(
        self,
        title: str,
        headers: List[str],
        rows: List[List[Any]],
    ) -> None:
        """
        Render a table.
        
        Args:
            title: Table title
            headers: Column headers
            rows: Table rows
        """
        table = Table(title=title, show_header=True, header_style="bold cyan")
        
        for header in headers:
            table.add_column(header)
        
        for row in rows:
            table.add_row(*[str(cell) for cell in row])
        
        self.console.print(table)
    
    def _render_json(self, data: Any, indent: int = 2) -> None:
        """Render JSON data with syntax highlighting."""
        import json
        
        json_str = json.dumps(data, indent=indent, ensure_ascii=False)
        syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
        self.console.print(syntax)
    
    def render_code(
        self,
        code: str,
        language: str = "python",
        line_numbers: bool = False,
    ) -> None:
        """
        Render code with syntax highlighting.
        
        Args:
            code: Code to render
            language: Programming language
            line_numbers: Whether to show line numbers
        """
        syntax = Syntax(
            code,
            language,
            theme="monokai",
            line_numbers=line_numbers,
        )
        self.console.print(syntax)
    
    def render_divider(self, title: Optional[str] = None) -> None:
        """
        Render a divider line.
        
        Args:
            title: Optional title for the divider
        """
        if title:
            self.console.print(f"\n[dim]{'─' * 20} {title} {'─' * 20}[/dim]\n")
        else:
            self.console.print(f"\n[dim]{'─' * 50}[/dim]\n")
    
    def clear(self) -> None:
        """Clear the console screen."""
        self.console.clear()
    
    def print(self, message: str, **kwargs: Any) -> None:
        """
        Print a message to the console.
        
        Args:
            message: Message to print
            **kwargs: Additional arguments for console.print
        """
        self.console.print(message, **kwargs)
