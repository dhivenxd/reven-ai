from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.schemas.streamflix import (  # noqa: E402
    Intervention,
    InterventionType,
    Outcome,
    RiskEvent,
    RiskEventType,
    Subscription,
)


def calculate_recovery_probability(
    intervention: Intervention,
    risk_events: list[RiskEvent],
    subscription: Subscription,
) -> float:
    """
    Estimate the probability that an intervention succeeds.

    These are synthetic simulation assumptions.
    They are NOT trained probabilities.
    """

    event_types = {event.event_type for event in risk_events}

    if intervention.intervention_type == InterventionType.PAYMENT_RETRY:
        probability = 0.55

        if any(
            event.event_type == RiskEventType.PAYMENT_FAILED
            and event.metadata.get("failure_reason") == "network_error"
            for event in risk_events
        ):
            probability += 0.20

        if not subscription.auto_renew:
            probability -= 0.10

    elif intervention.intervention_type == InterventionType.PAYMENT_REMINDER:
        probability = 0.35

    elif intervention.intervention_type == InterventionType.RENEWAL_REMINDER:
        probability = 0.45

        if RiskEventType.CANCELLATION_REQUESTED in event_types:
            probability -= 0.20

    elif intervention.intervention_type == InterventionType.PERSONALIZED_OFFER:
        probability = 0.50

    elif intervention.intervention_type == InterventionType.DISCOUNT:
        probability = 0.65

    elif intervention.intervention_type == InterventionType.PLAN_CHANGE:
        probability = 0.55

    elif intervention.intervention_type == InterventionType.CANCELLATION_SAVE:
        probability = 0.45

    elif intervention.intervention_type == InterventionType.NO_ACTION:
        probability = 0.0

    else:
        probability = 0.30

    # Strong cancellation intent makes recovery harder.
    if RiskEventType.CANCELLATION_REQUESTED in event_types:
        probability -= 0.15

    # Keep probability in a sensible range.
    return max(0.05, min(probability, 0.95))


def simulate_outcome(
    intervention: Intervention,
    subscription: Subscription,
    risk_events: list[RiskEvent],
    seed: int | None = None,
) -> Outcome:
    """
    Simulate the future result of an intervention.

    REVEN should call this only AFTER making its decision.
    """

    rng = random.Random(seed)

    probability = calculate_recovery_probability(
        intervention,
        risk_events,
        subscription,
    )

    succeeded = rng.random() < probability

    payment_recovered = False
    subscription_renewed = False

    if succeeded:
        if intervention.intervention_type in {
            InterventionType.PAYMENT_RETRY,
            InterventionType.PAYMENT_REMINDER,
        }:
            payment_recovered = True
            subscription_renewed = True

        elif intervention.intervention_type in {
            InterventionType.RENEWAL_REMINDER,
            InterventionType.PERSONALIZED_OFFER,
            InterventionType.DISCOUNT,
            InterventionType.PLAN_CHANGE,
            InterventionType.CANCELLATION_SAVE,
        }:
            subscription_renewed = True

    churned = not subscription_renewed

    revenue_preserved = (
        subscription.price
        if subscription_renewed
        else 0.0
    )

    net_revenue = (
        revenue_preserved
        - intervention.cost
        - intervention.offer_value
    )

    if subscription_renewed:
        reason = (
            f"Intervention succeeded "
            f"(simulated probability: {probability:.2%})"
        )
    else:
        reason = (
            f"Intervention failed "
            f"(simulated probability: {probability:.2%})"
        )

    return Outcome(
        outcome_id=f"out_{intervention.intervention_id}",
        customer_id=intervention.customer_id,
        intervention_id=intervention.intervention_id,
        evaluated_at=datetime.now(),
        subscription_renewed=subscription_renewed,
        payment_recovered=payment_recovered,
        churned=churned,
        revenue_preserved=revenue_preserved,
        intervention_cost=intervention.cost,
        net_revenue=net_revenue,
        reason=reason,
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

    customer_id = customers[0].customer_id
    subscription = subscriptions[0]

    customer_events = [
        event
        for event in events
        if event.customer_id == customer_id
    ]

    intervention = Intervention(
        intervention_id="int_test_001",
        customer_id=customer_id,
        intervention_type=InterventionType.PAYMENT_RETRY,
        created_at=datetime.now(),
        channel="system",
        cost=2.0,
        reason="Test payment recovery",
        status="executed",
    )

    outcome = simulate_outcome(
        intervention=intervention,
        subscription=subscription,
        risk_events=customer_events,
        seed=42,
    )

    print("STREAMFLIX OUTCOME ENGINE")
    print("=" * 40)
    print(f"Customer: {customer_id}")
    print(f"Intervention: {intervention.intervention_type.value}")
    print(f"Outcome: {outcome}")