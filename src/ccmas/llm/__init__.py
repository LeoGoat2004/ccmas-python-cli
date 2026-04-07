"""
LLM module for ccmas-python-cli.

This module provides LLM client implementations and adapters
for various LLM backends (OpenAI, vLLM, Ollama).
"""

from .client import LLMClient, OpenAIClient
from .ollama import OllamaAdapter
from .openai import OpenAIAdapter
from .vllm import VLLMAdapter

__all__ = [
    # Clients
    "LLMClient",
    "OpenAIClient",
    # Adapters
    "OpenAIAdapter",
    "VLLMAdapter",
    "OllamaAdapter",
]
