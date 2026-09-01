from __future__ import annotations

from dataclasses import dataclass

from backend.reven.decision_engine import (
    RevenueDecision,
    make_decision,
)

from backend.reven.intervention_engine import (
    InterventionPlan,
    build_intervention,
)

from backend.reven.state_engine import (
    CustomerState,
    build_customer_state,
)

from backend.schemas.streamflix import (
    Customer,
    EngagementSnapshot,
    Outcome,
    RiskEvent,
    Subscription,
)

from backend.simulator.outcome_engine import (
    simulate_outcome,
)


# ============================================================
# REVEN RESULT
# ============================================================

@dataclass
class RevenResult:

    customer_state: CustomerState

    decision: RevenueDecision

    intervention: InterventionPlan

    outcome: Outcome


# ============================================================
# GET SELECTED INTERVENTION PROBABILITY
# ============================================================

def get_selected_probability(
    decision: RevenueDecision,
) -> float:
    """
    Get the intervention probability used by the
    economic model for the selected action.

    This ensures the outcome simulator uses the same
    probability that REVEN used to make its decision.
    """

    selected_action = (
        decision.intervention_type
    )

    for evaluation in decision.alternatives:

        if (
            evaluation.intervention_type
            == selected_action
        ):

            return evaluation.success_probability

    # --------------------------------------------------------
    # NO ACTION
    # --------------------------------------------------------

    if (
        selected_action.value
        == "no_action"
    ):

        for evaluation in decision.alternatives:

            if (
                evaluation.intervention_type.value
                == "no_action"
            ):

                return evaluation.success_probability

    # --------------------------------------------------------
    # Defensive fallback
    # --------------------------------------------------------

    return 0.0


# ============================================================
# RUN REVEN
# ============================================================

def run_reven(
    customer: Customer,
    subscription: Subscription,
    risk_events: list[RiskEvent],
    engagement: EngagementSnapshot | None = None,
    seed: int | None = None,
) -> RevenResult:

    """
    Run one complete REVEN decision and outcome cycle.

    Pipeline:

        Customer
           ↓
        State
           ↓
        Decision
           ↓
        Intervention
           ↓
        Economic probability
           ↓
        Outcome simulation
    """

    # ========================================================
    # 1. BUILD CUSTOMER STATE
    # ========================================================

    state = build_customer_state(
        customer=customer,
        subscription=subscription,
        risk_events=risk_events,
        engagement=engagement,
    )

    # ========================================================
    # 2. MAKE REVEN DECISION
    # ========================================================

    decision = make_decision(
        state
    )

    # ========================================================
    # 3. BUILD EXECUTABLE INTERVENTION
    # ========================================================

    intervention = build_intervention(
        decision
    )

    # ========================================================
    # 4. GET SAME PROBABILITY USED BY DECISION MODEL
    # ========================================================

    success_probability = (
        get_selected_probability(
            decision
        )
    )

    # ========================================================
    # 5. SIMULATE ACTUAL OUTCOME
    # ========================================================

    # IMPORTANT: the outcome simulator deliberately uses its own
    # response model. Passing REVEN's predicted probability here
    # would leak the decision model into the counterfactual outcome
    # and make benchmark results circular.
    outcome = simulate_outcome(
        intervention=intervention.intervention,
        subscription=subscription,
        risk_events=risk_events,
        seed=seed,
    )

    # ========================================================
    # 6. RETURN COMPLETE REVEN RESULT
    # ========================================================

    return RevenResult(
        customer_state=state,
        decision=decision,
        intervention=intervention,
        outcome=outcome,
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

    # --------------------------------------------------------
    # Generate shared simulation world
    # --------------------------------------------------------

    customers, subscriptions = (
        generate_population(
            count=10_000,
            seed=42,
        )
    )

    events = generate_events(
        customers,
        subscriptions,
        seed=42,
        observation_days=30,
    )

    # --------------------------------------------------------
    # Find customer with most risk events
    # --------------------------------------------------------

    event_counts: dict[str, int] = {}

    for event in events:

        event_counts[event.customer_id] = (
            event_counts.get(
                event.customer_id,
                0,
            )
            + 1
        )

    customer_id = max(
        event_counts,
        key=event_counts.get,
    )

    customer = next(
        customer
        for customer in customers
        if customer.customer_id
        == customer_id
    )

    subscription = next(
        subscription
        for subscription in subscriptions
        if subscription.customer_id
        == customer_id
    )

    customer_events = [
        event
        for event in events
        if event.customer_id
        == customer_id
    ]

    # --------------------------------------------------------
    # Run REVEN
    # --------------------------------------------------------

    result = run_reven(
        customer=customer,
        subscription=subscription,
        risk_events=customer_events,
        seed=42,
    )

    # --------------------------------------------------------
    # Get probability used by REVEN
    # --------------------------------------------------------

    success_probability = (
        get_selected_probability(
            result.decision
        )
    )

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    print("REVEN END-TO-END ENGINE")
    print("=" * 50)

    print()
    print("CUSTOMER STATE")
    print("-" * 50)

    print(
        f"Customer: "
        f"{result.customer_state.customer_id}"
    )

    print(
        f"Risk state: "
        f"{result.customer_state.risk_state.value}"
    )

    print(
        f"Risk score: "
        f"{result.customer_state.risk_score:.1f}/100"
    )

    print(
        f"Days until renewal: "
        f"{result.customer_state.days_until_renewal}"
    )

    print(
        f"Payment failure: "
        f"{result.customer_state.payment_failure}"
    )

    print(
        f"Cancellation requested: "
        f"{result.customer_state.cancellation_requested}"
    )

    print(
        f"Engagement declining: "
        f"{result.customer_state.engagement_declining}"
    )

    print(
        f"Inactive: "
        f"{result.customer_state.inactive}"
    )

    print()
    print("REVEN DECISION")
    print("-" * 50)

    print(
        f"Action: "
        f"{result.decision.intervention_type.value}"
    )

    print(
        f"Expected incremental net revenue: "
        f"₹{result.decision.expected_net_revenue:.2f}"
    )

    print(
        f"Confidence: "
        f"{result.decision.confidence:.2%}"
    )

    print(
        f"Decision probability: "
        f"{success_probability:.2%}"
    )

    print(
        f"Reason: "
        f"{result.decision.reason}"
    )

    print()
    print("INTERVENTION")
    print("-" * 50)

    print(
        f"Primary action: "
        f"{result.intervention.intervention.intervention_type.value}"
    )

    print(
        f"Fallback: "
        f"{result.intervention.fallback_action.value}"
    )

    print(
        f"Status: "
        f"{result.intervention.intervention.status.value}"
    )

    print()
    print("OUTCOME")
    print("-" * 50)

    print(
        f"Subscription renewed: "
        f"{result.outcome.subscription_renewed}"
    )

    print(
        f"Payment recovered: "
        f"{result.outcome.payment_recovered}"
    )

    print(
        f"Churned: "
        f"{result.outcome.churned}"
    )

    print(
        f"Revenue preserved: "
        f"₹{result.outcome.revenue_preserved:.2f}"
    )

    print(
        f"Intervention cost: "
        f"₹{result.outcome.intervention_cost:.2f}"
    )

    print(
        f"Net revenue: "
        f"₹{result.outcome.net_revenue:.2f}"
    )

    print(
        f"Outcome reason: "
        f"{result.outcome.reason}"
    )