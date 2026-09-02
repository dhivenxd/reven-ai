"""Tool: get_reven_decision

Retrieves a specific REVEN decision by ID.
Read-only. Returns actual decisions, never fabricates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.llm.domain.results import ToolResult, ToolStatus

if TYPE_CHECKING:
    from backend.llm.store.decision_store import DecisionStore


def get_reven_decision(
    decision_id: str,
    store: "DecisionStore",
) -> ToolResult:
    """
    Get a specific REVEN decision by ID.

    Args:
        decision_id: The decision identifier
        store: Decision store (injected, not LLM-controlled)

    Returns:
        ToolResult with full decision data including alternatives

    Security:
        - Read-only
        - No data fabrication
        - Returns actual REVEN decision with full rationale
    """
    try:
        stored = store.get_decision(decision_id)

        if not stored:
            return ToolResult(
                status=ToolStatus.NOT_FOUND,
                error_message=f"Decision not found: {decision_id}",
            )

        decision = stored.to_decision()

        data = {
            "decision_id": decision_id,
            "customer_id": decision.customer_id,
            "intervention_type": decision.intervention_type.value,
            "expected_net_revenue": decision.expected_net_revenue,
            "confidence": decision.confidence,
            "reason": decision.reason,
            "created_at": stored.created_at.isoformat(),
            "execution_status": stored.execution_status,
            "alternatives": [
                {
                    "intervention_type": alt.intervention_type.value,
                    "expected_net_revenue": alt.expected_net_revenue,
                    "success_probability": alt.success_probability,
                    "incremental_lift": alt.incremental_lift,
                }
                for alt in decision.alternatives
            ],
        }

        return ToolResult(
            status=ToolStatus.SUCCESS,
            data=data,
        )

    except Exception as e:
        return ToolResult(
            status=ToolStatus.ERROR,
            error_message=f"Failed to retrieve decision: {str(e)}",
        )
