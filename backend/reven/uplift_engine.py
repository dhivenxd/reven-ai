from __future__ import annotations

from dataclasses import dataclass

from backend.reven.economic_engine import (
    estimate_baseline_probability,
    calculate_economics,
)
from backend.reven.state_engine import CustomerState
from backend.schemas.streamflix import InterventionType


# ============================================================
# POLICY PARAMETERS
# ============================================================

# Core economic gates.
#
# An intervention must demonstrate BOTH:
#   1. meaningful incremental uplift
#   2. positive expected incremental net revenue
#
MINIMUM_UPLIFT = 0.05
MINIMUM_NET_VALUE = 5.0


# Minimum risk required for autonomous intervention.
MINIMUM_AUTONOMOUS_RISK_SCORE = 30.0


# Action-specific risk thresholds.
#
# These prevent broad retention actions from being triggered
# simply because an action looks profitable in isolation.
MINIMUM_RENEWAL_REMINDER_RISK_SCORE = 40.0
MINIMUM_PERSONALIZED_OFFER_RISK_SCORE = 40.0

MINIMUM_DISCOUNT_RISK_SCORE = 45.0
MINIMUM_PLAN_CHANGE_RISK_SCORE = 55.0
MINIMUM_CANCELLATION_SAVE_RISK_SCORE = 70.0


# ============================================================
# DATA MODEL
# ============================================================

@dataclass
class UpliftEstimate:
    intervention_type: InterventionType

    baseline_probability: float
    intervention_probability: float

    incremental_lift: float
    incremental_revenue: float

    intervention_cost: float
    expected_net_revenue: float


# ============================================================
# CONTEXTUAL POLICY
# ============================================================

def is_contextually_appropriate(
    state: CustomerState,
    intervention_type: InterventionType,
) -> bool:
    """
    Determine whether an intervention is justified by observable
    customer evidence.

    REVEN policy principle:

        customer evidence
              +
        sufficient risk
              +
        positive economics
              =
        autonomous intervention

    The contextual layer intentionally remains conservative.
    Economic profitability alone is NOT sufficient justification.
    """

    # --------------------------------------------------------
    # NO ACTION
    # --------------------------------------------------------

    if intervention_type == InterventionType.NO_ACTION:
        return True

    # --------------------------------------------------------
    # GLOBAL AUTONOMOUS RISK GATE
    # --------------------------------------------------------

    if (
        state.risk_score < MINIMUM_AUTONOMOUS_RISK_SCORE
        and not state.cancellation_requested
    ):
        return False

    # --------------------------------------------------------
    # PAYMENT RECOVERY
    # --------------------------------------------------------
    #
    # Payment actions are directly tied to payment failure.
    #

    if intervention_type == InterventionType.PAYMENT_RETRY:
        return state.payment_failure

    if intervention_type == InterventionType.PAYMENT_REMINDER:
        return state.payment_failure

    # --------------------------------------------------------
    # RENEWAL REMINDER
    # --------------------------------------------------------
    #
    # Only contact customers who are actually approaching
    # renewal and have meaningful risk.
    #

    if intervention_type == InterventionType.RENEWAL_REMINDER:
        return (
            state.renewal_due
            and state.risk_score
            >= MINIMUM_RENEWAL_REMINDER_RISK_SCORE
        )

    # --------------------------------------------------------
    # PERSONALIZED OFFER
    # --------------------------------------------------------
    #
    # An offer is appropriate when there is evidence of
    # disengagement/inactivity.
    #
    # We do NOT offer incentives to customers merely because
    # they have a numerical risk score.
    #

    if intervention_type == InterventionType.PERSONALIZED_OFFER:
        return (
            state.risk_score
            >= MINIMUM_PERSONALIZED_OFFER_RISK_SCORE
            and (
                state.engagement_declining
                or state.inactive
            )
        )

    # --------------------------------------------------------
    # DISCOUNT
    # --------------------------------------------------------
    #
    # Discounts have a direct economic cost, so they require
    # stronger evidence than ordinary reminders/offers.
    #
    # Explicit cancellation is a strong signal and therefore
    # qualifies immediately.
    #
    # Otherwise, discount requires meaningful risk PLUS
    # engagement/inactivity evidence.
    #

    if intervention_type == InterventionType.DISCOUNT:
        if state.cancellation_requested:
            return True

        return (
            state.risk_score
            >= MINIMUM_DISCOUNT_RISK_SCORE
            and (
                state.engagement_declining
                or state.inactive
            )
        )

    # --------------------------------------------------------
    # PLAN CHANGE
    # --------------------------------------------------------
    #
    # Plan changes are a stronger intervention and should not
    # be used as a generic retention mechanism.
    #
    # Require either:
    #   - explicit cancellation
    #   - very high risk + strong engagement evidence
    #

    if intervention_type == InterventionType.PLAN_CHANGE:
        if state.cancellation_requested:
            return True

        return (
            state.risk_score
            >= MINIMUM_PLAN_CHANGE_RISK_SCORE
            and (
                state.engagement_declining
                or state.inactive
            )
        )

    # --------------------------------------------------------
    # CANCELLATION SAVE
    # --------------------------------------------------------
    #
    # IMPORTANT:
    #
    # This is intentionally the most restrictive retention
    # action.
    #
    # Cancellation-save is NOT a generic replacement for:
    #   - discount
    #   - personalized offer
    #   - engagement recovery
    #
    # It requires:
    #
    #   explicit cancellation
    #           AND
    #   high customer risk
    #
    # This prevents cancellation-save from becoming the default
    # action for broadly distressed customers.
    #

    if intervention_type == InterventionType.CANCELLATION_SAVE:
        return (
            state.cancellation_requested
            and state.risk_score
            >= MINIMUM_CANCELLATION_SAVE_RISK_SCORE
        )

    # --------------------------------------------------------
    # UNKNOWN ACTION
    # --------------------------------------------------------

    return False


# ============================================================
# UPLIFT
# ============================================================

def estimate_uplift(
    state: CustomerState,
    intervention_type: InterventionType,
) -> float:
    """
    Return modeled incremental renewal probability.
    """

    baseline = estimate_baseline_probability(state)

    economic = calculate_economics(
        state=state,
        intervention_type=intervention_type,
    )

    return economic.success_probability - baseline


# ============================================================
# FULL ECONOMIC ESTIMATE
# ============================================================

def calculate_uplift(
    state: CustomerState,
    intervention_type: InterventionType,
) -> UpliftEstimate:
    """
    Calculate the complete economic value of an action.

    The economic engine remains the source of truth for:

        - baseline probability
        - intervention probability
        - incremental lift
        - incremental revenue
        - intervention cost
        - expected net revenue
    """

    economic = calculate_economics(
        state=state,
        intervention_type=intervention_type,
    )

    return UpliftEstimate(
        intervention_type=intervention_type,
        baseline_probability=economic.baseline_probability,
        intervention_probability=economic.success_probability,
        incremental_lift=economic.incremental_lift,
        incremental_revenue=economic.incremental_revenue,
        intervention_cost=economic.intervention_cost,
        expected_net_revenue=economic.expected_net_revenue,
    )


# ============================================================
# ECONOMIC ELIGIBILITY
# ============================================================

def is_economically_eligible(
    estimate: UpliftEstimate,
) -> bool:
    """
    An action must satisfy BOTH economic requirements:

        incremental lift >= minimum uplift

    AND

        expected incremental net revenue >= minimum net value
    """

    return (
        estimate.incremental_lift >= MINIMUM_UPLIFT
        and estimate.expected_net_revenue >= MINIMUM_NET_VALUE
    )


# ============================================================
# FINAL INTERVENTION ELIGIBILITY
# ============================================================

def is_intervention_eligible(
    state: CustomerState,
    intervention_type: InterventionType,
) -> bool:
    """
    Final deterministic policy gate.

    Autonomous intervention requires:

        CONTEXT
            AND
        ECONOMICS
    """

    if intervention_type == InterventionType.NO_ACTION:
        return False

    if not is_contextually_appropriate(
        state,
        intervention_type,
    ):
        return False

    estimate = calculate_uplift(
        state,
        intervention_type,
    )

    return is_economically_eligible(estimate)


# ============================================================
# BEST UPLIFT ACTION
# ============================================================

def choose_best_uplift_action(
    state: CustomerState,
    candidates: list[InterventionType],
) -> UpliftEstimate | None:
    """
    Select the eligible action with the highest expected
    incremental net revenue.

    Objective:

        maximize expected incremental net revenue

    The policy does NOT optimize for intervention volume.
    """

    eligible: list[UpliftEstimate] = []

    for action in candidates:

        if is_intervention_eligible(
            state,
            action,
        ):
            eligible.append(
                calculate_uplift(
                    state,
                    action,
                )
            )

    if not eligible:
        return None

    return max(
        eligible,
        key=lambda estimate: estimate.expected_net_revenue,
    )


# ============================================================
# DEBUG
# ============================================================

def print_uplift_analysis(
    state: CustomerState,
) -> None:

    print("REVEN UPLIFT ENGINE")
    print("=" * 60)
    print()

    print(f"Customer: {state.customer_id}")
    print(f"Risk state: {state.risk_state.value}")
    print(f"Risk score: {state.risk_score:.1f}/100")
    print(f"Payment failure: {state.payment_failure}")
    print(f"Cancellation: {state.cancellation_requested}")
    print(f"Engagement decline: {state.engagement_declining}")
    print(f"Inactive: {state.inactive}")
    print(f"Renewal due: {state.renewal_due}")

    baseline = estimate_baseline_probability(state)

    print()
    print(f"Baseline probability: {baseline:.2%}")

    print()
    print("Policy parameters:")
    print(
        f"  minimum uplift: "
        f"{MINIMUM_UPLIFT:.2%}"
    )
    print(
        f"  minimum net value: "
        f"₹{MINIMUM_NET_VALUE:.2f}"
    )
    print(
        f"  minimum autonomous risk: "
        f"{MINIMUM_AUTONOMOUS_RISK_SCORE:.1f}"
    )
    print(
        f"  renewal reminder risk: "
        f"{MINIMUM_RENEWAL_REMINDER_RISK_SCORE:.1f}"
    )
    print(
        f"  personalized offer risk: "
        f"{MINIMUM_PERSONALIZED_OFFER_RISK_SCORE:.1f}"
    )
    print(
        f"  discount risk: "
        f"{MINIMUM_DISCOUNT_RISK_SCORE:.1f}"
    )
    print(
        f"  plan change risk: "
        f"{MINIMUM_PLAN_CHANGE_RISK_SCORE:.1f}"
    )
    print(
        f"  cancellation save risk: "
        f"{MINIMUM_CANCELLATION_SAVE_RISK_SCORE:.1f}"
    )

    print()
    print("Intervention analysis:")
    print()

    for action in InterventionType:

        estimate = calculate_uplift(
            state,
            action,
        )

        contextual = is_contextually_appropriate(
            state,
            action,
        )

        economic = is_economically_eligible(
            estimate,
        )

        final = is_intervention_eligible(
            state,
            action,
        )

        print(action.value)

        print(
            f"  baseline probability: "
            f"{estimate.baseline_probability:.2%}"
        )

        print(
            f"  intervention probability: "
            f"{estimate.intervention_probability:.2%}"
        )

        print(
            f"  incremental lift: "
            f"{estimate.incremental_lift:.2%}"
        )

        print(
            f"  incremental revenue: "
            f"₹{estimate.incremental_revenue:.2f}"
        )

        print(
            f"  intervention cost: "
            f"₹{estimate.intervention_cost:.2f}"
        )

        print(
            f"  expected net revenue: "
            f"₹{estimate.expected_net_revenue:.2f}"
        )

        print(
            f"  contextually appropriate: "
            f"{contextual}"
        )

        print(
            f"  economically eligible: "
            f"{economic}"
        )

        print(
            f"  FINAL eligible: "
            f"{final}"
        )

        print()


# ============================================================
# DEMO
# ============================================================

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

    customer = customers[0]

    subscription = next(
        subscription
        for subscription in subscriptions
        if subscription.customer_id == customer.customer_id
    )

    customer_events = [
        event
        for event in events
        if event.customer_id == customer.customer_id
    ]

    state = build_customer_state(
        customer=customer,
        subscription=subscription,
        risk_events=customer_events,
    )

    print_uplift_analysis(state)