from __future__ import annotations

from dataclasses import dataclass, field

from backend.reven.baseline_engine import simulate_baseline
from backend.reven.decision_engine import (
    get_candidate_interventions,
    make_decision,
)
from backend.reven.economic_engine import (
    DISCOUNT_RATE,
    INTERVENTION_COSTS,
    PLAN_CHANGE_REVENUE_FACTOR,
    estimate_baseline_probability,
    estimate_intervention_probability,
)
from backend.reven.intervention_engine import build_intervention
from backend.reven.state_engine import build_customer_state
from backend.reven.uplift_engine import (
    MINIMUM_NET_VALUE,
    MINIMUM_UPLIFT,
)
from backend.schemas.streamflix import InterventionType
from backend.simulator.customer_generator import generate_population
from backend.simulator.event_engine import generate_events
from backend.simulator.outcome_engine import simulate_outcome


# ============================================================
# METRICS
# ============================================================

@dataclass
class ActionMetrics:
    selected: int = 0
    renewals: int = 0
    revenue: float = 0.0
    cost: float = 0.0


@dataclass
class PolicyMetrics:
    interventions: int = 0
    no_action: int = 0
    renewals: int = 0
    revenue: float = 0.0
    intervention_cost: float = 0.0
    actions: dict[str, ActionMetrics] = field(default_factory=dict)


@dataclass
class TransitionMetrics:
    customers: int = 0
    original_renewals: int = 0
    current_renewals: int = 0
    original_revenue: float = 0.0
    current_revenue: float = 0.0


# ============================================================
# LEGACY POLICY
# ============================================================

def legacy_success_probability(state, action: InterventionType) -> float:
    """The legacy synthetic policy model kept for comparison."""

    if action == InterventionType.PAYMENT_RETRY:
        probability = 0.55
        if state.payment_failure:
            probability += 0.10
        if state.auto_renew:
            probability += 0.05
        if state.cancellation_requested:
            probability -= 0.25

    elif action == InterventionType.PAYMENT_REMINDER:
        probability = 0.40
        if state.payment_failure:
            probability += 0.10

    elif action == InterventionType.RENEWAL_REMINDER:
        probability = 0.45
        if state.renewal_due:
            probability += 0.10
        if state.cancellation_requested:
            probability -= 0.20

    elif action == InterventionType.PERSONALIZED_OFFER:
        probability = 0.50
        if state.engagement_declining:
            probability += 0.10
        if state.inactive:
            probability -= 0.10

    elif action == InterventionType.DISCOUNT:
        probability = 0.65
        if state.cancellation_requested:
            probability += 0.05

    elif action == InterventionType.PLAN_CHANGE:
        probability = 0.55
        if state.cancellation_requested:
            probability += 0.05

    elif action == InterventionType.CANCELLATION_SAVE:
        probability = 0.45
        if state.cancellation_requested:
            probability += 0.15

    else:
        probability = 0.0

    return max(0.0, min(probability, 0.95))


def choose_legacy_action(state) -> InterventionType:
    """
    Legacy policy chooses the best positive expected incremental
    value under the legacy probability model.
    """

    baseline = estimate_baseline_probability(state)
    price = state.subscription_price
    baseline_revenue = baseline * price

    best_action = InterventionType.NO_ACTION
    best_value = 0.0

    for action in get_candidate_interventions(state):
        if action == InterventionType.NO_ACTION:
            continue

        probability = legacy_success_probability(state, action)

        incremental_revenue = (
            probability * price
            - baseline_revenue
        )

        expected_net = (
            incremental_revenue
            - INTERVENTION_COSTS[action]
        )

        if expected_net > best_value:
            best_value = expected_net
            best_action = action

    return best_action


def build_legacy_decision(state):
    """
    Create a RevenueDecision-shaped object for the legacy policy.

    We construct it from the same economic evaluation objects used
    by REVEN so the intervention layer remains unchanged.
    """

    from backend.reven.economic_engine import InterventionEconomics

    baseline = estimate_baseline_probability(state)
    price = state.subscription_price
    baseline_revenue = baseline * price

    evaluations = []

    for action in get_candidate_interventions(state):
        probability = (
            baseline
            if action == InterventionType.NO_ACTION
            else legacy_success_probability(state, action)
        )

        if action == InterventionType.DISCOUNT:
            gross_revenue = price * (1.0 - DISCOUNT_RATE)
        elif action == InterventionType.PLAN_CHANGE:
            gross_revenue = price * PLAN_CHANGE_REVENUE_FACTOR
        else:
            gross_revenue = price

        expected_revenue = probability * gross_revenue
        baseline_expected_revenue = baseline_revenue
        incremental_revenue = expected_revenue - baseline_expected_revenue
        # Keep lift as probability lift for diagnostics; economics are
        # calculated from the actual revenue preserved by the action.
        lift = probability - baseline
        cost = INTERVENTION_COSTS[action]
        expected_net = incremental_revenue - cost

        evaluations.append(
            InterventionEconomics(
                intervention_type=action,
                success_probability=probability,
                baseline_probability=baseline,
                gross_revenue_if_success=gross_revenue,
                baseline_expected_revenue=baseline_revenue,
                expected_revenue=expected_revenue,
                incremental_lift=lift,
                incremental_revenue=incremental_revenue,
                intervention_cost=cost,
                offer_cost=0.0,
                expected_net_revenue=expected_net,
            )
        )

    best_action = choose_legacy_action(state)
    best_eval = next(
        e for e in evaluations
        if e.intervention_type == best_action
    )

    profitable = [
        e for e in evaluations
        if e.intervention_type != InterventionType.NO_ACTION
        and e.expected_net_revenue > 0
    ]

    other = sorted(
        (
            e.expected_net_revenue
            for e in profitable
            if e.intervention_type != best_action
        ),
        reverse=True,
    )

    if other:
        margin = best_eval.expected_net_revenue - other[0]
        confidence = min(
            1.0,
            max(
                0.50,
                0.50
                + margin / max(abs(best_eval.expected_net_revenue), 1.0)
                * 0.50,
            ),
        )
    else:
        confidence = 0.75

    return type(
        "LegacyDecision",
        (),
        {
            "customer_id": state.customer_id,
            "intervention_type": best_action,
            "expected_net_revenue": best_eval.expected_net_revenue,
            "confidence": confidence,
            "reason": (
                f"Legacy policy selected {best_action.value} "
                f"using legacy expected economics."
            ),
            "alternatives": evaluations,
        },
    )()


# ============================================================
# CURRENT / UPLIFT POLICY
# ============================================================

def choose_current_decision(state):
    """
    Current REVEN policy.

    The production decision engine is the source of truth for
    uplift-based economic selection.
    """

    return make_decision(state)


# ============================================================
# PROBABILITY HANDOFF
# ============================================================

def get_selected_probability(decision) -> float:
    for evaluation in decision.alternatives:
        if evaluation.intervention_type == decision.intervention_type:
            return evaluation.success_probability

    return 0.0


# ============================================================
# EXECUTION
# ============================================================

def execute_policy(
    decision,
    subscription,
    customer_events,
    seed: int,
    baseline,
    metrics: PolicyMetrics,
):
    action = decision.intervention_type

    action_metrics = metrics.actions.setdefault(
        action.value,
        ActionMetrics(),
    )

    action_metrics.selected += 1

    # Control arm uses the SAME realized baseline outcome.
    if action == InterventionType.NO_ACTION:
        metrics.no_action += 1

        if baseline.subscription_renewed:
            metrics.renewals += 1
            action_metrics.renewals += 1

        metrics.revenue += baseline.revenue_preserved
        action_metrics.revenue += baseline.revenue_preserved

        return {
            "renewed": baseline.subscription_renewed,
            "revenue": baseline.revenue_preserved,
            "cost": 0.0,
        }

    metrics.interventions += 1

    intervention_plan = build_intervention(decision)
    # Benchmark outcomes must come from an independent simulator
    # response model. Otherwise the policy is rewarded using the
    # same probabilities it used to choose the action.
    outcome = simulate_outcome(
        intervention=intervention_plan.intervention,
        subscription=subscription,
        risk_events=customer_events,
        seed=seed,
    )

    if outcome.subscription_renewed:
        metrics.renewals += 1
        action_metrics.renewals += 1

    metrics.revenue += outcome.revenue_preserved
    metrics.intervention_cost += outcome.intervention_cost

    action_metrics.revenue += outcome.revenue_preserved
    action_metrics.cost += outcome.intervention_cost

    return {
        "renewed": outcome.subscription_renewed,
        "revenue": outcome.revenue_preserved,
        "cost": outcome.intervention_cost,
    }


# ============================================================
# PRINTING
# ============================================================

def print_policy(title: str, metrics: PolicyMetrics, customer_count: int):
    print()
    print(title)
    print("-" * 65)

    rate = metrics.interventions / customer_count

    print(f"Interventions: {metrics.interventions:,}")
    print(f"No action: {metrics.no_action:,}")
    print(f"Intervention rate: {rate:.2%}")
    print(f"Renewals: {metrics.renewals:,}")


def print_action_performance(title: str, metrics: PolicyMetrics):
    print()
    print(title)
    print("-" * 65)

    for action, data in sorted(metrics.actions.items()):
        if data.selected == 0:
            continue

        rate = data.renewals / data.selected
        net = data.revenue - data.cost

        print()
        print(action)
        print(f"  selected: {data.selected:,}")
        print(f"  renewals: {data.renewals:,}")
        print(f"  renewal rate: {rate:.2%}")
        print(f"  revenue: ₹{data.revenue:,.2f}")
        print(f"  cost: ₹{data.cost:,.2f}")
        print(f"  net revenue: ₹{net:,.2f}")


# ============================================================
# BENCHMARK
# ============================================================

def run_uplift_benchmark(
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

    baseline_revenue = 0.0
    baseline_renewals = 0

    legacy = PolicyMetrics()
    current = PolicyMetrics()

    transitions: dict[
        tuple[str, str],
        TransitionMetrics,
    ] = {}

    decision_changes = 0

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

        if baseline.subscription_renewed:
            baseline_renewals += 1

        legacy_decision = build_legacy_decision(state)
        current_decision = choose_current_decision(state)

        legacy_action = legacy_decision.intervention_type
        current_action = current_decision.intervention_type

        if legacy_action != current_action:
            decision_changes += 1

        policy_seed = seed + 100_000 + index

        legacy_result = execute_policy(
            decision=legacy_decision,
            subscription=subscription,
            customer_events=customer_events,
            seed=policy_seed,
            baseline=baseline,
            metrics=legacy,
        )

        current_result = execute_policy(
            decision=current_decision,
            subscription=subscription,
            customer_events=customer_events,
            seed=policy_seed,
            baseline=baseline,
            metrics=current,
        )

        if legacy_action != current_action:

            key = (
                legacy_action.value,
                current_action.value,
            )

            transition = transitions.setdefault(
                key,
                TransitionMetrics(),
            )

            transition.customers += 1

            if legacy_result["renewed"]:
                transition.original_renewals += 1

            if current_result["renewed"]:
                transition.current_renewals += 1

            transition.original_revenue += legacy_result["revenue"]
            transition.current_revenue += current_result["revenue"]

    # ========================================================
    # FINANCIALS
    # ========================================================

    legacy_net = legacy.revenue - legacy.intervention_cost
    current_net = current.revenue - current.intervention_cost

    legacy_incremental = legacy_net - baseline_revenue
    current_incremental = current_net - baseline_revenue

    legacy_roi = (
        legacy_incremental / legacy.intervention_cost
        if legacy.intervention_cost
        else 0.0
    )

    current_roi = (
        current_incremental / current.intervention_cost
        if current.intervention_cost
        else 0.0
    )

    # ========================================================
    # OUTPUT
    # ========================================================

    print()
    print("REVEN UPLIFT BENCHMARK")
    print("=" * 65)

    print()
    print("BASELINE")
    print("-" * 65)
    print(f"Customers: {customer_count:,}")
    print(f"Renewals: {baseline_renewals:,}")
    print(f"Revenue: ₹{baseline_revenue:,.2f}")

    print()
    print("LEGACY REVEN")
    print("-" * 65)
    print(f"Interventions: {legacy.interventions:,}")
    print(f"No action: {legacy.no_action:,}")
    print(f"Intervention rate: {legacy.interventions / customer_count:.2%}")
    print(f"Renewals: {legacy.renewals:,}")
    print(f"Additional renewals: {legacy.renewals - baseline_renewals:+,}")
    print(f"Revenue: ₹{legacy.revenue:,.2f}")
    print(f"Intervention cost: ₹{legacy.intervention_cost:,.2f}")
    print(f"Net revenue: ₹{legacy_net:,.2f}")
    print(f"Incremental net revenue: ₹{legacy_incremental:,.2f}")
    print(f"ROI: {legacy_roi:.2f}x")

    print()
    print("CURRENT REVEN")
    print("-" * 65)
    print(f"Interventions: {current.interventions:,}")
    print(f"No action: {current.no_action:,}")
    print(f"Intervention rate: {current.interventions / customer_count:.2%}")
    print(f"Renewals: {current.renewals:,}")
    print(f"Additional renewals: {current.renewals - baseline_renewals:+,}")
    print(f"Revenue: ₹{current.revenue:,.2f}")
    print(f"Intervention cost: ₹{current.intervention_cost:,.2f}")
    print(f"Net revenue: ₹{current_net:,.2f}")
    print(f"Incremental net revenue: ₹{current_incremental:,.2f}")
    print(f"ROI: {current_roi:.2f}x")

    print_action_performance(
        "LEGACY ACTION PERFORMANCE",
        legacy,
    )

    print_action_performance(
        "CURRENT ACTION PERFORMANCE",
        current,
    )

    print()
    print("POLICY TRANSITIONS")
    print("-" * 65)

    for (old, new), transition in sorted(
        transitions.items(),
        key=lambda item: item[1].customers,
        reverse=True,
    ):

        print()
        print(f"{old} -> {new}")
        print(f"  customers: {transition.customers:,}")
        print(f"  legacy renewals: {transition.original_renewals:,}")
        print(f"  current renewals: {transition.current_renewals:,}")
        print(
            f"  renewal change: "
            f"{transition.current_renewals - transition.original_renewals:+,}"
        )
        print(
            f"  revenue change: "
            f"₹{transition.current_revenue - transition.original_revenue:,.2f}"
        )

    print()
    print("POLICY IMPACT")
    print("-" * 65)

    print(f"Decision changes: {decision_changes:,}")
    print(
        f"Renewal change vs legacy: "
        f"{current.renewals - legacy.renewals:+,}"
    )
    print(
        f"Intervention change vs legacy: "
        f"{current.interventions - legacy.interventions:+,}"
    )
    print(
        f"Net revenue change vs legacy: "
        f"₹{current_net - legacy_net:,.2f}"
    )
    print(
        f"Incremental net revenue change: "
        f"₹{current_incremental - legacy_incremental:,.2f}"
    )
    print(
        f"ROI change vs legacy: "
        f"{current_roi - legacy_roi:+.2f}x"
    )

    print()
    print("VERDICT")
    print("-" * 65)

    if current_incremental > legacy_incremental:
        print(
            "CURRENT REVEN OUTPERFORMS "
            "LEGACY REVEN ON INCREMENTAL NET REVENUE."
        )
    elif current_incremental < legacy_incremental:
        print(
            "LEGACY REVEN OUTPERFORMS "
            "CURRENT REVEN ON INCREMENTAL NET REVENUE."
        )
    else:
        print(
            "CURRENT AND LEGACY REVEN HAVE "
            "EQUAL INCREMENTAL NET REVENUE."
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="REVEN uplift benchmark",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for population/event generation (default: 42)",
    )
    parser.add_argument(
        "--customers",
        type=int,
        default=10_000,
        help="Number of customers to simulate (default: 10000)",
    )
    args = parser.parse_args()

    run_uplift_benchmark(
        customer_count=args.customers,
        seed=args.seed,
    )
