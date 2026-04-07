"""
CCMAS - Claude Code Multi-Agent System Python CLI

A powerful multi-agent system command-line tool for building and managing
AI-powered applications.
"""

__version__ = "0.1.0"
__author__ = "CCMAS Team"
__email__ = "ccmas@example.com"

from ccmas.cli.config import CLIConfig
from ccmas.cli.main import main
from ccmas.llm.client import LLMClient, OpenAIClient
from ccmas.types.message import (
    Message,
    UserMessage,
    AssistantMessage,
    ToolMessage,
)
from ccmas.types.tool import ToolDefinition
from ccmas.tool.registry import get_registry

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "CLIConfig",
    "main",
    "LLMClient",
    "OpenAIClient",
    "Message",
    "UserMessage",
    "AssistantMessage",
    "ToolMessage",
    "ToolDefinition",
    "get_registry",
]
