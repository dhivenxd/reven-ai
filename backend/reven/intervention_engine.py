from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backend.reven.decision_engine import RevenueDecision
from backend.reven.economic_engine import (
    DISCOUNT_RATE,
    INTERVENTION_COSTS,
)
from backend.schemas.streamflix import (
    Intervention,
    InterventionStatus,
    InterventionType,
)


@dataclass
class InterventionPlan:
    intervention: Intervention
    primary_reason: str
    fallback_action: InterventionType
    expected_value: float


def build_intervention(
    decision: RevenueDecision,
) -> InterventionPlan:
    """
    Convert a REVEN decision into an executable intervention plan.

    This layer does not make a new economic decision.
    It executes the decision already produced by the decision engine.
    """

    intervention_type = decision.intervention_type

    fallback_action = InterventionType.NO_ACTION

    if intervention_type == InterventionType.PAYMENT_RETRY:
        fallback_action = InterventionType.PAYMENT_REMINDER

    elif intervention_type == InterventionType.PAYMENT_REMINDER:
        fallback_action = InterventionType.NO_ACTION

    elif intervention_type == InterventionType.RENEWAL_REMINDER:
        fallback_action = InterventionType.NO_ACTION

    elif intervention_type == InterventionType.PERSONALIZED_OFFER:
        fallback_action = InterventionType.PLAN_CHANGE

    elif intervention_type == InterventionType.DISCOUNT:
        fallback_action = InterventionType.PERSONALIZED_OFFER

    elif intervention_type == InterventionType.PLAN_CHANGE:
        fallback_action = InterventionType.CANCELLATION_SAVE

    elif intervention_type == InterventionType.CANCELLATION_SAVE:
        fallback_action = InterventionType.PLAN_CHANGE

    reason = decision.reason

    # The outcome simulator derives the discount amount from the same
    # explicit DISCOUNT_RATE used by the economic model.
    offer_value = 0.0

    intervention = Intervention(
        intervention_id=f"int_{decision.customer_id}",
        customer_id=decision.customer_id,
        intervention_type=intervention_type,
        created_at=datetime.now(),
        channel="system",
        cost=INTERVENTION_COSTS[intervention_type],
        reason=reason,
        status=InterventionStatus.PROPOSED,
        offer_value=offer_value,
    )

    return InterventionPlan(
        intervention=intervention,
        primary_reason=reason,
        fallback_action=fallback_action,
        expected_value=decision.expected_net_revenue,
    )


if __name__ == "__main__":
    from backend.reven.decision_engine import make_decision
    from backend.reven.state_engine import (
        CustomerRiskState,
        CustomerState,
    )

    state = CustomerState(
        customer_id="demo_cancel",
        risk_state=CustomerRiskState.CRITICAL,
        days_until_renewal=5,
        auto_renew=False,
        subscription_price=599.0,
        payment_failure=False,
        cancellation_requested=True,
        engagement_declining=False,
        inactive=False,
        renewal_due=True,
        risk_score=80.0,
        reasons=[
            "cancellation requested",
            "renewal approaching",
        ],
    )

    decision = make_decision(state)

    plan = build_intervention(decision)

    print("REVEN INTERVENTION ENGINE")
    print("=" * 40)

    print(f"Customer: {plan.intervention.customer_id}")

    print(
        f"Primary action: "
        f"{plan.intervention.intervention_type.value}"
    )

    print(
        f"Expected incremental value: "
        f"₹{plan.expected_value:.2f}"
    )

    print(f"Reason: {plan.primary_reason}")

    print(
        f"Fallback action: "
        f"{plan.fallback_action.value}"
    )

    print(
        f"Status: "
        f"{plan.intervention.status.value}"
    )