"""
CLI command implementations.

This module provides command implementations for the CCMAS CLI,
including interactive mode and single task execution.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.prompt import Prompt, Confirm

from ccmas.cli.config import CLIConfig
from ccmas.cli.ui import ConsoleRenderer
from ccmas.llm.client import LLMClient, OpenAIClient
from ccmas.llm.ollama import OllamaAdapter
from ccmas.llm.vllm import VLLMAdapter
from ccmas.types.message import (
    AssistantMessage,
    Message,
    ToolMessage,
    UserMessage,
    create_user_message,
    create_tool_message,
)
from ccmas.prompt.system import build_system_prompt
from ccmas.types.tool import ToolDefinition
from ccmas.tool.base import ToolCallArgs
from ccmas.tool.builtin import register_builtin_tools
from ccmas.tool.registry import get_registry, register_tool as register_tool_to_registry
from ccmas.permission.mode import PermissionMode, PermissionContext
from ccmas.permission.checker import PermissionChecker


class CommandHandler:
    """
    Handler for CLI commands.
    
    Provides methods for processing user commands and managing
    the conversation flow.
    """
    
    def __init__(
        self,
        config: CLIConfig,
        renderer: ConsoleRenderer,
        client: LLMClient,
    ):
        """
        Initialize command handler.
        
        Args:
            config: CLI configuration
            renderer: Console renderer
            client: LLM client
        """
        self.config = config
        self.renderer = renderer
        self.client = client
        self.messages: List[Message] = []
        self.permission_checker = PermissionChecker(
            context=PermissionContext(mode=PermissionMode.from_string(config.permission_mode))
        )
        self._running = True
        self._system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """Build the system prompt with workspace information."""
        cwd = self.config.workspace or str(Path.cwd())
        is_git = (Path(cwd) / ".git").exists()

        return build_system_prompt(
            cwd=cwd,
            is_git=is_git,
        )

    def is_running(self) -> bool:
        """Check if the handler is still running."""
        return self._running
    
    async def handle_command(self, command: str) -> None:
        """
        Handle a user command.
        
        Args:
            command: User command string
        """
        command = command.strip()
        
        # Check for special commands
        if command in ("/exit", "/quit", "exit", "quit"):
            self._running = False
            self.renderer.render_info("Goodbye!")
            return
        
        if command in ("/help", "help"):
            self._show_help()
            return
        
        if command in ("/clear", "clear"):
            self.messages.clear()
            self.renderer.clear()
            self.renderer.render_success("Conversation cleared")
            return
        
        if command.startswith("/config"):
            self._handle_config_command(command)
            return
        
        if command.startswith("/save"):
            self._handle_save_command(command)
            return
        
        if command.startswith("/load"):
            self._handle_load_command(command)
            return
        
        if command.startswith("/history"):
            self._handle_history_command(command)
            return
        
        # Treat as regular message to the assistant
        await self._process_message(command)
    
    def _show_help(self) -> None:
        """Show help message."""
        help_text = """
[bold]Available Commands:[/bold]

[cyan]General:[/cyan]
  help, /help          Show this help message
  exit, /exit          Exit the CLI
  quit, /quit          Exit the CLI
  clear, /clear        Clear conversation history

[cyan]Configuration:[/cyan]
  /config              Show current configuration
  /config set <key> <value>   Set a configuration value
  /config save         Save configuration to file

[cyan]Conversation:[/cyan]
  /save [filename]     Save conversation to file
  /load <filename>     Load conversation from file
  /history             Show conversation history

[cyan]Tips:[/cyan]
  - Type your message directly to chat with the assistant
  - Use Tab for auto-completion (if available)
  - Press Ctrl+C to interrupt a long response
"""
        self.renderer.console.print(help_text)
    
    def _handle_config_command(self, command: str) -> None:
        """Handle configuration commands."""
        parts = command.split(maxsplit=3)
        
        if len(parts) == 1:
            # Show current config
            config_dict = self.config.model_dump(exclude_none=True)
            config_dict.pop("api_key", None)  # Don't show API key
            self.renderer.console.print("\n[bold]Current Configuration:[/bold]\n")
            self.renderer._render_json(config_dict)
            return
        
        if parts[1] == "set" and len(parts) >= 4:
            # Set config value
            key = parts[2]
            value = parts[3]
            
            try:
                # Try to parse as JSON for complex values
                try:
                    parsed_value = json.loads(value)
                except json.JSONDecodeError:
                    parsed_value = value
                
                # Update config
                if hasattr(self.config, key):
                    setattr(self.config, key, parsed_value)
                    self.renderer.render_success(f"Set {key} = {parsed_value}")
                else:
                    self.renderer.render_error(f"Unknown configuration key: {key}")
            except Exception as e:
                self.renderer.render_error(f"Failed to set configuration: {e}")
            return
        
        if parts[1] == "save":
            # Save config to file
            try:
                from ccmas.cli.config import save_config
                save_config(self.config)
                self.renderer.render_success("Configuration saved")
            except Exception as e:
                self.renderer.render_error(f"Failed to save configuration: {e}")
            return
        
        self.renderer.render_error("Invalid config command. Use: /config [set <key> <value> | save]")
    
    def _handle_save_command(self, command: str) -> None:
        """Handle save conversation command."""
        parts = command.split(maxsplit=1)
        filename = parts[1] if len(parts) > 1 else "conversation.json"
        
        if not filename.endswith(".json"):
            filename += ".json"
        
        try:
            # Convert messages to serializable format
            messages_data = []
            for msg in self.messages:
                msg_dict = msg.model_dump()
                messages_data.append(msg_dict)
            
            with open(filename, "w", encoding="utf-8") as f:
                json.dump({
                    "messages": messages_data,
                    "config": self.config.model_dump(exclude_none=True),
                }, f, indent=2, ensure_ascii=False)
            
            self.renderer.render_success(f"Conversation saved to {filename}")
        except Exception as e:
            self.renderer.render_error(f"Failed to save conversation: {e}")
    
    def _handle_load_command(self, command: str) -> None:
        """Handle load conversation command."""
        parts = command.split(maxsplit=1)
        
        if len(parts) < 2:
            self.renderer.render_error("Please specify a filename: /load <filename>")
            return
        
        filename = parts[1]
        if not filename.endswith(".json"):
            filename += ".json"
        
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Load messages
            self.messages.clear()
            for msg_data in data.get("messages", []):
                role = msg_data.get("role")
                if role == "user":
                    self.messages.append(UserMessage(**msg_data))
                elif role == "assistant":
                    self.messages.append(AssistantMessage(**msg_data))
                elif role == "tool":
                    self.messages.append(ToolMessage(**msg_data))
            
            self.renderer.render_success(f"Loaded {len(self.messages)} messages from {filename}")
        except Exception as e:
            self.renderer.render_error(f"Failed to load conversation: {e}")
    
    def _handle_history_command(self, command: str) -> None:
        """Handle history command."""
        if not self.messages:
            self.renderer.render_info("No conversation history")
            return
        
        self.renderer.render_divider("Conversation History")
        
        for i, msg in enumerate(self.messages, 1):
            role = msg.role if hasattr(msg, "role") else "unknown"
            content = msg.content if hasattr(msg, "content") else str(msg)
            
            if isinstance(content, str):
                preview = content[:100] + "..." if len(content) > 100 else content
            else:
                preview = f"<{type(content).__name__}>"
            
            self.renderer.console.print(f"[dim]{i}.[/dim] [{role}] {preview}")
    
    async def _process_message(self, user_input: str) -> None:
        """
        Process a user message and get assistant response.
        Handles tool call loops properly.

        Args:
            user_input: User's input text
        """
        # Create user message
        user_message = create_user_message(user_input)
        self.messages.append(user_message)

        # Show user message
        self.renderer.render_message(user_message)

        # Process in a loop to handle tool calls
        max_iterations = 10  # Prevent infinite loops
        for _ in range(max_iterations):
            # Get assistant response
            try:
                with self.renderer.render_spinner("Thinking..."):
                    response = await self.client.complete(
                        messages=self.messages,
                        system=self._system_prompt,
                    )

                # Add to message history
                self.messages.append(response)

                # Show assistant response
                self.renderer.render_message(response, show_metadata=True)

                # Handle tool calls if present
                if not response.tool_calls:
                    break  # No more tool calls, we're done

                await self._handle_tool_calls(response.tool_calls)

            except KeyboardInterrupt:
                self.renderer.render_warning("Request interrupted by user")
                break
            except Exception as e:
                self.renderer.render_error(f"Failed to get response: {e}")
                if self.config.verbose:
                    import traceback
                    self.renderer.console.print(traceback.format_exc())
                break
    
    async def _handle_tool_calls(self, tool_calls: List[Any]) -> None:
        """
        Handle tool calls from the assistant.
        
        Args:
            tool_calls: List of tool calls to execute
        """
        for tool_call in tool_calls:
            tool_name = tool_call.function.get("name", "unknown")
            arguments = tool_call.function.get("arguments", "{}")
            
            # Parse arguments
            try:
                args_dict = json.loads(arguments) if isinstance(arguments, str) else arguments
            except json.JSONDecodeError:
                args_dict = {}
            
            # Check permission
            permission = self.permission_checker.check_tool_permission(tool_name, args_dict)
            
            if not permission.is_allowed:
                if permission.needs_user_input:
                    # Ask user for permission
                    confirmed = Confirm.ask(
                        f"Allow tool call: {tool_name}?",
                        default=True,
                    )
                    if not confirmed:
                        # Send denial message
                        tool_message = create_tool_message(
                            tool_call_id=tool_call.id,
                            content="Tool call denied by user",
                            name=tool_name,
                        )
                        self.messages.append(tool_message)
                        continue
                else:
                    # Permission denied
                    tool_message = create_tool_message(
                        tool_call_id=tool_call.id,
                        content=f"Tool call denied: {permission.reason}",
                        name=tool_name,
                    )
                    self.messages.append(tool_message)
                    continue
            
            # Execute tool
            try:
                result = await self._execute_tool(tool_name, args_dict)
                
                # Create tool result message
                tool_message = create_tool_message(
                    tool_call_id=tool_call.id,
                    content=result,
                    name=tool_name,
                )
                self.messages.append(tool_message)
                
                # Show tool result
                self.renderer.render_message(tool_message)
            
            except Exception as e:
                error_message = create_tool_message(
                    tool_call_id=tool_call.id,
                    content=f"Error executing tool: {e}",
                    name=tool_name,
                )
                self.messages.append(error_message)
                self.renderer.render_error(f"Tool execution failed: {e}")
    
    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute a tool and return the result.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            Tool execution result as string
        """
        from uuid import uuid4

        # Get tool from registry
        tool_registry = get_registry()
        tool = tool_registry.get(tool_name)

        if tool is None:
            return f"Error: Tool '{tool_name}' not found"

        # Execute tool with proper ToolCallArgs
        try:
            tool_call_id = arguments.pop("_tool_call_id", str(uuid4()))
            tool_args = ToolCallArgs(tool_call_id=tool_call_id, arguments=arguments)
            result = await tool.execute(tool_args)
            # Extract content from ToolExecutionResult
            if hasattr(result, 'output'):
                output = result.output
                if hasattr(output, 'content'):
                    return str(output.content)
                return str(output)
            return str(result)
        except Exception as e:
            return f"Error: {e}"


async def interactive_mode(
    config: CLIConfig,
    client: LLMClient,
) -> None:
    """
    Run interactive mode.
    
    Provides a REPL-style interface for chatting with the assistant.
    
    Args:
        config: CLI configuration
        client: LLM client
    """
    # Create renderer
    renderer = ConsoleRenderer(
        color_output=config.color_output,
        show_timing=config.show_timing,
        show_token_usage=config.show_token_usage,
    )
    
    # Create command handler
    handler = CommandHandler(config, renderer, client)
    
    # Show welcome message
    renderer.render_welcome()
    renderer.start_session()
    
    # Main loop
    while handler.is_running():
        try:
            # Get user input
            user_input = Prompt.ask("[prompt]You[/prompt]")
            
            if not user_input.strip():
                continue
            
            # Handle command
            await handler.handle_command(user_input)
        
        except KeyboardInterrupt:
            renderer.console.print()
            renderer.render_info("Press Ctrl+C again or type 'exit' to quit")
        
        except EOFError:
            # Handle Ctrl+D
            renderer.console.print()
            handler._running = False
            renderer.render_info("Goodbye!")


async def single_task(
    config: CLIConfig,
    client: LLMClient,
    task: str,
    output_file: Optional[str] = None,
) -> None:
    """
    Execute a single task and exit.

    Args:
        config: CLI configuration
        client: LLM client
        task: Task to execute
        output_file: Optional file to save output
    """
    # Create renderer
    renderer = ConsoleRenderer(
        color_output=config.color_output,
        show_timing=config.show_timing,
        show_token_usage=config.show_token_usage,
    )

    # Create command handler (which properly handles tool calls)
    handler = CommandHandler(config, renderer, client)

    renderer.start_session()

    try:
        # Process the task (handles tool calls properly)
        await handler.handle_command(task)

        # Save to file if requested
        if output_file:
            # Get all assistant messages
            content_parts = []
            for msg in handler.messages:
                if isinstance(msg, AssistantMessage) and msg.content:
                    content_parts.append(msg.content)
            content = "\n\n".join(content_parts)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(content)
            renderer.render_success(f"Output saved to {output_file}")

    except Exception as e:
        renderer.render_error(f"Failed to execute task: {e}")
        if config.verbose:
            import traceback
            renderer.console.print(traceback.format_exc())
        sys.exit(1)


def create_client(config: CLIConfig) -> LLMClient:
    """
    Create an LLM client based on configuration.

    Args:
        config: CLI configuration

    Returns:
        LLM client instance
    """
    # Register built-in tools first
    register_builtin_tools()

    # Get tools from registry
    tool_registry = get_registry()
    tools = tool_registry.get_all_definitions()
    
    # Determine base URL based on backend
    base_url = config.get_api_base()
    
    if config.backend == "ollama":
        # Use Ollama's OpenAI-compatible endpoint
        base_url = base_url or OllamaAdapter.get_default_endpoint()
    elif config.backend == "vllm":
        # Use vLLM's OpenAI-compatible endpoint
        base_url = base_url or VLLMAdapter.get_default_endpoint()
    
    # All backends use OpenAIClient since they provide OpenAI-compatible APIs
    return OpenAIClient(
        model=config.model,
        api_key=config.api_key,
        base_url=base_url,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        tools=tools,
    )
