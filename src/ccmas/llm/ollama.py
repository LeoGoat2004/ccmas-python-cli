"""
Ollama API adapter.

This module provides an adapter for Ollama API with
Ollama-specific configuration options.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..types.message import (
    AssistantMessage,
    Message,
    MessageConverter,
    ToolCall,
)
from ..types.tool import ToolDefinition


class OllamaAdapter:
    """
    Ollama API adapter.

    Provides utilities for converting messages and tools
    to Ollama API format and parsing responses.
    Ollama provides an OpenAI-compatible API endpoint.
    """

    # Ollama-specific parameters
    OLLAMA_PARAMS = {
        "num_ctx",
        "num_keep",
        "seed",
        "num_predict",
        "top_k",
        "top_p",
        "tfs_z",
        "typical_p",
        "repeat_last_n",
        "temperature",
        "repeat_penalty",
        "presence_penalty",
        "frequency_penalty",
        "mirostat",
        "mirostat_tau",
        "mirostat_eta",
        "penalize_newline",
        "stop",
        "numa",
        "num_gpu",
        "main_gpu",
        "low_vram",
        "f16_kv",
        "vocab_only",
        "use_mmap",
        "use_mlock",
        "embedding_only",
        "rope_frequency_base",
        "rope_frequency_scale",
        "num_thread",
        "num_batch",
    }

    @staticmethod
    def convert_messages(messages: List[Message]) -> List[Dict[str, Any]]:
        """
        Convert messages to Ollama format (OpenAI-compatible).

        Args:
            messages: List of messages to convert

        Returns:
            List of messages in OpenAI format
        """
        return MessageConverter.to_openai_messages(messages)

    @staticmethod
    def convert_tools(tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        """
        Convert tools to Ollama format (OpenAI-compatible).

        Args:
            tools: List of tool definitions

        Returns:
            List of tools in OpenAI format
        """
        return [tool.to_openai_format() for tool in tools]

    @staticmethod
    def parse_response(response: Dict[str, Any]) -> AssistantMessage:
        """
        Parse Ollama API response.

        Args:
            response: Response from Ollama API

        Returns:
            AssistantMessage instance
        """
        choice = response.get("choices", [{}])[0]
        message = choice.get("message", {})

        content = message.get("content")
        tool_calls = None

        if "tool_calls" in message:
            tool_calls = [
                ToolCall(
                    id=tc.get("id", ""),
                    type=tc.get("type", "function"),
                    function=tc.get("function", {}),
                )
                for tc in message["tool_calls"]
            ]

        usage = response.get("usage", {})

        return AssistantMessage(
            content=content,
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            stop_reason=choice.get("finish_reason"),
        )

    @staticmethod
    def parse_stream_chunk(chunk: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse a streaming chunk from Ollama API.

        Args:
            chunk: Streaming chunk from Ollama API

        Returns:
            Parsed chunk data or None if no content
        """
        choices = chunk.get("choices", [])
        if not choices:
            return None

        delta = choices[0].get("delta", {})
        finish_reason = choices[0].get("finish_reason")

        result: Dict[str, Any] = {}

        if "content" in delta:
            result["content"] = delta["content"]

        if "tool_calls" in delta:
            result["tool_calls"] = delta["tool_calls"]

        if finish_reason:
            result["finish_reason"] = finish_reason

        return result if result else None

    @staticmethod
    def build_request_params(
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        # Ollama-specific parameters
        num_ctx: Optional[int] = None,
        num_keep: Optional[int] = None,
        seed: Optional[int] = None,
        num_predict: Optional[int] = None,
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
        tfs_z: Optional[float] = None,
        typical_p: Optional[float] = None,
        repeat_last_n: Optional[int] = None,
        repeat_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        mirostat: Optional[int] = None,
        mirostat_tau: Optional[float] = None,
        mirostat_eta: Optional[float] = None,
        penalize_newline: Optional[bool] = None,
        stop: Optional[List[str]] = None,
        numa: Optional[bool] = None,
        num_gpu: Optional[int] = None,
        main_gpu: Optional[int] = None,
        low_vram: Optional[bool] = None,
        f16_kv: Optional[bool] = None,
        vocab_only: Optional[bool] = None,
        use_mmap: Optional[bool] = None,
        use_mlock: Optional[bool] = None,
        embedding_only: Optional[bool] = None,
        rope_frequency_base: Optional[float] = None,
        rope_frequency_scale: Optional[float] = None,
        num_thread: Optional[int] = None,
        num_batch: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Build request parameters for Ollama API.

        Args:
            model: Model identifier
            messages: List of messages in OpenAI format
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            tools: List of tools in OpenAI format
            num_ctx: Context window size
            num_keep: Number of tokens to keep
            seed: Random seed
            num_predict: Number of tokens to predict
            top_k: Top-k sampling parameter
            top_p: Top-p sampling parameter
            tfs_z: Tail free sampling z
            typical_p: Typical sampling p
            repeat_last_n: Repeat last n tokens
            repeat_penalty: Repeat penalty
            presence_penalty: Presence penalty
            frequency_penalty: Frequency penalty
            mirostat: Mirostat version
            mirostat_tau: Mirostat tau
            mirostat_eta: Mirostat eta
            penalize_newline: Whether to penalize newlines
            stop: Stop sequences
            numa: Whether to use NUMA
            num_gpu: Number of GPUs
            main_gpu: Main GPU
            low_vram: Whether to use low VRAM mode
            f16_kv: Whether to use f16 for KV cache
            vocab_only: Whether to only load vocabulary
            use_mmap: Whether to use mmap
            use_mlock: Whether to use mlock
            embedding_only: Whether to only compute embeddings
            rope_frequency_base: RoPE frequency base
            rope_frequency_scale: RoPE frequency scale
            num_thread: Number of threads
            num_batch: Batch size
            **kwargs: Additional parameters

        Returns:
            Dictionary of request parameters
        """
        params: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            **kwargs,
        }

        if max_tokens is not None:
            params["max_tokens"] = max_tokens

        if tools:
            params["tools"] = tools

        # Add Ollama-specific parameters
        if num_ctx is not None:
            params["num_ctx"] = num_ctx

        if num_keep is not None:
            params["num_keep"] = num_keep

        if seed is not None:
            params["seed"] = seed

        if num_predict is not None:
            params["num_predict"] = num_predict

        if top_k is not None:
            params["top_k"] = top_k

        if top_p is not None:
            params["top_p"] = top_p

        if tfs_z is not None:
            params["tfs_z"] = tfs_z

        if typical_p is not None:
            params["typical_p"] = typical_p

        if repeat_last_n is not None:
            params["repeat_last_n"] = repeat_last_n

        if repeat_penalty is not None:
            params["repeat_penalty"] = repeat_penalty

        if presence_penalty is not None:
            params["presence_penalty"] = presence_penalty

        if frequency_penalty is not None:
            params["frequency_penalty"] = frequency_penalty

        if mirostat is not None:
            params["mirostat"] = mirostat

        if mirostat_tau is not None:
            params["mirostat_tau"] = mirostat_tau

        if mirostat_eta is not None:
            params["mirostat_eta"] = mirostat_eta

        if penalize_newline is not None:
            params["penalize_newline"] = penalize_newline

        if stop is not None:
            params["stop"] = stop

        if numa is not None:
            params["numa"] = numa

        if num_gpu is not None:
            params["num_gpu"] = num_gpu

        if main_gpu is not None:
            params["main_gpu"] = main_gpu

        if low_vram is not None:
            params["low_vram"] = low_vram

        if f16_kv is not None:
            params["f16_kv"] = f16_kv

        if vocab_only is not None:
            params["vocab_only"] = vocab_only

        if use_mmap is not None:
            params["use_mmap"] = use_mmap

        if use_mlock is not None:
            params["use_mlock"] = use_mlock

        if embedding_only is not None:
            params["embedding_only"] = embedding_only

        if rope_frequency_base is not None:
            params["rope_frequency_base"] = rope_frequency_base

        if rope_frequency_scale is not None:
            params["rope_frequency_scale"] = rope_frequency_scale

        if num_thread is not None:
            params["num_thread"] = num_thread

        if num_batch is not None:
            params["num_batch"] = num_batch

        return params

    @staticmethod
    def get_default_endpoint() -> str:
        """
        Get default Ollama endpoint.

        Returns:
            Default Ollama API endpoint URL
        """
        return "http://localhost:11434/v1"

    @staticmethod
    def get_ollama_native_endpoint() -> str:
        """
        Get Ollama native API endpoint.

        Returns:
            Ollama native API endpoint URL
        """
        return "http://localhost:11434/api"

    @staticmethod
    def get_tags_endpoint() -> str:
        """
        Get Ollama tags endpoint (list models).

        Returns:
            Tags endpoint URL
        """
        return "http://localhost:11434/api/tags"

    @staticmethod
    def get_generate_endpoint() -> str:
        """
        Get Ollama generate endpoint.

        Returns:
            Generate endpoint URL
        """
        return "http://localhost:11434/api/generate"

    @staticmethod
    def get_chat_endpoint() -> str:
        """
        Get Ollama chat endpoint.

        Returns:
            Chat endpoint URL
        """
        return "http://localhost:11434/api/chat"

    @staticmethod
    def get_embeddings_endpoint() -> str:
        """
        Get Ollama embeddings endpoint.

        Returns:
            Embeddings endpoint URL
        """
        return "http://localhost:11434/api/embeddings"
