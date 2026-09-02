"""Tool: get_recovery_outcome

Retrieves execution outcome for a decision.
Read-only. Distinguishes between payment link created vs payment captured.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.llm.domain.results import ToolResult, ToolStatus

if TYPE_CHECKING:
    from backend.llm.store.decision_store import DecisionStore


def get_recovery_outcome(
    decision_id: str,
    store: "DecisionStore",
) -> ToolResult:
    """
    Get execution outcome for a decision.

    IMPORTANT:
        - Payment link created ≠ payment captured
        - Payment link created ≠ revenue recovered
        - Only report actual recovery status

    Args:
        decision_id: The decision identifier
        store: Decision store (injected, not LLM-controlled)

    Returns:
        ToolResult with execution and outcome information

    Security:
        - Read-only
        - No data fabrication
        - Clearly distinguishes execution states
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
            "execution_status": stored.execution_status,
            "created_at": stored.created_at.isoformat(),
        }

        # Add execution details if executed
        if stored.execution_status == "executed":
            data["executed_at"] = stored.executed_at.isoformat() if stored.executed_at else None
            data["razorpay_resource_id"] = stored.razorpay_result_id

            # CRITICAL: Distinguish payment link creation from actual recovery
            if decision.intervention_type.value == "payment_retry":
                data["execution_message"] = (
                    "Payment link created. Customer must complete payment. "
                    "Revenue is NOT yet recovered."
                )
            else:
                data["execution_message"] = (
                    f"{decision.intervention_type.value} intervention executed."
                )

        elif stored.execution_status == "failed":
            data["execution_error"] = stored.execution_error

        elif stored.execution_status == "pending":
            data["execution_message"] = "Decision approved but not yet executed."

        elif stored.execution_status == "blocked":
            data["execution_message"] = "Decision blocked from execution."

        return ToolResult(
            status=ToolStatus.SUCCESS,
            data=data,
        )

    except Exception as e:
        return ToolResult(
            status=ToolStatus.ERROR,
            error_message=f"Failed to retrieve outcome: {str(e)}",
        )
