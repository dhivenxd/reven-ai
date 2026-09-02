"""Abstract LLM client interface.

Providers must implement this interface.
Allows swapping providers without changing business logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Message:
    """A message in the conversation."""
    role: str  # "user" or "assistant"
    content: str


@dataclass
class ToolUse:
    """A tool use request from the LLM."""
    tool_name: str
    tool_input: dict[str, Any]
    tool_use_id: str


@dataclass
class LLMResponse:
    """Response from the LLM."""
    text: str
    tool_uses: list[ToolUse]
    stop_reason: str  # "end_turn", "tool_use", etc


class RevenLLMClient(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        system_instruction: str,
        tools: list[dict[str, Any]],
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """
        Send a chat request to the LLM with tools.

        Args:
            messages: Conversation history
            system_instruction: System prompt
            tools: Tool definitions (provider-specific format)
            max_tokens: Maximum response tokens

        Returns:
            LLMResponse with text and tool calls
        """
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Close the client connection."""
        raise NotImplementedError
