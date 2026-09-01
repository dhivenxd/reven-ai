from __future__ import annotations

from dataclasses import dataclass

from backend.reven.economic_engine import (
    InterventionEconomics,
    calculate_economics,
)
from backend.reven.calibration_profiles import (
    CalibrationProfile,
)
from backend.reven.uplift_engine import (
    MINIMUM_NET_VALUE,
    MINIMUM_UPLIFT,
    is_contextually_appropriate,
)
from backend.reven.state_engine import CustomerState
from backend.schemas.streamflix import InterventionType


@dataclass
class RevenueDecision:
    customer_id: str
    intervention_type: InterventionType
    expected_net_revenue: float
    confidence: float
    reason: str
    alternatives: list[InterventionEconomics]


def get_candidate_interventions(
    state: CustomerState,
) -> list[InterventionType]:

    candidates = [
        InterventionType.NO_ACTION
    ]

    if state.payment_failure:
        candidates.extend(
            [
                InterventionType.PAYMENT_RETRY,
                InterventionType.PAYMENT_REMINDER,
            ]
        )

    if state.renewal_due:
        candidates.append(
            InterventionType.RENEWAL_REMINDER
        )

    if (
        state.engagement_declining
        or state.inactive
    ):
        candidates.append(
            InterventionType.PERSONALIZED_OFFER
        )

    if state.cancellation_requested:
        candidates.extend(
            [
                InterventionType.CANCELLATION_SAVE,
                InterventionType.PLAN_CHANGE,
                InterventionType.DISCOUNT,
            ]
        )

    return list(dict.fromkeys(candidates))


def _apply_calibration(
    probability: float,
    intervention_type: InterventionType,
    calibration_profiles: dict[
        InterventionType,
        CalibrationProfile,
    ] | None,
) -> float:

    if not calibration_profiles:
        return probability

    profile = calibration_profiles.get(intervention_type)

    if profile is None:
        profile = calibration_profiles.get(intervention_type.value)  # type: ignore[arg-type]

    if profile is None:
        return probability

    return max(
        0.0,
        min(
            probability
            * profile.calibration_factor,
            0.95,
        ),
    )


def make_decision(
    state: CustomerState,
    calibration_profiles: dict[
        InterventionType,
        CalibrationProfile,
    ] | None = None,
) -> RevenueDecision:

    candidates = get_candidate_interventions(
        state
    )

    evaluations: list[
        InterventionEconomics
    ] = []

    for action in candidates:

        evaluation = calculate_economics(
            state=state,
            intervention_type=action,
        )

        if calibration_profiles:

            probability = _apply_calibration(
                evaluation.success_probability,
                action,
                calibration_profiles,
            )

            baseline_revenue = (
                evaluation.baseline_expected_revenue
            )

            expected_revenue = (
                probability
                * evaluation.gross_revenue_if_success
            )

            incremental_revenue = (
                expected_revenue
                - baseline_revenue
            )

            expected_net = (
                incremental_revenue
                - evaluation.intervention_cost
                - evaluation.offer_cost
            )

            evaluation = InterventionEconomics(
                intervention_type=action,
                success_probability=probability,
                baseline_probability=(
                    evaluation.baseline_probability
                ),
                gross_revenue_if_success=(
                    evaluation.gross_revenue_if_success
                ),
                baseline_expected_revenue=(
                    baseline_revenue
                ),
                expected_revenue=expected_revenue,
                incremental_lift=(
                    probability
                    - evaluation.baseline_probability
                ),
                incremental_revenue=(
                    incremental_revenue
                ),
                intervention_cost=(
                    evaluation.intervention_cost
                ),
                offer_cost=(
                    evaluation.offer_cost
                ),
                expected_net_revenue=expected_net,
            )

        evaluations.append(evaluation)

    profitable = [
        evaluation
        for evaluation in evaluations
        if (
            evaluation.intervention_type
            != InterventionType.NO_ACTION
            and is_contextually_appropriate(
                state,
                evaluation.intervention_type,
            )
            and evaluation.incremental_lift >= MINIMUM_UPLIFT
            and evaluation.expected_net_revenue >= MINIMUM_NET_VALUE
        )
    ]

    if not profitable:

        return RevenueDecision(
            customer_id=state.customer_id,
            intervention_type=(
                InterventionType.NO_ACTION
            ),
            expected_net_revenue=0.0,
            confidence=1.0,
            reason=(
                "No eligible intervention has positive "
                "expected incremental net revenue."
            ),
            alternatives=evaluations,
        )

    best = max(
        profitable,
        key=lambda x: x.expected_net_revenue,
    )

    other_values = sorted(
        [
            x.expected_net_revenue
            for x in profitable
            if x.intervention_type
            != best.intervention_type
        ],
        reverse=True,
    )

    if other_values:

        second_best = other_values[0]

        margin = (
            best.expected_net_revenue
            - second_best
        )

        confidence = min(
            1.0,
            max(
                0.50,
                0.50
                + (
                    margin
                    / max(
                        abs(
                            best.expected_net_revenue
                        ),
                        1.0,
                    )
                )
                * 0.50,
            ),
        )

    else:
        confidence = 0.75

    if calibration_profiles:
        prefix = (
            "Selected "
            f"{best.intervention_type.value} using "
            "calibrated expected economics"
        )
    else:
        prefix = (
            "Selected "
            f"{best.intervention_type.value}"
        )

    reason = (
        f"{prefix} because it has the highest "
        "positive expected incremental net revenue "
        "among eligible actions "
        f"(₹{best.expected_net_revenue:.2f})."
    )

    return RevenueDecision(
        customer_id=state.customer_id,
        intervention_type=best.intervention_type,
        expected_net_revenue=(
            best.expected_net_revenue
        ),
        confidence=confidence,
        reason=reason,
        alternatives=evaluations,
    )


if __name__ == "__main__":

    from backend.simulator.customer_generator import (
        generate_population,
    )
    from backend.simulator.event_engine import (
        generate_events,
    )
    from backend.reven.state_engine import (
        build_customer_state,
    )

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

    event_counts: dict[str, int] = {}

    for event in events:
        event_counts[event.customer_id] = (
            event_counts.get(
                event.customer_id,
                0,
            )
            + 1
        )

    customer_id = max(
        event_counts,
        key=event_counts.get,
    )

    customer = next(
        c
        for c in customers
        if c.customer_id == customer_id
    )

    subscription = next(
        s
        for s in subscriptions
        if s.customer_id == customer_id
    )

    customer_events = [
        event
        for event in events
        if event.customer_id == customer_id
    ]

    state = build_customer_state(
        customer=customer,
        subscription=subscription,
        risk_events=customer_events,
    )

    decision = make_decision(state)

    print("REVEN DECISION ENGINE")
    print("=" * 50)

    print(
        f"Customer: {state.customer_id}"
    )

    print(
        f"Risk state: {state.risk_state.value}"
    )

    print(
        f"Risk score: "
        f"{state.risk_score:.1f}/100"
    )

    print("\nREVEN decision:")
    print(
        f"  {decision.intervention_type.value}"
    )

    print(
        "\nExpected incremental net revenue: "
        f"₹{decision.expected_net_revenue:.2f}"
    )

    print(
        "Decision confidence: "
        f"{decision.confidence:.2%}"
    )

    print("\nReason:")
    print(
        f"  {decision.reason}"
    )

    print("\nEligible alternatives:")

    for alternative in decision.alternatives:

        print(
            f"  {alternative.intervention_type.value}: "
            f"₹{alternative.expected_net_revenue:.2f}"
        )