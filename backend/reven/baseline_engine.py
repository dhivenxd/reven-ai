from __future__ import annotations

from backend.reven.state_engine import CustomerState
from backend.reven.uplift_engine import estimate_baseline_probability
from backend.schemas.streamflix import Outcome


def simulate_baseline(
    state: CustomerState,
    subscription,
    seed: int | None = None,
) -> Outcome:
    """
    Simulate what would happen without a REVEN intervention.

    The baseline uses the same synthetic renewal probability
    as the uplift engine so that policy comparisons remain
    internally consistent.
    """

    import random

    rng = random.Random(seed)

    baseline_probability = (
        estimate_baseline_probability(state)
    )

    renewed = (
        rng.random()
        < baseline_probability
    )

    revenue_preserved = (
        subscription.price
        if renewed
        else 0.0
    )

    return Outcome(
        outcome_id=(
            f"baseline_{state.customer_id}"
        ),
        customer_id=state.customer_id,
        evaluated_at=subscription.current_period_end,
        subscription_renewed=renewed,
        payment_recovered=False,
        churned=not renewed,
        revenue_preserved=revenue_preserved,
        intervention_cost=0.0,
        net_revenue=revenue_preserved,
        reason=(
            f"Baseline outcome "
            f"(simulated probability: "
            f"{baseline_probability:.2%})"
        ),
        intervention_id=None,
    )