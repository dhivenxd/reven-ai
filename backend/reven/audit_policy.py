from __future__ import annotations

from collections import Counter

from backend.reven.reven_engine import run_reven
from backend.reven.state_engine import build_customer_state
from backend.simulator.customer_generator import generate_population
from backend.simulator.event_engine import generate_events


if __name__ == "__main__":

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

    events_by_customer: dict[str, list] = {}

    for event in events:
        events_by_customer.setdefault(
            event.customer_id,
            [],
        ).append(event)

    action_counts = Counter()

    renewal_reminder_cases = []

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

        result = run_reven(
            customer=customer,
            subscription=subscription,
            risk_events=customer_events,
            seed=42 + index,
        )

        action = (
            result.decision.intervention_type.value
        )

        action_counts[action] += 1

        if action == "renewal_reminder":
            renewal_reminder_cases.append(
                (
                    state,
                    result.decision,
                )
            )

    print("REVEN POLICY AUDIT")
    print("=" * 60)

    print("\nACTION DISTRIBUTION")
    print("-" * 60)

    for action, count in action_counts.most_common():
        print(f"{action}: {count}")

    print("\nRENEWAL REMINDER CASES")
    print("-" * 60)

    print(
        f"Total renewal reminders: "
        f"{len(renewal_reminder_cases)}"
    )

    for state, decision in renewal_reminder_cases[:20]:

        print("\n" + "-" * 60)

        print(
            f"Customer: "
            f"{state.customer_id}"
        )

        print(
            f"Risk state: "
            f"{state.risk_state.value}"
        )

        print(
            f"Risk score: "
            f"{state.risk_score:.1f}"
        )

        print(
            f"Days until renewal: "
            f"{state.days_until_renewal}"
        )

        print(
            f"Auto-renew: "
            f"{state.auto_renew}"
        )

        print(
            f"Payment failure: "
            f"{state.payment_failure}"
        )

        print(
            f"Cancellation: "
            f"{state.cancellation_requested}"
        )

        print(
            f"Engagement decline: "
            f"{state.engagement_declining}"
        )

        print(
            f"Inactive: "
            f"{state.inactive}"
        )

        print(
            f"Decision: "
            f"{decision.intervention_type.value}"
        )

        print(
            f"Expected incremental value: "
            f"₹{decision.expected_net_revenue:.2f}"
        )

        print(
            f"Reason: "
            f"{decision.reason}"
        )