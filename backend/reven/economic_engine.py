from __future__ import annotations

from dataclasses import dataclass

from backend.reven.state_engine import CustomerState
from backend.schemas.streamflix import InterventionType


# ============================================================
# INTERVENTION COSTS
# ============================================================

# Synthetic MVP economic assumptions. These are explicit simulator
# assumptions, not observed causal effects.
DISCOUNT_RATE = 0.10
PLAN_CHANGE_REVENUE_FACTOR = 0.65


INTERVENTION_COSTS = {
    InterventionType.PAYMENT_RETRY: 2.0,
    InterventionType.PAYMENT_REMINDER: 1.0,
    InterventionType.RENEWAL_REMINDER: 1.0,
    InterventionType.PERSONALIZED_OFFER: 3.0,
    InterventionType.DISCOUNT: 2.0,
    InterventionType.PLAN_CHANGE: 2.0,
    InterventionType.CANCELLATION_SAVE: 3.0,
    InterventionType.NO_ACTION: 0.0,
}


# ============================================================
# ECONOMIC EVALUATION
# ============================================================

@dataclass
class EconomicEvaluation:
    intervention_type: InterventionType

    success_probability: float
    baseline_probability: float

    gross_revenue_if_success: float
    baseline_expected_revenue: float
    expected_revenue: float

    incremental_lift: float
    incremental_revenue: float

    intervention_cost: float
    offer_cost: float

    expected_net_revenue: float


# Backward compatibility.
InterventionEconomics = EconomicEvaluation


# ============================================================
# BASELINE PROBABILITY
# ============================================================

def estimate_baseline_probability(
    state: CustomerState,
) -> float:
    """
    Estimate probability of renewal without intervention.

    This is the single baseline probability model used by
    the economic and decision engines.
    """

    risk_state = state.risk_state.value

    if risk_state == "critical":
        return 0.20

    if risk_state == "at_risk":
        return 0.45

    if risk_state == "watch":
        return 0.60

    return 0.70


# ============================================================
# INTERVENTION PROBABILITY
# ============================================================

def estimate_intervention_probability(
    state: CustomerState,
    intervention_type: InterventionType,
) -> float:
    """
    Estimate renewal probability if an intervention is applied.

    This is the single intervention probability model used
    throughout REVEN.
    """

    baseline = estimate_baseline_probability(state)

    # --------------------------------------------------------
    # NO ACTION
    # --------------------------------------------------------

    if intervention_type == InterventionType.NO_ACTION:
        return baseline

    # --------------------------------------------------------
    # PAYMENT RETRY
    # --------------------------------------------------------

    if intervention_type == InterventionType.PAYMENT_RETRY:

        if not state.payment_failure:
            return baseline

        probability = baseline + 0.20

        if state.auto_renew:
            probability += 0.05

        if state.cancellation_requested:
            probability -= 0.15

        return min(0.95, max(0.05, probability))

    # --------------------------------------------------------
    # PAYMENT REMINDER
    # --------------------------------------------------------

    if intervention_type == InterventionType.PAYMENT_REMINDER:

        if not state.payment_failure:
            return baseline

        probability = baseline + 0.10

        return min(0.95, max(0.05, probability))

    # --------------------------------------------------------
    # RENEWAL REMINDER
    # --------------------------------------------------------

    if intervention_type == InterventionType.RENEWAL_REMINDER:

        if not state.renewal_due:
            return baseline

        probability = baseline + 0.05

        if state.engagement_declining:
            probability += 0.02

        if state.inactive:
            probability += 0.02

        if state.cancellation_requested:
            probability -= 0.10

        return min(0.95, max(0.05, probability))

    # --------------------------------------------------------
    # PERSONALIZED OFFER
    # --------------------------------------------------------

    if intervention_type == InterventionType.PERSONALIZED_OFFER:

        if not (
            state.engagement_declining
            or state.inactive
        ):
            return baseline

        probability = baseline + 0.08

        if state.engagement_declining:
            probability += 0.05

        if state.inactive:
            probability += 0.03

        if state.cancellation_requested:
            probability -= 0.05

        return min(0.95, max(0.05, probability))

    # --------------------------------------------------------
    # DISCOUNT
    # --------------------------------------------------------

    if intervention_type == InterventionType.DISCOUNT:

        if state.risk_state.value == "healthy":
            return baseline

        probability = baseline + 0.10

        if state.cancellation_requested:
            probability += 0.08

        if state.engagement_declining:
            probability += 0.04

        if state.inactive:
            probability += 0.03

        return min(0.95, max(0.05, probability))

    # --------------------------------------------------------
    # PLAN CHANGE
    # --------------------------------------------------------

    if intervention_type == InterventionType.PLAN_CHANGE:

        if not (
            state.cancellation_requested
            or state.engagement_declining
            or state.inactive
        ):
            return baseline

        probability = baseline + 0.10

        if state.cancellation_requested:
            probability += 0.10

        if state.engagement_declining:
            probability += 0.03

        if state.inactive:
            probability += 0.02

        return min(0.95, max(0.05, probability))

    # --------------------------------------------------------
    # CANCELLATION SAVE
    # --------------------------------------------------------

    if intervention_type == InterventionType.CANCELLATION_SAVE:

        if not state.cancellation_requested:
            return baseline

        probability = baseline + 0.10

        return min(0.95, max(0.05, probability))

    return baseline


# ============================================================
# SUCCESS PROBABILITY COMPATIBILITY WRAPPER
# ============================================================

def estimate_success_probability(
    state: CustomerState,
    intervention_type: InterventionType,
) -> float:

    return estimate_intervention_probability(
        state,
        intervention_type,
    )


# ============================================================
# ECONOMIC CALCULATION
# ============================================================

def calculate_economics(
    state: CustomerState,
    intervention_type: InterventionType,
) -> EconomicEvaluation:

    baseline_probability = (
        estimate_baseline_probability(
            state
        )
    )

    success_probability = (
        estimate_intervention_probability(
            state,
            intervention_type,
        )
    )

    price = state.subscription_price

    baseline_expected_revenue = (
        baseline_probability * price
    )

    # Revenue must reflect the economics of the selected action.
    # A discount does not preserve 100% of list price, and a plan
    # change intentionally trades some revenue for retention.
    if intervention_type == InterventionType.DISCOUNT:
        gross_revenue_if_success = (
            price * (1.0 - DISCOUNT_RATE)
        )
    elif intervention_type == InterventionType.PLAN_CHANGE:
        gross_revenue_if_success = (
            price * PLAN_CHANGE_REVENUE_FACTOR
        )
    else:
        gross_revenue_if_success = price

    expected_revenue = (
        success_probability
        * gross_revenue_if_success
    )

    # Preserve the signed treatment-vs-control lift.
    # A harmful intervention must be worth less than no-action.
    incremental_lift = (
        success_probability
        - baseline_probability
    )

    incremental_revenue = (
        expected_revenue - baseline_expected_revenue
    )

    intervention_cost = (
        INTERVENTION_COSTS.get(
            intervention_type,
            0.0,
        )
    )

    # Keep offer economics explicit so discounts/offers can
    # later have their actual monetary cost represented.
    offer_cost = 0.0

    expected_net_revenue = (
        incremental_revenue
        - intervention_cost
        - offer_cost
    )

    return EconomicEvaluation(
        intervention_type=intervention_type,
        success_probability=success_probability,
        baseline_probability=baseline_probability,
        gross_revenue_if_success=gross_revenue_if_success,
        baseline_expected_revenue=baseline_expected_revenue,
        expected_revenue=expected_revenue,
        incremental_lift=incremental_lift,
        incremental_revenue=incremental_revenue,
        intervention_cost=intervention_cost,
        offer_cost=offer_cost,
        expected_net_revenue=expected_net_revenue,
    )


# ============================================================
# DEMO
# ============================================================

if __name__ == "__main__":

    from backend.simulator.customer_generator import (
        generate_population,
    )

    from backend.simulator.event_engine import (
        generate_events,
    )

    from backend.reven.state_engine import (
        build_customer_state,
    )

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

    customer_id = "cust_000007"

    customer = next(
        c
        for c in customers
        if c.customer_id == customer_id
    )

    subscription = next(
        s
        for s in subscriptions
        if s.customer_id == customer_id
    )

    customer_events = [
        event
        for event in events
        if event.customer_id == customer_id
    ]

    state = build_customer_state(
        customer=customer,
        subscription=subscription,
        risk_events=customer_events,
    )

    print("REVEN ECONOMIC ENGINE")
    print("=" * 60)

    print(f"Customer: {customer_id}")
    print(
        f"Risk state: {state.risk_state.value}"
    )
    print(
        f"Risk score: {state.risk_score:.1f}/100"
    )
    print(
        f"Subscription value: "
        f"₹{state.subscription_price:.2f}"
    )

    for action in InterventionType:

        evaluation = calculate_economics(
            state=state,
            intervention_type=action,
        )

        print()
        print(action.value)

        print(
            f"  baseline probability: "
            f"{evaluation.baseline_probability:.2%}"
        )

        print(
            f"  intervention probability: "
            f"{evaluation.success_probability:.2%}"
        )

        print(
            f"  incremental lift: "
            f"{evaluation.incremental_lift:.2%}"
        )

        print(
            f"  baseline expected revenue: "
            f"₹{evaluation.baseline_expected_revenue:.2f}"
        )

        print(
            f"  expected revenue: "
            f"₹{evaluation.expected_revenue:.2f}"
        )

        print(
            f"  incremental revenue: "
            f"₹{evaluation.incremental_revenue:.2f}"
        )

        print(
            f"  intervention cost: "
            f"₹{evaluation.intervention_cost:.2f}"
        )

        print(
            f"  expected net revenue: "
            f"₹{evaluation.expected_net_revenue:.2f}"
        )