"""Google Gemini LLM client implementation.

Uses google-genai SDK with function calling support.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from google import genai
from google.genai import types

from backend.llm.client.base import RevenLLMClient, Message, ToolUse, LLMResponse


class GeminiLLMClient(RevenLLMClient):
    """Gemini implementation of RevenLLMClient."""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize Gemini client.

        Args:
            model: Model ID (e.g., "gemini-2.0-flash-exp")
            api_key: API key (defaults to GEMINI_API_KEY env var)

        Raises:
            ValueError: If API key is not configured
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY not configured. "
                "Set environment variable or pass api_key parameter."
            )

        self.model = model or os.environ.get(
            "GEMINI_MODEL",
            "gemini-2.0-flash-exp",
        )

        self.client = genai.Client(api_key=self.api_key)

    async def chat(
        self,
        messages: list[Message],
        system_instruction: str,
        tools: list[dict[str, Any]],
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """
        Send chat request to Gemini with tool support.

        Args:
            messages: Conversation history
            system_instruction: System prompt
            tools: Tool definitions (converted to Gemini format)
            max_tokens: Maximum response tokens

        Returns:
            LLMResponse with text and tool calls
        """
        # Convert messages to Gemini format
        gemini_contents = []
        for msg in messages:
            gemini_contents.append(
                types.Content(
                    role="user" if msg.role == "user" else "model",
                    parts=[types.Part(text=msg.content)],
                )
            )

        # Convert tools from Anthropic format to Gemini format
        gemini_tools = self._convert_tools(tools)

        # Build generation config
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=gemini_tools if gemini_tools else None,
            temperature=0.7,
        )

        # Call Gemini
        response = self.client.models.generate_content(
            model=self.model,
            contents=gemini_contents,
            config=config,
        )

        # Parse response
        text = ""
        tool_uses = []

        if response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]

            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if hasattr(part, 'text') and part.text:
                        text = part.text
                    elif hasattr(part, 'function_call') and part.function_call:
                        # Extract function call
                        fc = part.function_call
                        tool_uses.append(
                            ToolUse(
                                tool_name=fc.name,
                                tool_input=dict(fc.args) if fc.args else {},
                                tool_use_id=f"call_{len(tool_uses)}",
                            )
                        )

        # Determine stop reason
        stop_reason = "end_turn"
        if tool_uses:
            stop_reason = "tool_use"

        return LLMResponse(
            text=text,
            tool_uses=tool_uses,
            stop_reason=stop_reason,
        )

    def _convert_tools(self, anthropic_tools: list[dict[str, Any]]) -> list[types.Tool]:
        """Convert Anthropic tool format to Gemini format."""
        if not anthropic_tools:
            return []

        function_declarations = []
        for tool in anthropic_tools:
            # Extract schema
            input_schema = tool.get("input_schema", {})
            properties = input_schema.get("properties", {})
            required = input_schema.get("required", [])

            # Convert to Gemini parameter format
            gemini_properties = {}
            for prop_name, prop_def in properties.items():
                gemini_properties[prop_name] = types.Schema(
                    type=types.Type(prop_def.get("type", "STRING").upper()),
                    description=prop_def.get("description", ""),
                )

            # Build function declaration
            function_declarations.append(
                types.FunctionDeclaration(
                    name=tool["name"],
                    description=tool.get("description", ""),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties=gemini_properties,
                        required=required,
                    ),
                )
            )

        return [types.Tool(function_declarations=function_declarations)]

    async def close(self) -> None:
        """Close client connection."""
        # Gemini SDK doesn't require explicit close
        pass
