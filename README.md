# REVEN

**AI Revenue Recovery Agent**

REVEN doesn't just retry failed payments.
It decides whether recovering the customer is economically worth pursuing — and knows when NOT to intervene.

---

## The Problem

Involuntary churn silently erodes subscription revenue. Failed payments and expired cards drain revenue that was already earned — without the business even knowing it's happening.

Aggressive recovery attempts (automatic retries, aggressive dunning) can damage customer relationships and increase churn. Doing nothing loses revenue.

**REVEN's answer**: Model the full economic consequence of each intervention — not just today's recovered cash, but tomorrow's net revenue — and only act when the expected incremental value justifies the cost.

---

## How REVEN Is Different

| | Traditional Retry | REVEN |
|---|---|---|
| **Decisions made by** | Rule / ML model | Deterministic policy engine |
| **Metric optimized** | Same-day recovery rate | Expected incremental net revenue |
| **Action selection** | Often one-size-fits-all | Risk-calibrated, per-customer |
| **Safety model** | AI-only or rules-only | AI explains → Policy authorizes → Gateway executes |
| **Knows when NOT to act** | Rarely | By design |
| **Captures full economics** | Rarely | Always |

---

## Core Architecture

```
Razorpay payment.failed webhook
  → Webhook Server (signature validated)
  → Event Mapper (Razorpay payload → REVEN schemas)
  → REVEN Engine:
      State Engine        → observe customer risk signals
      Decision Engine     → evaluate all intervention economics
      Uplift/Policy Engine → deterministic eligibility gates
      Intervention Engine  → build executable plan
  → Execution Gateway     → frozen: decision → Payment Link
  → Audit Logger          → JSONL trail
  → LLM Agent             → query results via natural language
```

**The safety boundary**: AI recommends and explains. The deterministic Policy Engine authorizes. The frozen Execution Gateway acts. No single component can act alone.

---

## Decision Flow

1. **State Engine** — observes customer risk signals from events (payment failures, cancellation requests, engagement decline)
2. **Decision Engine** — for each candidate intervention, computes expected incremental net revenue
3. **Policy Engine** — applies hard gates: contextual appropriateness (risk score thresholds) + economic eligibility (minimum uplift ≥5%, minimum net value ≥₹5)
4. **Intervention Engine** — builds an executable plan from the authorized decision
5. **Execution Gateway** — frozen boundary; creates a Razorpay Payment Link for `PAYMENT_RETRY` interventions

---

## AI + Deterministic Policy Architecture

REVEN uses a layered safety model:

```
LLM Agent (Gemini)          → explains decisions, answers questions
Deterministic Policy Engine  → sole authority for intervention selection
Execution Gateway           → frozen boundary, Razorpay only
```

- The **LLM agent** reads pre-made decisions from the store and explains them in natural language
- The **Policy Engine** is rule-based and deterministic — same inputs always produce the same decision
- The **Execution Gateway** is a frozen security boundary — it only accepts `RevenueDecision` objects from the policy engine
- The LLM **cannot** create, modify, or choose interventions — it can only execute pre-approved decisions via `decision_id`

---

## Razorpay Integration

- **Mode**: Sandbox (production not yet implemented)
- **Webhook**: `POST /webhooks/razorpay` — receives `payment.failed` and `payment.captured`
- **Signature validation**: HMAC-SHA256 on every webhook
- **Execution**: Creates a Razorpay Payment Link for recovery-eligible customers
- **Critical truth**: Payment Link created ≠ Revenue recovered. Only `payment.captured` webhook confirms actual recovery.
- **Idempotency**: In-memory deduplication of webhook event IDs

---

## Gemini Agent

The LLM layer provides a natural-language interface to REVEN's decision store:

- **5 safe tools**: `get_customer_recovery_status`, `get_reven_decision`, `get_recovery_outcome`, `get_recovery_summary`, `execute_approved_decision`
- **Strict execution boundary**: `execute_approved_decision` only accepts `decision_id` — the LLM cannot invent or specify intervention types
- **Currency enforcement**: All monetary values are in INR (₹), never USD
- **Payment link truth**: PAYMENT_RETRY creates a link; the customer must complete payment — it is NOT an automatic retry
- **Revenue recovery truth**: Payment link creation is not revenue recovered; only `payment.captured` confirms recovery

---

## Benchmark Results

> ⚠️ **Synthetic data** — benchmark uses 10,000 synthetic customers generated from `customer_generator.py`, not real customer data. Results are deterministic (seed=42) and calibratable.

**Methodology**:
- 10,000 synthetic customers, seed=42
- 30-day observation window
- For each customer: run do-nothing baseline + run REVEN policy
- Incremental net revenue = REVEN net revenue − baseline net revenue
- ROI = incremental net revenue / intervention cost

**Key metrics**:
- REVEN's policy engine applies minimum uplift (5%) and minimum net value (₹5) gates
- Intervention rate is calibrated — REVEN deliberately chooses NO_ACTION for most customers
- ROI is positive because REVEN only intervenes when economics justify it

**What this means**: REVEN is designed to have a high ROI, not a high intervention rate. It is a policy engine that only acts when profitable to do so.

---

## Demo Flow

```bash
# Terminal 1: Start webhook server (Razorpay webhooks → port 8000)
python -m backend.integrations.razorpay.webhook_server

# Terminal 2: Start LLM agent API (port 8080)
python -m backend.llm.api.server

# Terminal 3: Seed demo decisions
curl -X POST http://localhost:8080/agent/demo/seed

# Terminal 4: Chat with REVEN
python backend/llm/demo.py --mode chat
```

Or test without API keys:
```bash
python backend/llm/demo.py --mode test
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.11+ |
| **Webhook server** | FastAPI (port 8000) |
| **LLM API server** | FastAPI (port 8080) |
| **LLM provider** | Google Gemini (`gemini-3-flash-preview`) |
| **LLM SDK** | `google-genai` |
| **Validation** | `pydantic` |
| **Razorpay client** | stdlib `urllib` only |
| **Testing** | `pytest` |
| **Decision store** | In-memory (ephemeral) |
| **Audit log** | JSONL file |

---

## Project Structure

```
backend/
├── reven/                     # Core decision engine
│   ├── state_engine.py        # Build customer risk state from events
│   ├── decision_engine.py      # Rank interventions by expected net revenue
│   ├── economic_engine.py     # Probability and economic math
│   ├── uplift_engine.py       # Policy gates (MINIMUM_UPLIFT, risk score thresholds)
│   ├── intervention_engine.py # Build executable intervention plan
│   ├── baseline_engine.py     # Simulate do-nothing baseline
│   ├── reven_engine.py        # Full pipeline: state → decision → intervention
│   ├── benchmark.py           # Fair comparison: REVEN vs baseline
│   └── calibration_profiles.py # Synthetic calibration data
│
├── integrations/
│   └── razorpay/              # Razorpay integration (frozen)
│       ├── webhook_server.py   # FastAPI: POST /webhooks/razorpay, GET /health
│       ├── webhook_handler.py # HMAC-SHA256 signature validation
│       ├── event_mapper.py   # Razorpay payload → REVEN schemas
│       ├── execution_gateway.py # Frozen boundary: decision → Payment Link
│       ├── razorpay_client.py # Payment Link creation (stdlib urllib)
│       └── audit.py           # JSONL audit logger
│
├── llm/                       # LLM agent layer
│   ├── agent/
│   │   ├── core.py            # RevenAgent: async tool-calling loop
│   │   └── prompts.py         # System instruction (Gemini-compatible)
│   ├── tools/
│   │   ├── status_tool.py     # get_customer_recovery_status
│   │   ├── decision_tool.py   # get_reven_decision
│   │   ├── outcome_tool.py    # get_recovery_outcome
│   │   ├── summary_tool.py    # get_recovery_summary
│   │   └── execute_tool.py    # execute_approved_decision (decision_id only)
│   ├── store/
│   │   └── decision_store.py  # In-memory decision store
│   ├── client/
│   │   └── gemini_client.py   # GeminiLLMClient (google-genai SDK)
│   ├── api/
│   │   └── server.py          # FastAPI: /agent/chat, /health, /agent/status
│   └── tests/
│       └── test_agent.py      # 23 tests covering tools, security, data truth
│
├── simulator/                 # Synthetic test fixtures
│   ├── customer_generator.py   # generate_population(count, seed)
│   ├── event_engine.py        # generate_events() — 5 risk event types
│   └── outcome_engine.py      # simulate_outcome() — seeded stochastic
│
└── schemas/
    └── streamflix.py          # All domain types (Customer, Subscription, etc.)

data/
└── razorpay_audit.jsonl      # Audit log (gitignored, runtime artifact)

docs/
├── REVEN_HANDOFF.md           # Internal technical handoff (secrets redacted)
├── architecture.md            # Architecture overview
├── product.md                # Product overview
└── experiment.md             # Experimentation methodology
```

---

## Setup / Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd reven-ai

# 2. Install Python dependencies
pip install -r backend/llm/requirements.txt

# 3. Copy environment template
cp .env.example .env

# 4. Configure credentials in .env
#    - RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET / RAZORPAY_WEBHOOK_SECRET
#    - GEMINI_API_KEY
```

---

## Running the Backend

```bash
# Webhook server (port 8000) — receives Razorpay webhooks
python -m backend.integrations.razorpay.webhook_server

# LLM agent API (port 8080) — natural language queries
python -m backend.llm.api.server

# Demo (no API key required)
python backend/llm/demo.py --mode test

# Interactive chat (requires GEMINI_API_KEY)
python backend/llm/demo.py --mode live
```

---

## API Endpoints

### Webhook Server (port 8000)

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/webhooks/razorpay` | Receive Razorpay webhooks |

### LLM Agent API (port 8080)

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/agent/status` | Agent metrics (sessions, total requests, store size) |
| POST | `/agent/chat` | Send message to REVEN agent |
| GET | `/agent/decisions/{customer_id}` | Direct decision lookup |
| POST | `/agent/demo/seed` | Seed demo decisions |

---

## Limitations

- **Synthetic benchmark data** — calibration profiles and customer generators are synthetic, not derived from real KKBOX data
- **In-memory decision store** — state resets on process restart; no persistence layer
- **payment.captured incomplete** — webhook handler logs captures but does not update decision store
- **No database** — all state is in-memory; decisions are lost on restart
- **Sandbox only** — Razorpay production mode not implemented
- **No frontend** — operator console not yet built
- **No multi-tenant support**
- **No real customer data enrichment** — only Razorpay webhook data

---

## Future Work

- [ ] Wire `payment.captured` webhook to update decision store
- [ ] Add persistence layer (SQLite/PostgreSQL) for decision store
- [ ] Real calibration from KKBOX churn dataset
- [ ] Frontend operator console (React + Vite)
- [ ] Razorpay production mode
- [ ] Token tracking / LLM cost monitoring
- [ ] WebSocket/SSE for real-time webhook events
- [ ] Multi-tenant support

---

## License

MIT
