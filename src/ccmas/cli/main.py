"""
CLI main entry point.

This module provides the main entry point for the CCMAS CLI,
using Click for command-line argument parsing.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Optional

import click

from ccmas import __version__
from ccmas.cli.config import CLIConfig, load_config, save_config, merge_config_with_args
from ccmas.cli.commands import interactive_mode, single_task, create_client


@click.command()
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
    model: Optional[str],
    api_base: Optional[str],
    api_key: Optional[str],
    ollama: bool,
    vllm: bool,
    temperature: Optional[float],
    max_tokens: Optional[int],
    permission_mode: Optional[str],
    config_file: Optional[str],
    save_config_flag: bool,
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

        # Execute a single task
        ccmas "Write a Python function to calculate fibonacci numbers"

        # Use Ollama backend
        ccmas --ollama --model llama2

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
    
    # Merge command-line arguments with config
    config = merge_config_with_args(
        config,
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
    if save_config_flag:
        try:
            save_config(config)
            click.echo("Configuration saved successfully")
        except Exception as e:
            click.echo(f"Error saving configuration: {e}", err=True)
            sys.exit(1)
    
    # Create LLM client
    try:
        client = create_client(config)
    except Exception as e:
        click.echo(f"Error creating client: {e}", err=True)
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
