from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.schemas.streamflix import (
    Customer,
    RiskEvent,
    RiskEventType,
    RiskSeverity,
    Subscription,
)


# These are SYNTHETIC assumptions.
# They are not directly measured by KKBOX.
PAYMENT_FAILURE_RATE = 0.08
ENGAGEMENT_DECLINE_RATE = 0.15
INACTIVITY_RATE = 0.07
CANCELLATION_RATE = 0.025


def create_event(
    customer_id: str,
    event_type: RiskEventType,
    occurred_at: datetime,
    severity: RiskSeverity,
    metadata: dict,
    event_number: int,
) -> RiskEvent:
    return RiskEvent(
        event_id=f"risk_{event_number:08d}",
        customer_id=customer_id,
        event_type=event_type,
        occurred_at=occurred_at,
        severity=severity,
        metadata=metadata,
    )


def generate_events(
    customers: list[Customer],
    subscriptions: list[Subscription],
    seed: int = 42,
    observation_days: int = 30,
) -> list[RiskEvent]:

    if len(customers) != len(subscriptions):
        raise ValueError("customers and subscriptions must have equal length")

    if observation_days <= 0:
        raise ValueError("observation_days must be greater than zero")

    rng = random.Random(seed)
    events: list[RiskEvent] = []

    today = date.today()

    for customer, subscription in zip(customers, subscriptions):

        days_until_renewal = (
            subscription.current_period_end - today
        ).days

        event_date = today - timedelta(
            days=rng.randint(0, observation_days - 1)
        )

        # ---------------------------------------------------------
        # 1. RENEWAL DUE
        # ---------------------------------------------------------
        # This is deterministic from the subscription state.
        if 0 <= days_until_renewal <= 7:
            severity = (
                RiskSeverity.CRITICAL
                if not subscription.auto_renew
                else RiskSeverity.HIGH
            )

            events.append(
                create_event(
                    customer.customer_id,
                    RiskEventType.RENEWAL_DUE,
                    datetime.combine(today, datetime.min.time()),
                    severity,
                    {
                        "days_until_expiry": days_until_renewal,
                        "auto_renew": subscription.auto_renew,
                    },
                    len(events) + 1,
                )
            )

        # ---------------------------------------------------------
        # 2. PAYMENT FAILURE
        # ---------------------------------------------------------
        payment_probability = PAYMENT_FAILURE_RATE

        # Customers approaching renewal are more exposed to
        # payment-related risk.
        if 0 <= days_until_renewal <= 7:
            payment_probability *= 1.5

        if rng.random() < min(payment_probability, 0.30):

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

            severity = (
                RiskSeverity.HIGH
                if failure_type in {
                    "card_expired",
                    "bank_declined",
                }
                else RiskSeverity.MEDIUM
            )

            events.append(
                create_event(
                    customer.customer_id,
                    RiskEventType.PAYMENT_FAILED,
                    datetime.combine(event_date, datetime.min.time()),
                    severity,
                    {
                        "failure_reason": failure_type,
                        "days_until_renewal": days_until_renewal,
                    },
                    len(events) + 1,
                )
            )

        # ---------------------------------------------------------
        # 3. ENGAGEMENT DECLINE
        # ---------------------------------------------------------
        engagement_probability = ENGAGEMENT_DECLINE_RATE

        # Renewal pressure makes declining engagement more important.
        if 0 <= days_until_renewal <= 7:
            engagement_probability *= 1.25

        if rng.random() < min(engagement_probability, 0.40):

            decline_percentage = round(
                rng.uniform(20, 60),
                2,
            )

            events.append(
                create_event(
                    customer.customer_id,
                    RiskEventType.ENGAGEMENT_DECLINE,
                    datetime.combine(event_date, datetime.min.time()),
                    RiskSeverity.MEDIUM,
                    {
                        "decline_percentage": decline_percentage,
                        "days_until_renewal": days_until_renewal,
                    },
                    len(events) + 1,
                )
            )

        # ---------------------------------------------------------
        # 4. INACTIVITY
        # ---------------------------------------------------------
        inactivity_probability = INACTIVITY_RATE

        if 0 <= days_until_renewal <= 7:
            inactivity_probability *= 1.25

        if rng.random() < min(inactivity_probability, 0.25):

            inactive_days = rng.randint(7, 30)

            events.append(
                create_event(
                    customer.customer_id,
                    RiskEventType.INACTIVITY,
                    datetime.combine(event_date, datetime.min.time()),
                    RiskSeverity.MEDIUM,
                    {
                        "inactive_days": inactive_days,
                    },
                    len(events) + 1,
                )
            )

        # ---------------------------------------------------------
        # 5. CANCELLATION REQUEST
        # ---------------------------------------------------------
        cancellation_probability = CANCELLATION_RATE

        # Non-auto-renewing customers are more likely to actively
        # cancel because they don't already have automatic renewal.
        if not subscription.auto_renew:
            cancellation_probability *= 1.75

        # Multiple risk signals can increase cancellation pressure.
        # We intentionally keep this probabilistic rather than deterministic.
        if 0 <= days_until_renewal <= 7:
            cancellation_probability *= 1.50

        if rng.random() < min(cancellation_probability, 0.15):

            events.append(
                create_event(
                    customer.customer_id,
                    RiskEventType.CANCELLATION_REQUESTED,
                    datetime.combine(event_date, datetime.min.time()),
                    RiskSeverity.CRITICAL,
                    {
                        "days_until_renewal": days_until_renewal,
                        "auto_renew": subscription.auto_renew,
                    },
                    len(events) + 1,
                )
            )

    events.sort(key=lambda event: event.occurred_at)

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

    print("STREAMFLIX EVENT ENGINE V2")
    print("=" * 40)

    print(f"Customers: {len(customers)}")
    print(f"Events generated: {len(events)}")

    event_counts: dict[str, int] = {}

    for event in events:
        event_type = event.event_type.value
        event_counts[event_type] = (
            event_counts.get(event_type, 0) + 1
        )

    print("\nEvent distribution:")

    for event_type, count in sorted(event_counts.items()):
        print(f"  {event_type}: {count}")

    print("\nSample events:")

    for event in events[:10]:
        print(event)