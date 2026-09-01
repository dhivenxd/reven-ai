from __future__ import annotations

from dataclasses import dataclass

from backend.reven.baseline_engine import simulate_baseline
from backend.reven.economic_engine import (
    estimate_success_probability,
)
from backend.reven.reven_engine import run_reven
from backend.reven.state_engine import build_customer_state
from backend.schemas.streamflix import InterventionType
from backend.simulator.customer_generator import generate_population
from backend.simulator.event_engine import generate_events


@dataclass
class CalibrationStats:
    action: str
    decisions: int
    expected_success_probability: float
    actual_success_rate: float
    calibration_error: float
    expected_incremental_value: float
    actual_incremental_value: float


def run_calibration(
    customer_count: int = 10_000,
    seed: int = 42,
) -> list[CalibrationStats]:

    # ---------------------------------------------------------
    # 1. Generate shared population
    # ---------------------------------------------------------

    customers, subscriptions = generate_population(
        count=customer_count,
        seed=seed,
    )

    # ---------------------------------------------------------
    # 2. Generate shared event world
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # 3. Collect calibration data
    # ---------------------------------------------------------

    data: dict[str, dict[str, float]] = {}

    for index, (customer, subscription) in enumerate(
        zip(customers, subscriptions)
    ):

        customer_events = events_by_customer.get(
            customer.customer_id,
            [],
        )

        # Build customer state
        state = build_customer_state(
            customer=customer,
            subscription=subscription,
            risk_events=customer_events,
        )

        # Run REVEN
        result = run_reven(
            customer=customer,
            subscription=subscription,
            risk_events=customer_events,
            seed=seed + index,
        )

        action = result.decision.intervention_type.value

        # -----------------------------------------------------
        # Ignore no-action decisions
        # -----------------------------------------------------

        if action == "no_action":
            continue

        intervention_type = InterventionType(action)

        # Use the EXACT probability logic from the
        # economic engine.
        probability = estimate_success_probability(
            state,
            intervention_type,
        )

        if action not in data:
            data[action] = {
                "decisions": 0,
                "expected_probability": 0.0,
                "successes": 0,
                "expected_value": 0.0,
                "actual_value": 0.0,
            }

        row = data[action]

        row["decisions"] += 1
        row["expected_probability"] += probability

        # -----------------------------------------------------
        # Actual intervention outcome
        # -----------------------------------------------------

        if result.outcome.subscription_renewed:
            row["successes"] += 1

        row["expected_value"] += (
            result.decision.expected_net_revenue
        )

        # -----------------------------------------------------
        # Baseline counterfactual
        # -----------------------------------------------------

        baseline = simulate_baseline(
            state=state,
            subscription=subscription,
            seed=seed + index,
        )

        actual_incremental_value = (
            result.outcome.revenue_preserved
            - baseline.revenue_preserved
            - result.outcome.intervention_cost
        )

        row["actual_value"] += (
            actual_incremental_value
        )

    # ---------------------------------------------------------
    # 4. Build calibration results
    # ---------------------------------------------------------

    results: list[CalibrationStats] = []

    for action, row in data.items():

        decisions = int(row["decisions"])

        if decisions == 0:
            continue

        expected_probability = (
            row["expected_probability"]
            / decisions
        )

        actual_success_rate = (
            row["successes"]
            / decisions
        )

        calibration_error = (
            actual_success_rate
            - expected_probability
        )

        results.append(
            CalibrationStats(
                action=action,
                decisions=decisions,
                expected_success_probability=(
                    expected_probability
                ),
                actual_success_rate=(
                    actual_success_rate
                ),
                calibration_error=(
                    calibration_error
                ),
                expected_incremental_value=(
                    row["expected_value"]
                ),
                actual_incremental_value=(
                    row["actual_value"]
                ),
            )
        )

    return sorted(
        results,
        key=lambda result: result.action,
    )


if __name__ == "__main__":

    results = run_calibration(
        customer_count=10_000,
        seed=42,
    )

    print("REVEN CALIBRATION ANALYSIS")
    print("=" * 65)

    for result in results:

        print("\n" + "-" * 65)

        print(
            f"Action: "
            f"{result.action}"
        )

        print(
            f"Decisions: "
            f"{result.decisions:,}"
        )

        print(
            f"Expected success probability: "
            f"{result.expected_success_probability:.2%}"
        )

        print(
            f"Actual success rate: "
            f"{result.actual_success_rate:.2%}"
        )

        print(
            f"Calibration error: "
            f"{result.calibration_error:+.2%}"
        )

        print(
            f"Expected incremental value: "
            f"₹{result.expected_incremental_value:,.2f}"
        )

        print(
            f"Actual incremental value: "
            f"₹{result.actual_incremental_value:,.2f}"
        )