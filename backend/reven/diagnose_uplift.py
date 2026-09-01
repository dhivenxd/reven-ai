from __future__ import annotations

from collections import Counter, defaultdict

from backend.reven.decision_engine import get_candidate_interventions, make_decision
from backend.reven.state_engine import build_customer_state
from backend.reven.uplift_engine import (
    MINIMUM_NET_VALUE,
    MINIMUM_UPLIFT,
    MINIMUM_AUTONOMOUS_RISK_SCORE,
    calculate_uplift,
    is_contextually_appropriate,
    is_economically_eligible,
)
from backend.simulator.customer_generator import generate_population
from backend.simulator.event_engine import generate_events


def run_diagnostic(customer_count: int = 10_000, seed: int = 42) -> None:
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

    events_by_customer: dict[str, list] = defaultdict(list)
    for event in events:
        events_by_customer[event.customer_id].append(event)

    states = []
    decisions = []
    eligibility = Counter()
    uplift_values: dict[str, list[float]] = defaultdict(list)
    risk_counts = Counter()

    for customer, subscription in zip(customers, subscriptions):
        state = build_customer_state(
            customer=customer,
            subscription=subscription,
            risk_events=events_by_customer.get(customer.customer_id, []),
        )
        decision = make_decision(state)
        states.append(state)
        decisions.append(decision)
        risk_counts[state.risk_state.value] += 1

        for action in get_candidate_interventions(state):
            if action.value == "no_action":
                continue
            estimate = calculate_uplift(state, action)
            if estimate.incremental_lift > 0:
                eligibility[(action.value, "positive")] += 1
            if is_economically_eligible(estimate):
                eligibility[(action.value, "economic")] += 1
            if is_contextually_appropriate(state, action) and is_economically_eligible(estimate):
                eligibility[(action.value, "final")] += 1
                uplift_values[action.value].append(estimate.incremental_lift)

    decision_counts = Counter(d.intervention_type.value for d in decisions)
    interventions = customer_count - decision_counts["no_action"]

    by_risk: Counter[tuple[str, str]] = Counter()
    for state, decision in zip(states, decisions):
        if decision.intervention_type.value != "no_action":
            by_risk[(state.risk_state.value, "intervention")] += 1

    print()
    print("REVEN UPLIFT DIAGNOSTIC")
    print("=" * 70)
    print("\nPOLICY PARAMETERS")
    print("-" * 70)
    print(f"Minimum uplift: {MINIMUM_UPLIFT:.2%}")
    print(f"Minimum expected net value: ₹{MINIMUM_NET_VALUE:.2f}")
    print(f"Minimum autonomous risk score: {MINIMUM_AUTONOMOUS_RISK_SCORE:.1f}/100")

    print("\nCUSTOMER RISK DISTRIBUTION")
    print("-" * 70)
    for state in ("healthy", "watch", "at_risk", "critical"):
        count = risk_counts[state]
        print(f"{state:<12} {count:>6,} ({count / customer_count:.2%})")

    print("\nACTION ELIGIBILITY")
    print("-" * 70)
    print(f"{'ACTION':<25}{'POSITIVE':>12}{'ECONOMIC':>12}{'FINAL':>12}")
    actions = [
        "payment_retry", "payment_reminder", "renewal_reminder",
        "personalized_offer", "discount", "plan_change", "cancellation_save",
    ]
    for action in actions:
        print(
            f"{action:<25}"
            f"{eligibility[(action, 'positive')]:>12,}"
            f"{eligibility[(action, 'economic')]:>12,}"
            f"{eligibility[(action, 'final')]:>12,}"
        )

    print("\nCURRENT REVEN DECISION DISTRIBUTION")
    print("-" * 70)
    for action, count in sorted(decision_counts.items(), key=lambda x: (-x[1], x[0])):
        print(f"{action:<25} {count:>6,} {count / customer_count:>11.2%}")

    print("\nINTERVENTION SELECTION DIAGNOSTIC")
    print("-" * 70)
    print(f"Customers receiving intervention: {interventions:,}")
    print(f"Intervention rate: {interventions / customer_count:.2%}")

    print("\nINTERVENTION RATE BY RISK STATE")
    print("-" * 70)
    for state in ("healthy", "watch", "at_risk", "critical"):
        total = risk_counts[state]
        selected = by_risk[(state, "intervention")]
        rate = selected / total if total else 0.0
        print(f"{state:<12} {selected:>5,} / {total:<5,} = {rate:.2%}")

    print("\nUPLIFT DISTRIBUTION FOR FINAL-ELIGIBLE ACTIONS")
    print("-" * 70)
    for action in actions:
        values = uplift_values[action]
        if not values:
            continue
        values.sort()
        median = values[len(values) // 2]
        p90 = values[min(len(values) - 1, int(len(values) * 0.90))]
        print(f"\n{action}")
        print(f"  median uplift: {median:.2%}")
        print(f"  p90 uplift:    {p90:.2%}")
        print(f"  max uplift:    {max(values):.2%}")
        print(f"  eligible:      {len(values):,}")

    print("\nDIAGNOSIS")
    print("=" * 70)
    print(f"Current intervention rate: {interventions / customer_count:.2%}")
    if interventions / customer_count >= 0.40:
        print("WARNING: REVEN intervention coverage is above 40%.")
    elif interventions / customer_count >= 0.25:
        print("WARNING: REVEN intervention coverage is relatively high.")
    else:
        print("Intervention coverage is below 25%.")

    print("\nDiagnostic does not modify policy parameters.")
    print("Counterfactual outcomes are generated independently from decision probabilities.")
    print("=" * 70)


if __name__ == "__main__":
    run_diagnostic()
