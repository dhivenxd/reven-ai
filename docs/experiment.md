# Experiments

REVEN treats every authorized intervention as a measurable bet against a do-nothing baseline.

## North-star metric

**Expected Net Revenue Preserved** — not same-day payment recovery.

An action that recovers a payment today but increases churn, support cost, or discount leakage can lose on this metric. An action that pauses or downgrades a customer can win if it preserves more lifetime net revenue.

## Guardrails

- Hold out a **Do Nothing** (or current-playbook) control whenever traffic allows.
- Policy Engine assignment is the source of truth for treatment vs. control.
- Do not optimize solely for recovery rate, retry success, or incentive take-rate.
- Track cost of action: incentives, dunning fees, support time, goodwill credits.

## Suggested first experiments

1. **Retry vs. Update Payment** for involuntary churn (failed card, expired method).
2. **Payment Plan / Pause vs. aggressive retry** for hardship or cash-flow signals.
3. **Incentive vs. Downgrade** when price sensitivity is the diagnosed cause.
4. **Escalate vs. Autopilot** for high-ARR accounts where policy forbids fully automatic action.

## Learning loop

Detect → Diagnose → Predict → Decide → Authorize → Act → Measure → Learn

Predictions are logged *before* act. Measurement compares predicted vs. realized net revenue preserved and feeds the next model/policy iteration.
