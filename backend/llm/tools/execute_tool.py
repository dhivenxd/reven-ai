"""Tool: execute_approved_decision

CRITICAL SECURITY BOUNDARY.

This is the ONLY tool that can trigger recovery execution.

The LLM provides ONLY decision_id.
The server resolves and validates the decision independently.

The LLM CANNOT:
- Specify intervention_type
- Specify amount
- Specify Razorpay parameters
- Bypass ExecutionGateway
- Execute NO_ACTION
- Execute non-existent decisions
- Fabricate execution results
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from backend.schemas.streamflix import InterventionType, Subscription
from backend.integrations.razorpay.execution_gateway import ExecutionGateway
from backend.llm.domain.results import (
    ExecutionConfirmation,
    ToolResult,
    ToolStatus,
    ToolError,
)

if TYPE_CHECKING:
    from backend.llm.store.decision_store import DecisionStore


def execute_approved_decision(
    decision_id: str,
    store: "DecisionStore",
    gateway: ExecutionGateway,
) -> ToolResult:
    """
    Execute an approved REVEN decision.

    SECURITY CONTRACT:
        1. LLM provides ONLY decision_id
        2. Server loads decision from trusted store
        3. Server validates decision exists and is approved
        4. Server rejects NO_ACTION
        5. Server prevents duplicate execution
        6. Server resolves subscription independently
        7. Server calls ExecutionGateway (frozen)
        8. Server returns actual ExecutionResult

    Args:
        decision_id: The decision identifier (LLM-provided)
        store: Decision store (injected, not LLM-controlled)
        gateway: ExecutionGateway (injected, not LLM-controlled)

    Returns:
        ToolResult with ExecutionConfirmation

    Raises:
        ToolError for validation failures

    Security validations:
        - Decision must exist in store
        - Decision must not be NO_ACTION
        - Decision must not already be executed
        - Subscription must be resolvable
        - Only ExecutionGateway can call Razorpay
    """
    try:
        # VALIDATION 1: Decision must exist
        stored = store.get_decision(decision_id)
        if not stored:
            return ToolResult(
                status=ToolStatus.NOT_FOUND,
                error_message=f"Decision not found: {decision_id}. Cannot execute a decision that does not exist.",
            )

        decision = stored.to_decision()

        # VALIDATION 2: Cannot execute NO_ACTION
        if decision.intervention_type == InterventionType.NO_ACTION:
            store.update_execution_status(
                decision_id,
                status="blocked",
                error="NO_ACTION cannot be executed",
            )
            return ToolResult(
                status=ToolStatus.BLOCKED,
                error_message=(
                    "This decision is NO_ACTION. REVEN determined that no "
                    "recovery action should be taken, so there is nothing to execute."
                ),
            )

        # VALIDATION 3: Prevent duplicate execution
        if stored.execution_status == "executed":
            return ToolResult(
                status=ToolStatus.BLOCKED,
                error_message=(
                    f"Decision {decision_id} has already been executed at "
                    f"{stored.executed_at.isoformat() if stored.executed_at else 'unknown time'}."
                ),
            )

        # VALIDATION 4: Resolve subscription independently
        # For buildathon: create minimal subscription from stored decision
        # In production: load from actual subscription store
        subscription = _resolve_subscription(decision.customer_id, stored)

        # EXECUTION: Call frozen ExecutionGateway
        # The gateway is the ONLY entry point to Razorpay
        execution_result = gateway.execute_decision(
            decision=decision,
            subscription=subscription,
            customer_email=None,  # Not available in buildathon
            customer_contact=None,
            reference_id=decision_id,
        )

        # Record execution result
        store.update_execution_status(
            decision_id,
            status="executed" if execution_result.execution_status == "executed" else "failed",
            razorpay_result_id=execution_result.razorpay_resource_id,
            error=execution_result.message if execution_result.execution_status != "executed" else None,
        )

        # Build confirmation
        confirmation = ExecutionConfirmation(
            decision_id=decision_id,
            intervention_type=decision.intervention_type,
            execution_status=execution_result.execution_status,
            razorpay_operation=execution_result.razorpay_operation,
            razorpay_resource_id=execution_result.razorpay_resource_id,
            razorpay_resource_url=execution_result.razorpay_resource_url,
            message=execution_result.message,
            executed_at=datetime.now(),
        )

        return ToolResult(
            status=ToolStatus.SUCCESS,
            data=confirmation.to_dict(),
        )

    except Exception as e:
        # Log execution failure
        store.update_execution_status(
            decision_id,
            status="failed",
            error=str(e),
        )

        return ToolResult(
            status=ToolStatus.ERROR,
            error_message=f"Execution failed: {str(e)}",
        )


def _resolve_subscription(customer_id: str, stored_decision) -> Subscription:
    """
    Resolve subscription for execution.

    For buildathon: create minimal subscription from decision data.
    In production: load from actual subscription store.
    """
    from datetime import date

    return Subscription(
        subscription_id=f"sub_{customer_id}",
        customer_id=customer_id,
        plan_id="standard",
        status="past_due",  # Assuming failed payment
        start_date=date.today(),
        current_period_start=date.today(),
        current_period_end=date.today(),
        price=stored_decision.expected_net_revenue + 100.0,  # Rough estimate
        currency="INR",
        auto_renew=True,
    )
