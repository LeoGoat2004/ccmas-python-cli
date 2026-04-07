"""
vLLM API adapter.

This module provides an adapter for vLLM API with
vLLM-specific configuration options.
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


class VLLMAdapter:
    """
    vLLM API adapter.

    Provides utilities for converting messages and tools
    to vLLM API format and parsing responses.
    vLLM is compatible with OpenAI API format.
    """

    # vLLM-specific parameters
    VLLM_PARAMS = {
        "top_k",
        "top_p",
        "repetition_penalty",
        "length_penalty",
        "early_stopping",
        "stop_token_ids",
        "ignore_eos",
        "max_tokens",
        "min_tokens",
        "logprobs",
        "prompt_logprobs",
        "skip_special_tokens",
        "spaces_between_special_tokens",
        "use_beam_search",
        "best_of",
        "n",
        "seed",
    }

    @staticmethod
    def convert_messages(messages: List[Message]) -> List[Dict[str, Any]]:
        """
        Convert messages to vLLM format (OpenAI-compatible).

        Args:
            messages: List of messages to convert

        Returns:
            List of messages in OpenAI format
        """
        return MessageConverter.to_openai_messages(messages)

    @staticmethod
    def convert_tools(tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        """
        Convert tools to vLLM format (OpenAI-compatible).

        Args:
            tools: List of tool definitions

        Returns:
            List of tools in OpenAI format
        """
        return [tool.to_openai_format() for tool in tools]

    @staticmethod
    def parse_response(response: Dict[str, Any]) -> AssistantMessage:
        """
        Parse vLLM API response.

        Args:
            response: Response from vLLM API

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
        Parse a streaming chunk from vLLM API.

        Args:
            chunk: Streaming chunk from vLLM API

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
        # vLLM-specific parameters
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
        repetition_penalty: Optional[float] = None,
        length_penalty: Optional[float] = None,
        early_stopping: Optional[bool] = None,
        stop_token_ids: Optional[List[int]] = None,
        ignore_eos: Optional[bool] = None,
        min_tokens: Optional[int] = None,
        logprobs: Optional[int] = None,
        prompt_logprobs: Optional[int] = None,
        skip_special_tokens: Optional[bool] = None,
        spaces_between_special_tokens: Optional[bool] = None,
        use_beam_search: Optional[bool] = None,
        best_of: Optional[int] = None,
        n: Optional[int] = None,
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Build request parameters for vLLM API.

        Args:
            model: Model identifier
            messages: List of messages in OpenAI format
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            tools: List of tools in OpenAI format
            top_k: Top-k sampling parameter
            top_p: Top-p sampling parameter
            repetition_penalty: Repetition penalty
            length_penalty: Length penalty
            early_stopping: Whether to stop early
            stop_token_ids: List of stop token IDs
            ignore_eos: Whether to ignore EOS token
            min_tokens: Minimum tokens to generate
            logprobs: Number of logprobs to return
            prompt_logprobs: Number of prompt logprobs to return
            skip_special_tokens: Whether to skip special tokens
            spaces_between_special_tokens: Whether to add spaces between special tokens
            use_beam_search: Whether to use beam search
            best_of: Best of parameter
            n: Number of completions to generate
            seed: Random seed
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

        # Add vLLM-specific parameters
        if top_k is not None:
            params["top_k"] = top_k

        if top_p is not None:
            params["top_p"] = top_p

        if repetition_penalty is not None:
            params["repetition_penalty"] = repetition_penalty

        if length_penalty is not None:
            params["length_penalty"] = length_penalty

        if early_stopping is not None:
            params["early_stopping"] = early_stopping

        if stop_token_ids is not None:
            params["stop_token_ids"] = stop_token_ids

        if ignore_eos is not None:
            params["ignore_eos"] = ignore_eos

        if min_tokens is not None:
            params["min_tokens"] = min_tokens

        if logprobs is not None:
            params["logprobs"] = logprobs

        if prompt_logprobs is not None:
            params["prompt_logprobs"] = prompt_logprobs

        if skip_special_tokens is not None:
            params["skip_special_tokens"] = skip_special_tokens

        if spaces_between_special_tokens is not None:
            params["spaces_between_special_tokens"] = spaces_between_special_tokens

        if use_beam_search is not None:
            params["use_beam_search"] = use_beam_search

        if best_of is not None:
            params["best_of"] = best_of

        if n is not None:
            params["n"] = n

        if seed is not None:
            params["seed"] = seed

        return params

    @staticmethod
    def get_default_endpoint() -> str:
        """
        Get default vLLM endpoint.

        Returns:
            Default vLLM API endpoint URL
        """
        return "http://localhost:8000/v1"

    @staticmethod
    def get_health_endpoint() -> str:
        """
        Get vLLM health check endpoint.

        Returns:
            Health check endpoint URL
        """
        return "http://localhost:8000/health"

    @staticmethod
    def get_models_endpoint() -> str:
        """
        Get vLLM models endpoint.

        Returns:
            Models endpoint URL
        """
        return "http://localhost:8000/v1/models"
