from __future__ import annotations

from dataclasses import dataclass

from backend.reven.baseline_engine import simulate_baseline
from backend.reven.calibration_profiles import get_calibration_profiles
from backend.reven.decision_engine import make_decision
from backend.reven.intervention_engine import build_intervention
from backend.reven.state_engine import build_customer_state
from backend.schemas.streamflix import InterventionType
from backend.simulator.customer_generator import generate_population
from backend.simulator.event_engine import generate_events
from backend.simulator.outcome_engine import simulate_outcome


@dataclass
class PolicyMetrics:
    interventions: int = 0
    no_action: int = 0
    renewals: int = 0
    revenue: float = 0.0
    intervention_cost: float = 0.0


def selected_probability(decision) -> float:
    for evaluation in decision.alternatives:
        if evaluation.intervention_type == decision.intervention_type:
            return evaluation.success_probability
    return 0.0


def execute(
    decision,
    subscription,
    events,
    seed: int,
    baseline,
    metrics: PolicyMetrics,
) -> None:
    action = decision.intervention_type

    if action == InterventionType.NO_ACTION:
        metrics.no_action += 1
        metrics.renewals += int(baseline.subscription_renewed)
        metrics.revenue += baseline.revenue_preserved
        return

    metrics.interventions += 1

    intervention = build_intervention(decision)

    # Use the independent simulator response model. The calibrated
    # probability is for decision-making/evaluation, not for creating
    # the realized counterfactual outcome.
    outcome = simulate_outcome(
        intervention=intervention.intervention,
        subscription=subscription,
        risk_events=events,
        seed=seed,
    )

    metrics.renewals += int(outcome.subscription_renewed)
    metrics.revenue += outcome.revenue_preserved
    metrics.intervention_cost += outcome.intervention_cost


def run_calibrated_benchmark(
    customer_count: int = 10_000,
    seed: int = 42,
) -> None:

    print("Generating shared simulation world...")

    customers, subscriptions = generate_population(
        count=customer_count,
        seed=seed,
    )

    events = generate_events(
        customers,
        subscriptions,
        seed=seed,
        observation_days=30,
    )

    events_by_customer: dict[str, list] = {}

    for event in events:
        events_by_customer.setdefault(
            event.customer_id,
            [],
        ).append(event)

    profiles = get_calibration_profiles()

    baseline_revenue = 0.0
    baseline_renewals = 0

    original = PolicyMetrics()
    calibrated = PolicyMetrics()

    changed_decisions = 0

    for index, (customer, subscription) in enumerate(
        zip(customers, subscriptions)
    ):

        customer_events = events_by_customer.get(
            customer.customer_id,
            [],
        )

        state = build_customer_state(
            customer=customer,
            subscription=subscription,
            risk_events=customer_events,
        )

        baseline = simulate_baseline(
            state=state,
            subscription=subscription,
            seed=seed + index,
        )

        baseline_revenue += baseline.revenue_preserved
        baseline_renewals += int(baseline.subscription_renewed)

        original_decision = make_decision(state)
        calibrated_decision = make_decision(
            state,
            calibration_profiles=profiles,
        )

        if (
            original_decision.intervention_type
            != calibrated_decision.intervention_type
        ):
            changed_decisions += 1

        policy_seed = seed + 100_000 + index

        execute(
            original_decision,
            subscription,
            customer_events,
            policy_seed,
            baseline,
            original,
        )

        execute(
            calibrated_decision,
            subscription,
            customer_events,
            policy_seed,
            baseline,
            calibrated,
        )

    original_net = original.revenue - original.intervention_cost
    calibrated_net = calibrated.revenue - calibrated.intervention_cost

    original_incremental = original_net - baseline_revenue
    calibrated_incremental = calibrated_net - baseline_revenue

    original_roi = (
        original_incremental / original.intervention_cost
        if original.intervention_cost
        else 0.0
    )

    calibrated_roi = (
        calibrated_incremental / calibrated.intervention_cost
        if calibrated.intervention_cost
        else 0.0
    )

    print()
    print("REVEN CALIBRATED BENCHMARK")
    print("=" * 65)

    print()
    print("BASELINE")
    print("-" * 65)
    print(f"Customers: {customer_count:,}")
    print(f"Renewals: {baseline_renewals:,}")
    print(f"Revenue: ₹{baseline_revenue:,.2f}")

    print()
    print("ORIGINAL REVEN")
    print("-" * 65)
    print(f"Interventions: {original.interventions:,}")
    print(f"No action: {original.no_action:,}")
    print(f"Renewals: {original.renewals:,}")
    print(f"Revenue: ₹{original.revenue:,.2f}")
    print(f"Intervention cost: ₹{original.intervention_cost:,.2f}")
    print(f"Net revenue: ₹{original_net:,.2f}")
    print(f"Incremental net revenue: ₹{original_incremental:,.2f}")
    print(f"ROI: {original_roi:.2f}x")

    print()
    print("CALIBRATED REVEN")
    print("-" * 65)
    print(f"Interventions: {calibrated.interventions:,}")
    print(f"No action: {calibrated.no_action:,}")
    print(f"Renewals: {calibrated.renewals:,}")
    print(f"Revenue: ₹{calibrated.revenue:,.2f}")
    print(f"Intervention cost: ₹{calibrated.intervention_cost:,.2f}")
    print(f"Net revenue: ₹{calibrated_net:,.2f}")
    print(f"Incremental net revenue: ₹{calibrated_incremental:,.2f}")
    print(f"ROI: {calibrated_roi:.2f}x")

    print()
    print("CALIBRATION IMPACT")
    print("-" * 65)
    print(f"Decision changes: {changed_decisions:,}")
    print(
        f"Incremental net revenue change: "
        f"₹{calibrated_incremental - original_incremental:,.2f}"
    )
    print(
        f"Renewal change: "
        f"{calibrated.renewals - original.renewals:+,}"
    )
    print(
        f"Intervention change: "
        f"{calibrated.interventions - original.interventions:+,}"
    )


if __name__ == "__main__":
    run_calibrated_benchmark(
        customer_count=10_000,
        seed=42,
    )
