"""
CLI main entry point.

This module provides the main entry point for the CCMAS CLI,
using Click for command-line argument parsing.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import click

from ccmas import __version__
from ccmas.cli.config import CLIConfig, load_config, save_config, merge_config_with_args, get_config_path
from ccmas.cli.commands import interactive_mode, single_task, create_client


def check_and_setup_config() -> bool:
    """
    Check if configuration is complete and guide user through setup if needed.

    Returns:
        True if config is ready, False if user wants to exit
    """
    config_path = get_config_path()

    # If config exists and has api_key, we're good
    if config_path.exists():
        try:
            config = load_config(config_path)
            if config.api_key or config.backend in ("ollama",):
                return True
        except Exception:
            pass

    # Show setup wizard
    click.echo("\n=== CCMAS Setup Wizard ===\n")

    # Check for existing config
    if config_path.exists():
        click.echo(f"Found existing config at {config_path}")
        if not click.confirm("Do you want to reconfigure?"):
            return True

    # Workspace setup
    default_workspace = os.getcwd()
    workspace = click.prompt(
        "\nWorking directory",
        default=default_workspace,
        show_default=True,
    )

    # Backend selection
    click.echo("\nSelect backend:")
    click.echo("1. OpenAI (or OpenAI-compatible like MiniMax, DeepSeek)")
    click.echo("2. Ollama (local model)")
    click.echo("3. vLLM (local model)")

    backend_choice = click.prompt("Choice", default="1")

    if backend_choice == "1":
        backend = "openai"
        api_base = click.prompt(
            "API Base URL",
            default="https://api.openai.com/v1",
            show_default=True,
        )
        api_key = click.prompt("API Key", hide_input=True)
        model = click.prompt("Model", default="gpt-4", show_default=True)
    elif backend_choice == "2":
        backend = "ollama"
        api_base = None
        api_key = None
        model = click.prompt("Model", default="llama3", show_default=True)
    else:
        backend = "vllm"
        api_base = click.prompt(
            "API Base URL",
            default="http://localhost:8000/v1",
            show_default=True,
        )
        api_key = None
        model = click.prompt("Model", default="meta-llama/Llama-2-7b-chat-hf", show_default=True)

    # Create new config
    new_config = CLIConfig(
        workspace=workspace,
        backend=backend,
        api_base=api_base,
        api_key=api_key,
        model=model,
    )

    # Save config
    try:
        save_config(new_config)
        click.echo(f"\nConfiguration saved to {config_path}")
    except Exception as e:
        click.echo(f"Warning: Could not save config: {e}", err=True)

    return True


@click.command()
@click.option(
    "--workspace",
    "-w",
    default=None,
    help="Working directory for the CLI",
)
@click.option(
    "--model",
    "-m",
    default=None,
    help="Model to use (e.g., gpt-4, llama2)",
)
@click.option(
    "--api-base",
    "-b",
    default=None,
    help="Base URL for API calls (e.g., https://api.minimax.chat/v1)",
)
@click.option(
    "--api-key",
    "-k",
    default=None,
    help="API key for authentication",
)
@click.option(
    "--ollama",
    is_flag=True,
    default=False,
    help="Use Ollama backend",
)
@click.option(
    "--vllm",
    is_flag=True,
    default=False,
    help="Use vLLM backend",
)
@click.option(
    "--temperature",
    "-t",
    default=None,
    type=float,
    help="Sampling temperature (0-2)",
)
@click.option(
    "--max-tokens",
    default=None,
    type=int,
    help="Maximum tokens to generate",
)
@click.option(
    "--permission-mode",
    "-p",
    default=None,
    type=click.Choice(
        ["default", "acceptEdits", "bypassPermissions", "plan", "auto"],
        case_sensitive=False,
    ),
    help="Permission mode",
)
@click.option(
    "--config",
    "-c",
    "config_file",
    default=None,
    type=click.Path(exists=True),
    help="Path to configuration file",
)
@click.option(
    "--save-config",
    is_flag=True,
    default=False,
    help="Save current settings to config file",
)
@click.option(
    "--setup",
    is_flag=True,
    default=False,
    help="Run setup wizard to configure workspace and model",
)
@click.option(
    "--no-color",
    is_flag=True,
    default=False,
    help="Disable colored output",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable verbose output",
)
@click.option(
    "--version",
    is_flag=True,
    default=False,
    help="Show version and exit",
)
@click.option(
    "--output",
    "-o",
    default=None,
    type=click.Path(),
    help="Output file for single task mode",
)
@click.argument("task", required=False)
@click.pass_context
def main(
    ctx: click.Context,
    workspace: Optional[str],
    model: Optional[str],
    api_base: Optional[str],
    api_key: Optional[str],
    ollama: bool,
    vllm: bool,
    temperature: Optional[float],
    max_tokens: Optional[int],
    permission_mode: Optional[str],
    config_file: Optional[str],
    save_config: bool,
    setup: bool,
    no_color: bool,
    verbose: bool,
    version: bool,
    output: Optional[str],
    task: Optional[str],
) -> None:
    """
    CCMAS - Claude Code Multi-Agent System CLI

    A powerful multi-agent system command-line tool for building and managing
    AI-powered applications.

    Examples:

        # Start interactive mode
        ccmas

        # First-time setup
        ccmas --setup

        # Execute a single task
        ccmas "Write a Python function to calculate fibonacci numbers"

        # Use Ollama backend
        ccmas --ollama --model llama3

        # Use vLLM backend
        ccmas --vllm --model meta-llama/Llama-2-7b-chat-hf

        # Use custom OpenAI-compatible API (e.g., MiniMax, DeepSeek)
        ccmas --api-base https://api.minimax.chat/v1 --api-key YOUR_API_KEY --model MiniMax-text-01

        # Save output to file
        ccmas "Explain quantum computing" -o output.txt
    """
    # Show version and exit
    if version:
        click.echo(f"CCMAS version {__version__}")
        return

    # Run setup wizard if requested or no config exists
    config_path = get_config_path()
    if setup or not config_path.exists():
        if not check_and_setup_config():
            return

    # Load configuration
    try:
        config = load_config(config_file)
    except Exception as e:
        click.echo(f"Error loading configuration: {e}", err=True)
        sys.exit(1)

    # Determine backend from flags
    backend = None
    if ollama and vllm:
        click.echo("Error: Cannot use both --ollama and --vllm", err=True)
        sys.exit(1)
    elif ollama:
        backend = "ollama"
    elif vllm:
        backend = "vllm"

    # Determine workspace
    cwd = workspace or config.workspace or os.getcwd()

    # Merge command-line arguments with config
    config = merge_config_with_args(
        config,
        workspace=cwd,
        model=model,
        api_base=api_base,
        api_key=api_key,
        backend=backend,
        temperature=temperature,
        max_tokens=max_tokens,
        permission_mode=permission_mode,
        color_output=not no_color,
        verbose=verbose,
    )

    # Save config if requested
    if save_config:
        try:
            save_config(config)
            click.echo("Configuration saved successfully")
        except Exception as e:
            click.echo(f"Error saving configuration: {e}", err=True)
            sys.exit(1)

    # Change to workspace directory
    if config.workspace and os.path.isdir(config.workspace):
        try:
            os.chdir(config.workspace)
        except Exception as e:
            click.echo(f"Warning: Could not change to workspace: {e}", err=True)

    # Create LLM client
    try:
        client = create_client(config)
    except Exception as e:
        click.echo(f"Error creating client: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    # Run in appropriate mode
    try:
        if task:
            # Single task mode
            asyncio.run(single_task(config, client, task, output))
        else:
            # Interactive mode
            asyncio.run(interactive_mode(config, client))
    except KeyboardInterrupt:
        click.echo("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
