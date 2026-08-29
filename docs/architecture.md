# Architecture

REVEN is an agent that recommends revenue-retention interventions. A deterministic Policy Engine is the only component that may authorize action.

## Safety boundary

```
AI Agent (recommend)  →  Policy Engine (authorize)  →  Actuators (execute)
```

The model never writes directly to billing, payments, or customer-facing systems. Every action is gated by policy.

## Core loop

| Stage | Responsibility |
| --- | --- |
| Detect | Identify accounts where revenue is at risk (failed payment, usage drop, churn signals). |
| Diagnose | Infer *why* revenue is at risk (instrument, timing, product fit, hardship, intent). |
| Predict | Estimate outcomes for each candidate action, including expected future net revenue. |
| Decide | Rank actions by Expected Net Revenue Preserved, not today's recovered cash. |
| Authorize | Policy Engine applies hard rules (eligibility, spend caps, legal, brand, experiment assignment). |
| Act | Execute the authorized action through billing, payments, CRM, or support systems. |
| Measure | Record realized outcomes against predictions. |
| Learn | Update models and playbooks from measured results. |

## Primary metric

**Expected Net Revenue Preserved** — expected future net revenue kept versus a do-nothing baseline, after costs of incentives, write-downs, and support.

## Action space

Retry · Update Payment · Billing Change · Payment Plan · Downgrade · Pause · Incentive · Escalate · Do Nothing

## Intended layout

- `backend/` — agent, policy engine, and integrations
- `frontend/` — operator console for review, overrides, and measurement
- `data/` — schemas, fixtures, and evaluation datasets
- `tests/` — policy, decision, and integration tests
