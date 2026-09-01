# REVEN Backend Hardening — Sep 1, 2026

This backend revision aligns the MVP implementation with the current REVEN PRD.

## Major fixes

1. **Action-specific economics**
   - Discounts preserve 90% of list price under the explicit synthetic simulator assumption.
   - Plan changes preserve 65% of list price under the explicit synthetic simulator assumption.
   - Incremental revenue is calculated from expected action revenue minus expected baseline revenue.
   - This prevents plan-change/discount actions from being valued as if they preserve full price.

2. **Independent counterfactual outcome simulation**
   - REVEN decision probabilities are no longer injected into benchmark outcomes.
   - The simulator has its own synthetic response model.
   - This avoids circular evaluation and reduces the risk of baking an advantage into REVEN's benchmark.
   - The simulator remains explicitly synthetic; these probabilities are not observed causal effects.

3. **Contextual + economic eligibility**
   - Actions must have evidence in the customer state.
   - Autonomous interventions require a minimum material risk score of 30 unless cancellation was explicitly requested.
   - `no_action` remains valid.

4. **Benchmark consistency**
   - Legacy and current policies use the same independent simulator and paired per-customer seeds.
   - Action economics and realized revenue now use the same action-specific revenue assumptions.

5. **Diagnostic tooling restored**
   - Added `diagnose_uplift.py` to the backend package.
   - It reports eligibility, decision distribution, risk-state intervention coverage, and uplift distributions.

## Important interpretation

The response simulator is a controlled synthetic environment, not observed customer-level causal evidence. Benchmark results should therefore be described as modeled/simulated evaluation results, consistent with the PRD.
