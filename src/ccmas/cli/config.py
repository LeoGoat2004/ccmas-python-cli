"""
CLI configuration management.

This module provides configuration management for the CCMAS CLI,
including loading, saving, and validating configuration settings.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class CLIConfig(BaseModel):
    """
    CLI configuration settings.

    Manages all configuration options for the CCMAS CLI,
    including model settings, API endpoints, and user preferences.
    """

    # Workspace settings
    workspace: str = Field(
        default=None,
        description="Working directory for the CLI"
    )

    # Model settings
    model: str = Field(
        default="gpt-4",
        description="Default model to use"
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature"
    )
    max_tokens: Optional[int] = Field(
        default=None,
        description="Maximum tokens to generate"
    )

    # API settings
    api_base: Optional[str] = Field(
        default=None,
        description="Base URL for API calls"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API key for authentication"
    )

    # Backend settings
    backend: str = Field(
        default="openai",
        description="Backend to use (openai, ollama, vllm)"
    )

    # Ollama specific settings
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama server URL"
    )
    
    # vLLM specific settings
    vllm_base_url: str = Field(
        default="http://localhost:8000",
        description="vLLM server URL"
    )
    
    # Permission settings
    permission_mode: str = Field(
        default="acceptEdits",
        description="Permission mode (default, acceptEdits, bypassPermissions, bubble, plan, auto)"
    )
    
    # UI settings
    show_token_usage: bool = Field(
        default=True,
        description="Show token usage information"
    )
    show_timing: bool = Field(
        default=True,
        description="Show timing information"
    )
    color_output: bool = Field(
        default=True,
        description="Enable colored output"
    )
    
    # History settings
    save_history: bool = Field(
        default=True,
        description="Save conversation history"
    )
    history_file: Optional[str] = Field(
        default=None,
        description="Path to history file"
    )
    max_history_size: int = Field(
        default=1000,
        description="Maximum number of history entries"
    )
    
    # Advanced settings
    timeout: int = Field(
        default=300,
        description="Request timeout in seconds"
    )
    retry_attempts: int = Field(
        default=3,
        description="Number of retry attempts for failed requests"
    )
    verbose: bool = Field(
        default=False,
        description="Enable verbose output"
    )
    
    @field_validator("backend")
    @classmethod
    def validate_backend(cls, v: str) -> str:
        """Validate backend is one of the supported options."""
        valid_backends = {"openai", "ollama", "vllm"}
        if v.lower() not in valid_backends:
            raise ValueError(f"Invalid backend: {v}. Must be one of {valid_backends}")
        return v.lower()
    
    @field_validator("permission_mode")
    @classmethod
    def validate_permission_mode(cls, v: str) -> str:
        """Validate permission mode."""
        valid_modes = {"default", "acceptEdits", "bypassPermissions", "plan", "auto"}
        if v not in valid_modes:
            raise ValueError(f"Invalid permission mode: {v}. Must be one of {valid_modes}")
        return v
    
    def get_api_base(self) -> Optional[str]:
        """
        Get the appropriate API base URL based on backend.
        
        Returns:
            API base URL or None for default
        """
        if self.api_base:
            return self.api_base
        
        if self.backend == "ollama":
            return self.ollama_base_url
        elif self.backend == "vllm":
            return self.vllm_base_url
        
        return None
    
    def get_history_path(self) -> Path:
        """
        Get the path to the history file.
        
        Returns:
            Path to history file
        """
        if self.history_file:
            return Path(self.history_file)
        
        # Default to ~/.ccmas/history.json
        config_dir = Path.home() / ".ccmas"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "history.json"
    
    class Config:
        """Pydantic config."""
        
        use_enum_values = True


def get_config_path() -> Path:
    """
    Get the path to the configuration file.
    
    Returns:
        Path to config file
    """
    # Check for config in current directory first
    local_config = Path.cwd() / ".ccmas" / "config.json"
    if local_config.exists():
        return local_config
    
    # Fall back to user config directory
    config_dir = Path.home() / ".ccmas"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.json"


def load_config(config_path: Optional[Path] = None) -> CLIConfig:
    """
    Load configuration from file.
    
    Args:
        config_path: Optional path to config file. If not provided,
                    uses default location.
    
    Returns:
        CLIConfig instance
    
    Raises:
        ValueError: If config file is invalid
    """
    if config_path is None:
        config_path = get_config_path()
    
    if not config_path.exists():
        # Return default config if file doesn't exist
        return CLIConfig()
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        
        # Load environment variables for sensitive data
        if "api_key" not in config_data:
            config_data["api_key"] = os.getenv("OPENAI_API_KEY")
        
        return CLIConfig(**config_data)
    
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file: {e}")
    except Exception as e:
        raise ValueError(f"Failed to load config: {e}")


def save_config(config: CLIConfig, config_path: Optional[Path] = None) -> None:
    """
    Save configuration to file.
    
    Args:
        config: CLIConfig instance to save
        config_path: Optional path to config file. If not provided,
                    uses default location.
    
    Raises:
        IOError: If config file cannot be written
    """
    if config_path is None:
        config_path = get_config_path()
    
    # Ensure parent directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to dict, excluding None values
    config_dict = config.model_dump(exclude_none=True)

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)
    except Exception as e:
        raise IOError(f"Failed to save config: {e}")


def merge_config_with_args(config: CLIConfig, **kwargs: Any) -> CLIConfig:
    """
    Merge configuration with command-line arguments.
    
    Command-line arguments take precedence over config file settings.
    
    Args:
        config: Base CLIConfig instance
        **kwargs: Command-line arguments
    
    Returns:
        New CLIConfig instance with merged settings
    """
    config_dict = config.model_dump()
    
    # Update with non-None kwargs
    for key, value in kwargs.items():
        if value is not None:
            config_dict[key] = value
    
    return CLIConfig(**config_dict)


def create_default_config() -> CLIConfig:
    """
    Create a default configuration with sensible defaults.
    
    Returns:
        CLIConfig instance with default settings
    """
    return CLIConfig(
        model="gpt-4",
        temperature=0.7,
        backend="openai",
        permission_mode="acceptEdits",
        show_token_usage=True,
        show_timing=True,
        color_output=True,
        save_history=True,
        verbose=False,
    )
