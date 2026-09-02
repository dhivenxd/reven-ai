"""REVEN LLM Agent Layer.

An orchestration and explanation layer for the REVEN revenue recovery system.

Architecture:
    Frontend
        ↓
    LLM Agent
        ↓
    Tool Layer (read-only + execution gateway)
        ↓
    REVEN Policy Engine (frozen)
        ↓
    Razorpay Execution Gateway (frozen)

SAFETY:
- LLM NEVER chooses interventions (REVEN does)
- LLM NEVER calls Razorpay directly (ExecutionGateway does)
- LLM NEVER fabricates data (only reports REVEN results)
- Execution requires decision_id, not intervention_type
"""

from backend.llm.agent.core import RevenAgent
from backend.llm.client.gemini_client import GeminiLLMClient
from backend.llm.client.base import RevenLLMClient
from backend.llm.tools.base import ToolResult, ToolError
from backend.llm.tools.decision_tool import get_reven_decision
from backend.llm.tools.execute_tool import execute_approved_decision
from backend.llm.tools.outcome_tool import get_recovery_outcome
from backend.llm.tools.status_tool import get_customer_recovery_status
from backend.llm.tools.summary_tool import get_recovery_summary
from backend.llm.store.decision_store import DecisionStore, InMemoryDecisionStore

__all__ = [
    # Agent
    "RevenAgent",
    # LLM Client
    "RevenLLMClient",
    "GeminiLLMClient",
    # Tools
    "get_reven_decision",
    "get_recovery_outcome",
    "get_customer_recovery_status",
    "get_recovery_summary",
    "execute_approved_decision",
    # Store
    "DecisionStore",
    "InMemoryDecisionStore",
    # Types
    "ToolResult",
    "ToolError",
]
