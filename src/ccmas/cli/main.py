"""
CCMAS CLI - CCMAS Multi-Agent System

A Python implementation of CCMAS core functionality.
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
from ccmas.memory.loader import load_ccmas_md, CCMAS_FILE_NAME
from ccmas.memory.session import SessionManager
from ccmas.skill.commands import (
    install_skill,
    uninstall_skill,
    update_skill,
    list_installed_skills,
    get_skill_info,
)


@click.group(name="skill")
def skill_group():
    """Manage skills (install, list, uninstall)."""
    pass


@skill_group.command(name="install")
@click.argument("source")
@click.option("--name", "-n", default=None, help="Name for the skill")
def skill_install(source: str, name: Optional[str]) -> None:
    """Install a skill from a source.

    SOURCE can be:
        - GitHub repo: user/repo or user/repo/skill-name
        - GitHub file URL: direct link to SKILL.md
        - GitHub zipball URL
        - Local path

    Examples:

        ccmas skill install user/repo
        ccmas skill install user/repo/skill-name
        ccmas skill install https://github.com/user/repo/blob/main/SKILL.md
        ccmas skill install /path/to/local/skill
    """
    result = install_skill(source, name)
    if result["success"]:
        click.echo(f"[OK] {result['message']}")
    else:
        click.echo(f"[ERROR] {result['message']}", err=True)
        sys.exit(1)


@skill_group.command(name="list")
def skill_list() -> None:
    """List all installed skills."""
    skills = list_installed_skills()
    if not skills:
        click.echo("No skills installed.")
        click.echo("Run 'ccmas skill install <source>' to install a skill.")
        return

    click.echo(f"\nInstalled skills ({len(skills)}):\n")
    for skill in skills:
        desc = skill.display_description
        if len(desc) > 60:
            desc = desc[:57] + "..."
        click.echo(f"  • {skill.name}")
        if desc:
            click.echo(f"    {desc}")
        click.echo()


@skill_group.command(name="info")
@click.argument("name")
def skill_info(name: str) -> None:
    """Show detailed information about a skill."""
    info = get_skill_info(name)
    if not info:
        click.echo(f"[ERROR] Skill '{name}' not found", err=True)
        click.echo("Run 'ccmas skill list' to see installed skills.")
        sys.exit(1)

    click.echo(f"\nSkill: {info['name']}\n")
    click.echo(f"Description: {info['description']}")
    if info.get("when_to_use"):
        click.echo(f"Use when: {info['when_to_use']}")
    if info.get("allowed_tools"):
        click.echo(f"Allowed tools: {', '.join(info['allowed_tools'])}")
    if info.get("version"):
        click.echo(f"Version: {info['version']}")
    click.echo(f"Location: {info['file_path']}")


@skill_group.command(name="uninstall")
@click.argument("name")
def skill_uninstall(name: str) -> None:
    """Uninstall a skill by name."""
    result = uninstall_skill(name)
    if result["success"]:
        click.echo(f"[OK] {result['message']}")
    else:
        click.echo(f"[ERROR] {result['message']}", err=True)
        sys.exit(1)


@skill_group.command(name="update")
@click.argument("name")
def skill_update(name: str) -> None:
    """Update an installed skill."""
    result = update_skill(name)
    if result["success"]:
        click.echo(f"[OK] {result['message']}")
    else:
        click.echo(f"[ERROR] {result['message']}", err=True)
        sys.exit(1)


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


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx: click.Context) -> None:
    """CCMAS - Multi-Agent System CLI.

    A powerful multi-agent CLI for orchestrating software engineering tasks.

    Usage: ccmas [OPTIONS] [TASK] or ccmas run [OPTIONS] [TASK]
    """
    if ctx.invoked_subcommand is None:
        ctx.invoke(run)


main.add_command(skill_group)


@click.command(name="run")
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
@click.option(
    "--continue", "use_continue", is_flag=True, default=False,
    help="Continue from last session"
)
@click.option(
    "--load-session", "load_session_id", default=None, type=str,
    help="Load a specific historical session by ID"
)
@click.option(
    "--no-memory", is_flag=True, default=False,
    help="Disable memory loading"
)
@click.argument("task", required=False)
def run(
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
    use_continue: bool,
    load_session_id: Optional[str],
    no_memory: bool,
    task: Optional[str],
) -> None:
    """
    Run CCMAS in interactive mode or execute a single task.

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

    # Memory handling
    session_to_load = None
    if not no_memory:
        # Check for CCMAS.md
        ccmas_md_content = load_ccmas_md(cwd)
        if ccmas_md_content:
            click.echo(f"\n[Memory] {CCMAS_FILE_NAME} loaded - project context available")

        # Check for historical sessions
        session_manager = SessionManager()
        latest_session = session_manager.get_latest_session(cwd)

        if latest_session:
            if use_continue:
                # Auto-continue from last session
                session_to_load = latest_session.id
                click.echo(f"[Memory] Continuing session: {session_to_load}")
            elif load_session_id:
                # Load specific session
                try:
                    session_to_load = session_manager.load_session(load_session_id).id
                    click.echo(f"[Memory] Loaded session: {session_to_load}")
                except FileNotFoundError:
                    click.echo(f"[Memory] Session not found: {load_session_id}", err=True)
            elif not task:
                # Ask user if they want to continue
                click.echo(f"\n[Memory] Found previous session: {latest_session.id}")
                click.echo(f"       Last updated: {latest_session.updated_at}")
                if click.confirm("Continue from last session?"):
                    session_to_load = latest_session.id
                    click.echo(f"[Memory] Continuing session: {session_to_load}")

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


main.add_command(run)


if __name__ == "__main__":
    main()
