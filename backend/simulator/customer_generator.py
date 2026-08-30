from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from pathlib import Path
import sys

# Allow importing schemas when this file is run directly.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.schemas.streamflix import (  # noqa: E402
    Customer,
    Subscription,
    SubscriptionStatus,
)


PLANS = {
    "basic": {
        "price": 199.0,
        "currency": "INR",
        "period_days": 30,
    },
    "standard": {
        "price": 399.0,
        "currency": "INR",
        "period_days": 30,
    },
    "premium": {
        "price": 599.0,
        "currency": "INR",
        "period_days": 30,
    },
}


def generate_customer(
    index: int,
    rng: random.Random,
    today: date,
) -> tuple[Customer, Subscription]:
    customer_id = f"cust_{index:06d}"
    subscription_id = f"sub_{index:06d}"

    # Tenure distribution: mostly established customers,
    # with a meaningful population of newer customers.
    tenure_days = int(rng.triangular(30, 1095, 240))
    signup_date = today - timedelta(days=tenure_days)

    plan_id = rng.choices(
        population=list(PLANS.keys()),
        weights=[0.35, 0.45, 0.20],
        k=1,
    )[0]

    plan = PLANS[plan_id]

        # Calibrated loosely around the observed KKBOX behavior:
    # auto-renew is common, but not universal.
    auto_renew = rng.random() < 0.785

    period_days = plan["period_days"]

    # Place the customer at a random point in their current billing cycle.
    # This creates realistic renewal timing instead of making everyone renew
    # on the same date.
    days_since_period_start = rng.randint(0, period_days - 1)

    current_period_end = today + timedelta(
        days=period_days - days_since_period_start
    )

    current_period_start = current_period_end - timedelta(
        days=period_days
    )

    customer = Customer(
        customer_id=customer_id,
        signup_date=signup_date,
        tenure_days=tenure_days,
        current_plan_id=plan_id,
        current_subscription_status=SubscriptionStatus.ACTIVE,
        lifetime_value=round(
            plan["price"] * max(1, tenure_days // period_days),
            2,
        ),
        created_at=datetime.combine(
            signup_date,
            datetime.min.time(),
        ),
    )

    subscription = Subscription(
        subscription_id=subscription_id,
        customer_id=customer_id,
        plan_id=plan_id,
        status=SubscriptionStatus.ACTIVE,
        start_date=signup_date,
        current_period_start=current_period_start,
        current_period_end=current_period_end,
        price=plan["price"],
        currency=plan["currency"],
        auto_renew=auto_renew,
    )

    return customer, subscription


def generate_population(
    count: int = 10_000,
    seed: int = 42,
    today: date | None = None,
) -> tuple[list[Customer], list[Subscription]]:
    if count <= 0:
        raise ValueError("count must be greater than zero")

    rng = random.Random(seed)
    today = today or date.today()

    customers: list[Customer] = []
    subscriptions: list[Subscription] = []

    for index in range(1, count + 1):
        customer, subscription = generate_customer(index, rng, today)
        customers.append(customer)
        subscriptions.append(subscription)

    return customers, subscriptions


if __name__ == "__main__":
    customers, subscriptions = generate_population()

    print("STREAMFLIX CUSTOMER GENERATOR")
    print("=" * 40)
    print(f"Customers generated: {len(customers)}")
    print(f"Subscriptions generated: {len(subscriptions)}")

    auto_renew_count = sum(
        subscription.auto_renew for subscription in subscriptions
    )

    print(
        f"Auto-renew rate: "
        f"{auto_renew_count / len(subscriptions):.2%}"
    )

    renewal_0_3 = 0
    renewal_4_7 = 0
    renewal_8_30 = 0

    for subscription in subscriptions:
        days_until_renewal = (
            subscription.current_period_end - date.today()
        ).days

        if 0 <= days_until_renewal <= 3:
            renewal_0_3 += 1
        elif 4 <= days_until_renewal <= 7:
            renewal_4_7 += 1
        elif 8 <= days_until_renewal <= 30:
            renewal_8_30 += 1

    print(f"Renewing in 0–3 days: {renewal_0_3}")
    print(f"Renewing in 4–7 days: {renewal_4_7}")
    print(f"Renewing in 8–30 days: {renewal_8_30}")

    print("\nSample customer:")
    print(customers[0])

    print("\nSample subscription:")
    print(subscriptions[0])