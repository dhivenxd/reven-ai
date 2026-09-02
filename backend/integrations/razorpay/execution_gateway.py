"""Execution gateway: the safety boundary between REVEN decisions and Razorpay API calls.

CRITICAL SECURITY BOUNDARY:

    LLM/frontend → REVEN policy engine → THIS GATEWAY → Razorpay API

The execution gateway:
1. Accepts ONLY RevenueDecision objects produced by run_reven()
2. Verifies the decision passed policy gates (intervention_type != NO_ACTION)
3. Maps InterventionType to Razorpay API operations
4. Executes the API call if appropriate
5. Returns execution result WITHOUT fabricating success

DO NOT:
- Allow LLM or frontend to directly call Razorpay API
- Execute decisions that did not pass REVEN policy gates
- Add financial decision logic in this gateway (that logic lives in REVEN)
- Fabricate successful recovery when only a payment link was created
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backend.reven.decision_engine import RevenueDecision
from backend.schemas.streamflix import InterventionType, Subscription
from backend.integrations.razorpay.razorpay_client import create_payment_link


@dataclass
class ExecutionResult:
    """Result of executing a REVEN decision via Razorpay API."""

    decision_id: str
    intervention_type: InterventionType
    execution_status: str  # "executed", "no_api_available", "blocked"
    razorpay_operation: str | None
    razorpay_resource_id: str | None
    razorpay_resource_url: str | None
    executed_at: datetime
    message: str


class ExecutionGateway:
    """Bounded execution gateway for Razorpay operations."""

    def execute_decision(
        self,
        decision: RevenueDecision,
        subscription: Subscription,
        customer_email: str | None = None,
        customer_contact: str | None = None,
        reference_id: str | None = None,
    ) -> ExecutionResult:
        """Execute a REVEN decision via Razorpay API.

        Args:
            decision: RevenueDecision from run_reven()
            subscription: Subscription object (for amount/currency)
            customer_email: Optional customer email for payment link
            customer_contact: Optional customer phone

        Returns:
            ExecutionResult with operation details

        IMPORTANT:
        - Creating a payment link != revenue recovered
        - Only subsequent payment.captured webhook = revenue recovered
        """
        executed_at = datetime.now()

        # Gate 1: Block NO_ACTION
        if decision.intervention_type == InterventionType.NO_ACTION:
            return ExecutionResult(
                decision_id=decision.customer_id,
                intervention_type=decision.intervention_type,
                execution_status="blocked",
                razorpay_operation=None,
                razorpay_resource_id=None,
                razorpay_resource_url=None,
                executed_at=executed_at,
                message="NO_ACTION decisions are not executed",
            )

        # Gate 2: PAYMENT_RETRY → Payment Link (Phase 2 recovery mechanism)
        if decision.intervention_type == InterventionType.PAYMENT_RETRY:
            return self._create_payment_recovery_link(
                decision,
                subscription,
                customer_email,
                customer_contact,
                executed_at,
                reference_id,
            )

        # Gate 3: All other interventions have no Razorpay API equivalent
        return ExecutionResult(
            decision_id=decision.customer_id,
            intervention_type=decision.intervention_type,
            execution_status="no_api_available",
            razorpay_operation=None,
            razorpay_resource_id=None,
            razorpay_resource_url=None,
            executed_at=executed_at,
            message=(
                f"{decision.intervention_type.value} requires "
                "customer-facing channel (email/SMS/app notification). "
                "Razorpay API does not support this intervention type."
            ),
        )

    def _create_payment_recovery_link(
        self,
        decision: RevenueDecision,
        subscription: Subscription,
        customer_email: str | None,
        customer_contact: str | None,
        executed_at: datetime,
        reference_id: str | None = None,
    ) -> ExecutionResult:
        """Create a Razorpay Payment Link for payment recovery.

        This is NOT an automatic card retry. It generates a link the
        customer must click and complete payment through.
        """
        amount_paise = int(subscription.price * 100)
        description = (
            f"Payment recovery for subscription {subscription.subscription_id}"
        )

        # Use provided reference_id or fall back to subscription_id
        # (caller can provide unique reference_id to avoid collisions)
        if reference_id is None:
            reference_id = subscription.subscription_id

        try:
            response = create_payment_link(
                amount=amount_paise,
                currency=subscription.currency,
                description=description,
                customer_email=customer_email,
                customer_contact=customer_contact,
                reference_id=reference_id,
            )

            return ExecutionResult(
                decision_id=decision.customer_id,
                intervention_type=decision.intervention_type,
                execution_status="executed",
                razorpay_operation="create_payment_link",
                razorpay_resource_id=response.get("id"),
                razorpay_resource_url=response.get("short_url"),
                executed_at=executed_at,
                message=(
                    "Payment recovery link created. "
                    "This is NOT automatic retry. "
                    "Customer must complete payment via link. "
                    "Revenue is NOT yet recovered."
                ),
            )

        except Exception as e:
            return ExecutionResult(
                decision_id=decision.customer_id,
                intervention_type=decision.intervention_type,
                execution_status="failed",
                razorpay_operation="create_payment_link",
                razorpay_resource_id=None,
                razorpay_resource_url=None,
                executed_at=executed_at,
                message=f"Razorpay API error: {e}",
            )
