"""REVEN Agent orchestrator.

Coordinates user requests with tools and LLM.
Implements the full tool-calling loop.
"""

from __future__ import annotations

import json
from typing import Any, Optional, TYPE_CHECKING

from backend.llm.client.base import Message, LLMResponse
from backend.llm.domain.results import ToolResult, ToolStatus
from backend.llm.agent.prompts import SYSTEM_INSTRUCTION
from backend.llm.tools.status_tool import get_customer_recovery_status
from backend.llm.tools.decision_tool import get_reven_decision
from backend.llm.tools.outcome_tool import get_recovery_outcome
from backend.llm.tools.summary_tool import get_recovery_summary
from backend.llm.tools.execute_tool import execute_approved_decision

if TYPE_CHECKING:
    from backend.llm.client.base import RevenLLMClient
    from backend.llm.store.decision_store import DecisionStore
    from backend.integrations.razorpay.execution_gateway import ExecutionGateway


# Tool schemas in Anthropic format
TOOL_DEFINITIONS = [
    {
        "name": "get_customer_recovery_status",
        "description": "Get recovery status for a specific customer. Returns latest decision, execution status, and history.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "The customer ID",
                }
            },
            "required": ["customer_id"],
        },
    },
    {
        "name": "get_reven_decision",
        "description": "Get full details of a specific REVEN decision by ID. Returns intervention, confidence, expected revenue, and alternatives.",
        "input_schema": {
            "type": "object",
            "properties": {
                "decision_id": {
                    "type": "string",
                    "description": "The decision ID (e.g., dec_abc123)",
                }
            },
            "required": ["decision_id"],
        },
    },
    {
        "name": "get_recovery_outcome",
        "description": "Check execution outcome and payment status for a decision. Distinguishes payment link creation from actual recovery.",
        "input_schema": {
            "type": "object",
            "properties": {
                "decision_id": {
                    "type": "string",
                    "description": "The decision ID",
                }
            },
            "required": ["decision_id"],
        },
    },
    {
        "name": "get_recovery_summary",
        "description": "Get aggregate recovery metrics for a timeframe.",
        "input_schema": {
            "type": "object",
            "properties": {
                "timeframe_days": {
                    "type": "integer",
                    "description": "Number of days to look back (default: 30)",
                    "default": 30,
                },
                "include_pending": {
                    "type": "boolean",
                    "description": "Include pending decisions in summary (default: false)",
                    "default": False,
                },
            },
            "required": [],
        },
    },
    {
        "name": "execute_approved_decision",
        "description": "Execute an approved REVEN decision. ONLY accepts decision_id. Server validates and executes independently.",
        "input_schema": {
            "type": "object",
            "properties": {
                "decision_id": {
                    "type": "string",
                    "description": "The approved decision ID to execute (e.g., dec_abc123)",
                }
            },
            "required": ["decision_id"],
        },
    },
]


class RevenAgent:
    """REVEN LLM Agent orchestrator."""

    def __init__(
        self,
        llm_client: RevenLLMClient,
        decision_store: "DecisionStore",
        execution_gateway: "ExecutionGateway",
    ):
        """
        Initialize agent.

        Args:
            llm_client: LLM provider (e.g., AnthropicLLMClient)
            decision_store: Decision storage (e.g., InMemoryDecisionStore)
            execution_gateway: Razorpay execution gateway (frozen)
        """
        self.llm = llm_client
        self.store = decision_store
        self.gateway = execution_gateway
        self.conversation_history: list[Message] = []

    async def chat(self, user_message: str) -> str:
        """
        Process a user message and return a response.

        Implements tool-calling loop:
        1. Send user message + system instruction to LLM
        2. LLM selects tools (or responds directly)
        3. Execute tools server-side
        4. Feed results back to LLM
        5. Repeat until LLM returns final response

        Args:
            user_message: The user's query

        Returns:
            Final agent response
        """
        # Add user message to history
        self.conversation_history.append(Message(role="user", content=user_message))

        # Tool-calling loop
        max_iterations = 5  # Prevent infinite loops
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Call LLM with current conversation
            llm_response = await self.llm.chat(
                messages=self.conversation_history,
                system_instruction=SYSTEM_INSTRUCTION,
                tools=TOOL_DEFINITIONS,
                max_tokens=1024,
            )

            # If LLM has text response, add to history
            if llm_response.text:
                self.conversation_history.append(
                    Message(role="assistant", content=llm_response.text)
                )

            # If no tool calls, return final response
            if not llm_response.tool_uses:
                return llm_response.text or "I couldn't process that request."

            # Execute tool calls
            tool_results = []
            for tool_use in llm_response.tool_uses:
                result = await self._execute_tool(
                    tool_use.tool_name,
                    tool_use.tool_input,
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.tool_use_id,
                        "content": json.dumps(result),
                    }
                )

            # Add tool use and results to history
            # Build assistant message with tool uses
            assistant_content = [
                {
                    "type": "tool_use",
                    "id": tu.tool_use_id,
                    "name": tu.tool_name,
                    "input": tu.tool_input,
                }
                for tu in llm_response.tool_uses
            ]
            if llm_response.text:
                assistant_content.insert(0, {"type": "text", "text": llm_response.text})

            # For simplicity, add as text message (Anthropic SDK will handle properly)
            tool_summary = "\n".join(
                [f"Tool {tr['tool_use_id']}: {tr['content']}" for tr in tool_results]
            )
            self.conversation_history.append(
                Message(role="user", content=f"Tool results:\n{tool_summary}")
            )

        # Max iterations reached
        return "I was unable to complete that request after multiple attempts."

    async def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Execute a single tool call."""
        try:
            if tool_name == "get_customer_recovery_status":
                result = get_customer_recovery_status(
                    customer_id=tool_input["customer_id"],
                    store=self.store,
                )

            elif tool_name == "get_reven_decision":
                result = get_reven_decision(
                    decision_id=tool_input["decision_id"],
                    store=self.store,
                )

            elif tool_name == "get_recovery_outcome":
                result = get_recovery_outcome(
                    decision_id=tool_input["decision_id"],
                    store=self.store,
                )

            elif tool_name == "get_recovery_summary":
                result = get_recovery_summary(
                    timeframe_days=tool_input.get("timeframe_days", 30),
                    include_pending=tool_input.get("include_pending", False),
                    store=self.store,
                )

            elif tool_name == "execute_approved_decision":
                result = execute_approved_decision(
                    decision_id=tool_input["decision_id"],
                    store=self.store,
                    gateway=self.gateway,
                )

            else:
                return {
                    "status": "error",
                    "error": f"Unknown tool: {tool_name}",
                }

            # Convert ToolResult to dict
            if isinstance(result, ToolResult):
                return {
                    "status": result.status.value,
                    "data": result.data,
                    "error": result.error_message,
                }
            else:
                return {
                    "status": "success",
                    "data": result,
                }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }
