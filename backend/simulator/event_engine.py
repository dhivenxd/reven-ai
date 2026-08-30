from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.schemas.streamflix import (  # noqa: E402
    Customer,
    RiskEvent,
    RiskEventType,
    RiskSeverity,
    Subscription,
)


def generate_events(
    customers: list[Customer],
    subscriptions: list[Subscription],
    seed: int = 42,
    observation_days: int = 30,
) -> list[RiskEvent]:
    """Generate realistic risk events for an observation period."""

    if len(customers) != len(subscriptions):
        raise ValueError("customers and subscriptions must have equal length")

    if observation_days <= 0:
        raise ValueError("observation_days must be greater than zero")

    rng = random.Random(seed)
    events: list[RiskEvent] = []

    today = date.today()

    for customer, subscription in zip(customers, subscriptions):
        # A small portion of customers experience a payment failure.
        if rng.random() < 0.08:
            event_date = today - timedelta(
                days=rng.randint(0, observation_days - 1)
            )

            failure_type = rng.choices(
                [
                    "insufficient_funds",
                    "card_expired",
                    "bank_declined",
                    "network_error",
                    "authentication_required",
                ],
                weights=[35, 15, 25, 15, 10],
                k=1,
            )[0]

            events.append(
                RiskEvent(
                    event_id=f"risk_{len(events) + 1:08d}",
                    customer_id=customer.customer_id,
                    event_type=RiskEventType.PAYMENT_FAILED,
                    occurred_at=datetime.combine(
                        event_date,
                        datetime.min.time(),
                    ),
                    severity=(
                        RiskSeverity.HIGH
                        if failure_type
                        in {"card_expired", "bank_declined"}
                        else RiskSeverity.MEDIUM
                    ),
                    metadata={
                        "failure_reason": failure_type,
                    },
                )
            )

        # Some customers show declining engagement.
        if rng.random() < 0.15:
            event_date = today - timedelta(
                days=rng.randint(0, observation_days - 1)
            )

            events.append(
                RiskEvent(
                    event_id=f"risk_{len(events) + 1:08d}",
                    customer_id=customer.customer_id,
                    event_type=RiskEventType.ENGAGEMENT_DECLINE,
                    occurred_at=datetime.combine(
                        event_date,
                        datetime.min.time(),
                    ),
                    severity=RiskSeverity.MEDIUM,
                    metadata={
                        "decline_percentage": round(
                            rng.uniform(20, 60),
                            2,
                        )
                    },
                )
            )

        # A smaller group becomes inactive.
        if rng.random() < 0.07:
            event_date = today - timedelta(
                days=rng.randint(0, observation_days - 1)
            )

            events.append(
                RiskEvent(
                    event_id=f"risk_{len(events) + 1:08d}",
                    customer_id=customer.customer_id,
                    event_type=RiskEventType.INACTIVITY,
                    occurred_at=datetime.combine(
                        event_date,
                        datetime.min.time(),
                    ),
                    severity=RiskSeverity.MEDIUM,
                    metadata={
                        "inactive_days": rng.randint(7, 30),
                    },
                )
            )

        # Renewal becomes a risk event when the period is approaching expiry.
        days_until_expiry = (
            subscription.current_period_end - today
        ).days

        if 0 <= days_until_expiry <= 7:
            events.append(
                RiskEvent(
                    event_id=f"risk_{len(events) + 1:08d}",
                    customer_id=customer.customer_id,
                    event_type=RiskEventType.RENEWAL_DUE,
                    occurred_at=datetime.combine(
                        today,
                        datetime.min.time(),
                    ),
                    severity=RiskSeverity.HIGH,
                    metadata={
                        "days_until_expiry": days_until_expiry,
                        "auto_renew": subscription.auto_renew,
                    },
                )
            )

    return events


if __name__ == "__main__":
    from backend.simulator.customer_generator import generate_population

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

    print("STREAMFLIX EVENT ENGINE")
    print("=" * 40)
    print(f"Customers: {len(customers)}")
    print(f"Events generated: {len(events)}")

    event_counts: dict[str, int] = {}

    for event in events:
        key = event.event_type.value
        event_counts[key] = event_counts.get(key, 0) + 1

    print("\nEvent distribution:")
    for event_type, count in sorted(event_counts.items()):
        print(f"  {event_type}: {count}")

    print("\nSample events:")
    for event in events[:5]:
        print(event)