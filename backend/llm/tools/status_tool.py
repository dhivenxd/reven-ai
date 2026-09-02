"""Tool: get_customer_recovery_status

Retrieves recovery status for a specific customer.
Read-only. Never fabricates data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.llm.domain.results import (
    RecoveryStatusResult,
    ExecutionStatus,
    ToolResult,
    ToolStatus,
)

if TYPE_CHECKING:
    from backend.llm.store.decision_store import DecisionStore


def get_customer_recovery_status(
    customer_id: str,
    store: "DecisionStore",
) -> ToolResult:
    """
    Get recovery status for a customer.

    Args:
        customer_id: The customer identifier
        store: Decision store (injected, not LLM-controlled)

    Returns:
        ToolResult with RecoveryStatusResult data

    Security:
        - Read-only
        - No data fabrication
        - Returns actual REVEN decisions only
    """
    try:
        decisions = store.get_decision_by_customer(customer_id, limit=10)

        if not decisions:
            result = RecoveryStatusResult(
                customer_id=customer_id,
                status=ExecutionStatus.NOT_FOUND,
            )
            return ToolResult(
                status=ToolStatus.NOT_FOUND,
                data=result.to_dict(),
            )

        # Get latest decision
        latest = decisions[0]
        decision = latest.to_decision()

        # Build decision history
        history = [
            {
                "decision_id": d.decision_id,
                "intervention_type": d.intervention_type.value,
                "expected_net_revenue": d.expected_net_revenue,
                "confidence": d.confidence,
                "execution_status": d.execution_status,
                "created_at": d.created_at.isoformat(),
            }
            for d in decisions
        ]

        # Determine overall status
        status = ExecutionStatus.PENDING
        if latest.execution_status == "executed":
            status = ExecutionStatus.EXECUTED
        elif latest.execution_status == "failed":
            status = ExecutionStatus.FAILED
        elif latest.execution_status == "blocked":
            status = ExecutionStatus.BLOCKED

        result = RecoveryStatusResult(
            customer_id=customer_id,
            status=status,
            decision=decision,
            decision_id=latest.decision_id,
            intervention_type=decision.intervention_type,
            confidence=decision.confidence,
            expected_net_revenue=decision.expected_net_revenue,
            reven_rationale=decision.reason,
            execution_status=latest.execution_status,
            decision_history=history,
        )

        return ToolResult(
            status=ToolStatus.SUCCESS,
            data=result.to_dict(),
        )

    except Exception as e:
        return ToolResult(
            status=ToolStatus.ERROR,
            error_message=f"Failed to retrieve customer status: {str(e)}",
        )
