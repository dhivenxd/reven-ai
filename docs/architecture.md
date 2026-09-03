# REVEN Architecture

REVEN is an AI-powered revenue recovery system with a layered safety model. The architecture separates concerns: AI recommends, the policy engine authorizes, and the execution gateway acts.

## Safety Boundary

```
LLM Agent (Gemini)              → explains and answers questions
Deterministic Policy Engine      → sole authority for intervention selection
Execution Gateway (frozen)      → only path to external systems (Razorpay)
```

**The LLM has no financial authority.** It cannot create, modify, or choose interventions. It can only execute pre-approved decisions via `decision_id`.

## Component Architecture

```
Razorpay webhook
    │
    ▼
┌─────────────────────┐
│  Webhook Server     │  FastAPI (port 8000)
│  (signature check)   │  HMAC-SHA256 validation
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Event Mapper        │  Converts Razorpay payload → REVEN schemas
│  (no engagement     │  Does NOT fabricate engagement data
│   fabrication)       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  REVEN Engine        │  Full pipeline
│  (stateless)         │
│  ┌─────────────────┐ │
│  │ State Engine     │ │ Observes customer risk signals
│  ├─────────────────┤ │
│  │ Decision Engine  │ │ Evaluates intervention economics
│  ├─────────────────┤ │
│  │ Uplift/Policy    │ │ Applies deterministic eligibility gates
│  │ Engine           │ │
│  ├─────────────────┤ │
│  │ Intervention     │ │ Builds executable plan
│  │ Engine           │ │
│  └─────────────────┘ │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Execution Gateway   │  FROZEN boundary
│  (no direct LLM     │  Decision → Payment Link
│   access)            │  BLOCKED: NO_ACTION
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Audit Logger        │  JSONL append-only trail
└─────────────────────┘
```

## Event Flow

### 1. Webhook Reception
```
Razorpay → POST /webhooks/razorpay
  → Read raw body + X-Razorpay-Signature header
  → verify_webhook_signature() via HMAC-SHA256
  → Idempotency check (in-memory event ID set)
```

### 2. Event Mapping
```
Razorpay payload → map_razorpay_to_reven()
  → Extract customer_id, subscription_id, amount, error_reason
  → Map error_reason → PaymentFailureReason enum
  → Convert paise → rupees
  → Build Customer, Subscription, RiskEvent objects
```

### 3. REVEN Decision Pipeline
```
run_reven(customer, subscription, risk_events)
  │
  ├── state_engine.build_customer_state()
  │     Rule-based risk scoring from observable signals
  │     Output: CustomerState (risk_state, risk_score, reasons)
  │
  ├── decision_engine.make_decision(state)
  │     get_candidate_interventions() → list of InterventionType
  │     For each: economic_engine.calculate_economics() → InterventionEconomics
  │     Filter: uplift_engine gates (contextual + economic)
  │     Rank by expected_net_revenue
  │     Output: RevenueDecision
  │
  ├── intervention_engine.build_intervention(decision)
  │     Build InterventionPlan with cost, fallback
  │     Output: InterventionPlan
  │
  └── outcome_engine.simulate_outcome() [synthetic, seeded]
        Stochastic outcome for benchmark
        Output: Outcome
```

### 4. Execution
```
ExecutionGateway.execute_decision(decision, subscription)
  │
  ├── Gate: NO_ACTION? → BLOCKED
  ├── Gate: PAYMENT_RETRY?
  │     razorpay_client.create_payment_link() → Payment Link URL
  │     Reference ID = decision_id
  └── Return ExecutionResult
```

## Decision Flow

```
Customer Risk Signals
    │
    ▼
┌──────────────────────────────────────────┐
│  Gate 1: Contextual Appropriateness      │
│  Is this intervention appropriate for      │
│  this customer's risk state?              │
│  (Risk score thresholds per type)         │
└──────────┬───────────────────────────────┘
           │  YES
           ▼
┌──────────────────────────────────────────┐
│  Gate 2: Economic Eligibility              │
│  Is the expected incremental net revenue  │
│  ≥ minimum threshold?                    │
│  (MINIMUM_UPLIFT=5%, MINIMUM_NET=₹5)    │
└──────────┬───────────────────────────────┘
           │  YES
           ▼
┌──────────────────────────────────────────┐
│  Rank by Expected Net Revenue             │
│  Choose the intervention with the highest │
│  expected incremental value               │
└──────────────────────────────────────────┘
```

## LLM Safety Architecture

The LLM agent runs in a tool-calling loop with strict constraints:

```
User message
    │
    ▼
┌──────────────────────────┐
│  RevenAgent.chat()       │  Max 5 iterations
│  (async tool loop)       │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  LLM (Gemini)            │  System instruction: no financial
│  with tools              │  authority, report actual data only
└──────────┬───────────────┘
           │
    ┌──────┴──────┐
    │              │
    ▼              ▼
Text response  Tool calls
                 │
                 ├─ get_customer_recovery_status
                 ├─ get_reven_decision
                 ├─ get_recovery_outcome
                 ├─ get_recovery_summary
                 └─ execute_approved_decision ← ONLY accepts decision_id
```

**Key security property**: The `execute_approved_decision` tool only accepts `decision_id`. The LLM cannot specify intervention type, amount, or any other parameter. The server validates all parameters independently.

## Recovery Confirmation Flow

```
Payment Link created
    │
    ▼
Customer receives link
    │
    ▼
Customer completes payment
    │
    ▼
Razorpay sends payment.captured webhook
    │
    ▼
Webhook server logs to audit
    │
    ▼
[Gap] Decision store NOT updated (future work)
```

> ⚠️ Currently `payment.captured` only logs to audit. The decision store is NOT updated, so `revenue_recovered` in summaries is always 0.0. This is a known gap.

## Data Flow Summary

| Stage | Transformation |
|---|---|
| Razorpay → REVEN | Paise ÷ 100 → rupees |
| Razorpay → REVEN | error_reason string → PaymentFailureReason enum |
| Decision → Execution | `RevenueDecision` → `Intervention` (adds cost) |
| Execution → Audit | Object → dict → JSONL line |
| Store → API | `StoredDecision` → `RevenueDecision` |
