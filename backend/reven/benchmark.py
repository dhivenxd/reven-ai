from __future__ import annotations

from dataclasses import dataclass, field

from backend.reven.baseline_engine import simulate_baseline
from backend.reven.reven_engine import run_reven
from backend.reven.state_engine import build_customer_state
from backend.simulator.customer_generator import generate_population
from backend.simulator.event_engine import generate_events


@dataclass
class InterventionStats:
    decisions: int = 0
    successes: int = 0
    failures: int = 0
    revenue: float = 0.0
    cost: float = 0.0
    incremental_revenue: float = 0.0


@dataclass
class BenchmarkResult:
    total_customers: int
    interventions: int
    no_action: int

    baseline_renewals: int
    reven_renewals: int

    baseline_revenue: float
    reven_revenue: float
    intervention_cost: float

    reven_net_revenue: float
    incremental_net_revenue: float
    roi: float

    intervention_stats: dict[str, InterventionStats] = field(
        default_factory=dict
    )


def run_benchmark(
    customer_count: int = 10_000,
    seed: int = 42,
) -> BenchmarkResult:

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

    baseline_revenue = 0.0
    reven_revenue = 0.0
    intervention_cost = 0.0

    baseline_renewals = 0
    reven_renewals = 0

    interventions = 0
    no_action = 0

    stats: dict[str, InterventionStats] = {}

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

        # -----------------------------------------------------
        # BASELINE
        # -----------------------------------------------------

        baseline = simulate_baseline(
            state=state,
            subscription=subscription,
            seed=seed + index,
        )

        if baseline.subscription_renewed:
            baseline_renewals += 1

        baseline_revenue += baseline.revenue_preserved

        # -----------------------------------------------------
        # REVEN
        # -----------------------------------------------------

        reven = run_reven(
            customer=customer,
            subscription=subscription,
            risk_events=customer_events,
            seed=seed + index,
        )

        action = reven.decision.intervention_type.value

        # -----------------------------------------------------
        # NO ACTION
        # -----------------------------------------------------

        if action == "no_action":

            no_action += 1

            if baseline.subscription_renewed:
                reven_renewals += 1

            reven_revenue += baseline.revenue_preserved

            continue

        # -----------------------------------------------------
        # INTERVENTION
        # -----------------------------------------------------

        interventions += 1

        intervention_stats = stats.setdefault(
            action,
            InterventionStats(),
        )

        intervention_stats.decisions += 1

        if reven.outcome.subscription_renewed:
            reven_renewals += 1
            intervention_stats.successes += 1
        else:
            intervention_stats.failures += 1

        actual_revenue = (
            reven.outcome.revenue_preserved
        )

        actual_cost = (
            reven.outcome.intervention_cost
        )

        # Incremental revenue against THIS customer's
        # baseline outcome.
        customer_incremental_revenue = (
            actual_revenue
            - baseline.revenue_preserved
        )

        intervention_stats.revenue += actual_revenue
        intervention_stats.cost += actual_cost
        intervention_stats.incremental_revenue += (
            customer_incremental_revenue
        )

        reven_revenue += actual_revenue
        intervention_cost += actual_cost

    # ---------------------------------------------------------
    # FINAL FINANCIAL RESULTS
    # ---------------------------------------------------------

    reven_net_revenue = (
        reven_revenue
        - intervention_cost
    )

    incremental_net_revenue = (
        reven_net_revenue
        - baseline_revenue
    )

    if intervention_cost > 0:
        roi = (
            incremental_net_revenue
            / intervention_cost
        )
    else:
        roi = 0.0

    return BenchmarkResult(
        total_customers=customer_count,
        interventions=interventions,
        no_action=no_action,
        baseline_renewals=baseline_renewals,
        reven_renewals=reven_renewals,
        baseline_revenue=baseline_revenue,
        reven_revenue=reven_revenue,
        intervention_cost=intervention_cost,
        reven_net_revenue=reven_net_revenue,
        incremental_net_revenue=incremental_net_revenue,
        roi=roi,
        intervention_stats=stats,
    )


if __name__ == "__main__":

    result = run_benchmark(
        customer_count=10_000,
        seed=42,
    )

    print("REVEN FAIR BENCHMARK")
    print("=" * 60)

    print("\nCUSTOMER COVERAGE")
    print("-" * 60)

    print(
        f"Total customers: "
        f"{result.total_customers:,}"
    )

    print(
        f"Interventions: "
        f"{result.interventions:,}"
    )

    print(
        f"No action: "
        f"{result.no_action:,}"
    )

    intervention_rate = (
        result.interventions
        / result.total_customers
    )

    print(
        f"Intervention rate: "
        f"{intervention_rate:.2%}"
    )

    print("\nRENEWAL OUTCOMES")
    print("-" * 60)

    print(
        f"Baseline renewals: "
        f"{result.baseline_renewals:,}"
    )

    print(
        f"REVEN renewals: "
        f"{result.reven_renewals:,}"
    )

    print(
        f"Additional renewals: "
        f"{result.reven_renewals - result.baseline_renewals:+,}"
    )

    print("\nTOTAL ECONOMICS")
    print("-" * 60)

    print(
        f"Baseline revenue: "
        f"₹{result.baseline_revenue:,.2f}"
    )

    print(
        f"REVEN revenue: "
        f"₹{result.reven_revenue:,.2f}"
    )

    print(
        f"Intervention cost: "
        f"₹{result.intervention_cost:,.2f}"
    )

    print(
        f"REVEN net revenue: "
        f"₹{result.reven_net_revenue:,.2f}"
    )

    print(
        f"Incremental net revenue: "
        f"₹{result.incremental_net_revenue:,.2f}"
    )

    print(
        f"ROI on intervention spend: "
        f"{result.roi:.2f}x"
    )

    print("\nINTERVENTION PERFORMANCE")
    print("-" * 60)

    for action, stats in sorted(
        result.intervention_stats.items()
    ):

        net_incremental = (
            stats.incremental_revenue
            - stats.cost
        )

        print(f"\n{action}")

        print(
            f"  decisions: "
            f"{stats.decisions:,}"
        )

        print(
            f"  successes: "
            f"{stats.successes:,}"
        )

        print(
            f"  failures: "
            f"{stats.failures:,}"
        )

        success_rate = (
            stats.successes
            / stats.decisions
            if stats.decisions
            else 0.0
        )

        print(
            f"  success rate: "
            f"{success_rate:.2%}"
        )

        print(
            f"  revenue preserved: "
            f"₹{stats.revenue:,.2f}"
        )

        print(
            f"  intervention cost: "
            f"₹{stats.cost:,.2f}"
        )

        print(
            f"  incremental revenue: "
            f"₹{stats.incremental_revenue:,.2f}"
        )

        print(
            f"  incremental net revenue: "
            f"₹{net_incremental:,.2f}"
        )