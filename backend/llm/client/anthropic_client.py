"""Anthropic Claude LLM client implementation.

Uses native tool_use feature via anthropic-sdk.
"""

from __future__ import annotations

import os
from typing import Any, Optional
import json

import anthropic

from backend.llm.client.base import RevenLLMClient, Message, ToolUse, LLMResponse


class AnthropicLLMClient(RevenLLMClient):
    """Claude implementation of RevenLLMClient."""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize Anthropic client.

        Args:
            model: Model ID (e.g., "claude-3-5-sonnet-20241022")
            api_key: API key (defaults to ANTHROPIC_API_KEY env var)

        Raises:
            ValueError: If API key is not configured
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not configured. "
                "Set environment variable or pass api_key parameter."
            )

        self.model = model or os.environ.get(
            "REVEN_LLM_MODEL",
            "claude-3-5-sonnet-20241022",
        )

        self.client = anthropic.Anthropic(api_key=self.api_key)

    async def chat(
        self,
        messages: list[Message],
        system_instruction: str,
        tools: list[dict[str, Any]],
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """
        Send chat request to Claude with tool support.

        Args:
            messages: Conversation history
            system_instruction: System prompt
            tools: Tool definitions in Anthropic format
            max_tokens: Maximum response tokens

        Returns:
            LLMResponse with text and tool calls
        """
        # Convert messages to Anthropic format
        anthropic_messages = [
            {
                "role": msg.role,
                "content": msg.content,
            }
            for msg in messages
        ]

        # Call Claude with tool support
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_instruction,
            tools=tools,
            messages=anthropic_messages,
        )

        # Parse response
        text = ""
        tool_uses = []

        for block in response.content:
            if block.type == "text":
                text = block.text
            elif block.type == "tool_use":
                tool_uses.append(
                    ToolUse(
                        tool_name=block.name,
                        tool_input=block.input,
                        tool_use_id=block.id,
                    )
                )

        return LLMResponse(
            text=text,
            tool_uses=tool_uses,
            stop_reason=response.stop_reason or "end_turn",
        )

    async def close(self) -> None:
        """Close client connection."""
        # Anthropic SDK doesn't require explicit close
        pass
