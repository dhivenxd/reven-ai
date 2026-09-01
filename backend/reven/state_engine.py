from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional

from backend.schemas.streamflix import (
    Customer,
    EngagementSnapshot,
    RiskEvent,
    RiskEventType,
    RiskSeverity,
    Subscription,
)


class CustomerRiskState(str, Enum):
    HEALTHY = "healthy"
    WATCH = "watch"
    AT_RISK = "at_risk"
    CRITICAL = "critical"


@dataclass
class CustomerState:
    customer_id: str
    risk_state: CustomerRiskState

    days_until_renewal: int
    auto_renew: bool
    subscription_price: float

    payment_failure: bool
    cancellation_requested: bool
    engagement_declining: bool
    inactive: bool
    renewal_due: bool

    risk_score: float
    reasons: list[str]


def build_customer_state(
    customer: Customer,
    subscription: Subscription,
    risk_events: list[RiskEvent],
    engagement: Optional[EngagementSnapshot] = None,
    today: Optional[date] = None,
) -> CustomerState:
    """
    Build REVEN's observable customer state.

    IMPORTANT:
    This function must only use information that would be available
    at decision time. It must never inspect Outcome objects or future
    intervention results.
    """

    today = today or date.today()

    customer_events = [
        event
        for event in risk_events
        if event.customer_id == customer.customer_id
    ]

    event_types = {
        event.event_type
        for event in customer_events
    }

    days_until_renewal = (
        subscription.current_period_end - today
    ).days

    payment_failure = (
        RiskEventType.PAYMENT_FAILED in event_types
    )

    cancellation_requested = (
        RiskEventType.CANCELLATION_REQUESTED in event_types
        or RiskEventType.CANCELLATION in event_types
    )

    engagement_declining = (
        RiskEventType.ENGAGEMENT_DECLINE in event_types
    )

    inactive = (
        RiskEventType.INACTIVITY in event_types
    )

    renewal_due = (
        0 <= days_until_renewal <= 7
    )

    # ---------------------------------------------------------
    # Risk scoring
    # ---------------------------------------------------------
    # This is a transparent rule-based baseline.
    # It is NOT an ML probability.
    score = 0.0
    reasons: list[str] = []

    if payment_failure:
        score += 30
        reasons.append("payment failure")

    if cancellation_requested:
        score += 40
        reasons.append("cancellation requested")

    if engagement_declining:
        score += 15
        reasons.append("engagement declining")

    if inactive:
        score += 15
        reasons.append("customer inactive")

    if renewal_due:
        score += 20
        reasons.append(
            f"renewal in {days_until_renewal} days"
        )

    if not subscription.auto_renew:
        score += 15
        reasons.append("auto-renew disabled")

    # Engagement is informative but deliberately not dominant.
    # Our KKBOX analysis showed that engagement alone does not
    # cleanly separate churners from non-churners.

    score = min(score, 100.0)

    # ---------------------------------------------------------
    # Risk state
    # ---------------------------------------------------------
    if cancellation_requested or score >= 70:
        risk_state = CustomerRiskState.CRITICAL

    elif score >= 45:
        risk_state = CustomerRiskState.AT_RISK

    elif score >= 20:
        risk_state = CustomerRiskState.WATCH

    else:
        risk_state = CustomerRiskState.HEALTHY

    return CustomerState(
        customer_id=customer.customer_id,
        risk_state=risk_state,
        days_until_renewal=days_until_renewal,
        auto_renew=subscription.auto_renew,
        subscription_price=subscription.price,
        payment_failure=payment_failure,
        cancellation_requested=cancellation_requested,
        engagement_declining=engagement_declining,
        inactive=inactive,
        renewal_due=renewal_due,
        risk_score=score,
        reasons=reasons,
    )


if __name__ == "__main__":
    from backend.simulator.customer_generator import generate_population
    from backend.simulator.event_engine import generate_events

    customers, subscriptions = generate_population(
        count=10_000,
        seed=42,
    )

    events = generate_events(
        customers,
        subscriptions,
        seed=42,
        observation_days=30,
    )

    # Pick a customer with at least one risk event.
    event_customer_ids = {
        event.customer_id
        for event in events
    }

    customer = next(
        customer
        for customer in customers
        if customer.customer_id in event_customer_ids
    )

    subscription = next(
        subscription
        for subscription in subscriptions
        if subscription.customer_id == customer.customer_id
    )

    state = build_customer_state(
        customer=customer,
        subscription=subscription,
        risk_events=events,
    )

    print("REVEN STATE ENGINE")
    print("=" * 40)
    print(f"Customer: {state.customer_id}")
    print(f"Risk state: {state.risk_state.value}")
    print(f"Risk score: {state.risk_score:.1f}/100")
    print(f"Days until renewal: {state.days_until_renewal}")
    print(f"Auto-renew: {state.auto_renew}")
    print(f"Payment failure: {state.payment_failure}")
    print(f"Cancellation requested: {state.cancellation_requested}")
    print(f"Engagement declining: {state.engagement_declining}")
    print(f"Inactive: {state.inactive}")
    print(f"Renewal due: {state.renewal_due}")

    print("\nReasons:")
    for reason in state.reasons:
        print(f"  - {reason}")