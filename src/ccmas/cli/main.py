"""
CCMAS CLI - Claude Code Multi-Agent System

A Python implementation of Claude Code's MAS core functionality.
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


def run_setup_wizard(force: bool = False) -> Optional[CLIConfig]:
    """
    Run the setup wizard to configure CCMAS.

    Args:
        force: If True, always show wizard even if config exists

    Returns:
        CLIConfig if setup completed, None if user cancelled
    """
    config_path = get_config_path()

    click.echo("\n" + "=" * 60)
    click.echo("  CCMAS Setup Wizard")
    click.echo("=" * 60)

    # Check existing config
    existing_config = None
    if config_path.exists():
        try:
            existing_config = load_config(config_path)
            if not force and existing_config.api_key:
                click.echo(f"\nFound existing config at {config_path}")
                click.echo(f"Model: {existing_config.model}")
                click.echo(f"Backend: {existing_config.backend}")
                if click.confirm("\nUse existing configuration?"):
                    return existing_config
        except Exception:
            existing_config = None

    click.echo("\nLet's configure CCMAS for first-time use.\n")

    # Workspace setup
    default_workspace = os.getcwd()
    workspace = click.prompt(
        "\n1. Working directory",
        default=default_workspace,
        show_default=True,
    )

    # Backend selection
    click.echo("\n2. Select backend:")
    click.echo("   [1] OpenAI (or OpenAI-compatible like MiniMax, DeepSeek)")
    click.echo("   [2] Ollama (local model)")
    click.echo("   [3] vLLM (local model)")

    backend_choice = click.prompt("\n   Enter choice", default="1")

    if backend_choice == "1":
        backend = "openai"
        api_base = click.prompt(
            "\n3. API Base URL",
            default="https://api.openai.com/v1",
            show_default=True,
        )
        api_key = click.prompt(
            "\n4. API Key",
            hide_input=True,
            confirmation_prompt=True,
        )
        model = click.prompt(
            "\n5. Model name",
            default="gpt-4",
            show_default=True,
        )
    elif backend_choice == "2":
        backend = "ollama"
        api_base = None
        api_key = None
        model = click.prompt(
            "\n3. Model name (e.g., llama3, mistral)",
            default="llama3",
            show_default=True,
        )
    else:
        backend = "vllm"
        api_base = click.prompt(
            "\n3. API Base URL",
            default="http://localhost:8000/v1",
            show_default=True,
        )
        api_key = None
        model = click.prompt(
            "\n4. Model name",
            default="meta-llama/Llama-2-7b-chat-hf",
            show_default=True,
        )

    # Create config
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
        click.echo(f"\n[OK] Configuration saved to {config_path}")
    except Exception as e:
        click.echo(f"\n[WARNING] Could not save config: {e}", err=True)
        click.echo("Config will not persist after this session.")

    return new_config


@click.command()
@click.option(
    "--workspace", "-w", default=None,
    help="Working directory for the CLI"
)
@click.option(
    "--model", "-m", default=None,
    help="Model to use (e.g., gpt-4, llama3)"
)
@click.option(
    "--api-base", "-b", default=None,
    help="API base URL (e.g., https://api.minimax.chat/v1)"
)
@click.option(
    "--api-key", "-k", default=None,
    help="API key for authentication"
)
@click.option(
    "--ollama", is_flag=True, default=False,
    help="Use Ollama backend"
)
@click.option(
    "--vllm", is_flag=True, default=False,
    help="Use vLLM backend"
)
@click.option(
    "--temperature", "-t", default=None, type=float,
    help="Sampling temperature (0-2)"
)
@click.option(
    "--max-tokens", default=None, type=int,
    help="Maximum tokens to generate"
)
@click.option(
    "--permission-mode", "-p", default=None,
    type=click.Choice(["default", "acceptEdits", "bypassPermissions", "plan", "auto"]),
    help="Permission mode"
)
@click.option(
    "--config", "-c", "config_file", default=None,
    type=click.Path(exists=True),
    help="Path to configuration file"
)
@click.option(
    "--setup", is_flag=True, default=False,
    help="Run setup wizard"
)
@click.option(
    "--reset", is_flag=True, default=False,
    help="Reset configuration and run setup wizard"
)
@click.option(
    "--no-color", is_flag=True, default=False,
    help="Disable colored output"
)
@click.option(
    "--verbose", "-v", is_flag=True, default=False,
    help="Enable verbose output"
)
@click.option(
    "--version", is_flag=True, default=False,
    help="Show version"
)
@click.option(
    "--output", "-o", default=None, type=click.Path(),
    help="Output file for single task mode"
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
    setup: bool,
    reset: bool,
    no_color: bool,
    verbose: bool,
    version: bool,
    output: Optional[str],
    task: Optional[str],
) -> None:
    """
    CCMAS - Claude Code Multi-Agent System CLI

    A powerful multi-agent CLI that 1:1 replicates Claude Code's MAS core functionality.

    Examples:

        ccmas                                    # Start interactive mode
        ccmas --setup                            # Run setup wizard
        ccmas "Write a fibonacci function"      # Execute single task
        ccmas --ollama --model llama3            # Use Ollama
        ccmas --api-base <url> --api-key <key>   # Use custom OpenAI-compatible API
    """
    # Show version and exit
    if version:
        click.echo(f"CCMAS version {__version__}")
        return

    # Handle reset
    if reset:
        config_path = get_config_path()
        if config_path.exists():
            try:
                os.remove(config_path)
                click.echo(f"Configuration file removed: {config_path}")
            except Exception:
                pass
        setup = True

    # Determine config source
    config_path = get_config_path() if not config_file else Path(config_file)
    config: Optional[CLIConfig] = None

    # Try to load existing config
    if config_path.exists():
        try:
            config = load_config(config_path)
        except Exception as e:
            if verbose:
                click.echo(f"Warning: Failed to load config: {e}", err=True)

    # Run setup if needed
    if setup or config is None or config.api_key is None:
        if not task and not setup:
            # No task provided and no config - offer setup
            click.echo("\nCCMAS requires configuration to run.")
            if click.confirm("Would you like to run the setup wizard now?"):
                setup = True
            else:
                click.echo("\nRun 'ccmas --setup' to configure later.")
                return

        config = run_setup_wizard(force=True)
        if config is None:
            click.echo("\nSetup cancelled.")
            return

    # Determine backend from flags
    backend = None
    if ollama and vllm:
        click.echo("Error: Cannot use both --ollama and --vllm", err=True)
        sys.exit(1)
    elif ollama:
        backend = "ollama"
    elif vllm:
        backend = "vllm"

    # Override config with command-line arguments
    cwd = workspace or config.workspace or os.getcwd()

    # Handle API key from command line
    final_api_key = api_key or config.api_key
    if not final_api_key and config.backend == "openai":
        click.echo("\nError: API key is required for OpenAI backend.", err=True)
        click.echo("Run 'ccmas --setup' to configure or use --api-key argument.")
        sys.exit(1)

    config = merge_config_with_args(
        config,
        workspace=cwd,
        model=model,
        api_base=api_base,
        api_key=final_api_key,
        backend=backend,
        temperature=temperature,
        max_tokens=max_tokens,
        permission_mode=permission_mode,
        color_output=not no_color,
        verbose=verbose,
    )

    # Change to workspace
    if config.workspace and os.path.isdir(config.workspace):
        try:
            os.chdir(config.workspace)
        except Exception as e:
            click.echo(f"Warning: Could not change to workspace: {e}", err=True)

    # Create LLM client
    try:
        client = create_client(config)
    except Exception as e:
        click.echo(f"\nError creating client: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        click.echo("\nHint: Run 'ccmas --setup' to reconfigure or check your API key.")
        sys.exit(1)

    # Run
    try:
        if task:
            asyncio.run(single_task(config, client, task, output))
        else:
            asyncio.run(interactive_mode(config, client))
    except KeyboardInterrupt:
        click.echo("\n\nInterrupted. Goodbye!")
        sys.exit(0)
    except Exception as e:
        click.echo(f"\nError: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
