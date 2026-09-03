# REVEN Demo Guide

## Prerequisites

1. **Install dependencies:**
   ```bash
   pip install -r backend/llm/requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials:
   #   - RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET / RAZORPAY_WEBHOOK_SECRET
   #   - GEMINI_API_KEY
   ```

3. **Configure Razorpay webhooks** (for live webhook testing):
   - Log into [Razorpay Dashboard](https://dashboard.razorpay.com)
   - Go to Settings → Webhooks
   - Add webhook URL: `https://your-public-url/webhooks/razorpay`
   - For local testing, use [ngrok](https://ngrok.com) or [localtunnel](https://localtunnel.me)

---

## Demo Sequence

### Step 1 — Start the Backend Servers

**Terminal 1: Webhook Server (port 8000)**
```bash
python -m backend.integrations.razorpay.webhook_server
```
Razorpay webhooks → REVEN decisions → Payment Links.

**Terminal 2: LLM Agent API (port 8080)**
```bash
python -m backend.llm.api.server
```
Natural language queries to REVEN.

### Step 2 — Seed Demo Decisions

```bash
curl -X POST http://localhost:8080/agent/demo/seed
```

Or via Python:
```bash
python -c "
import requests, json
r = requests.post('http://localhost:8080/agent/demo/seed', json={'count': 10})
print(json.dumps(r.json(), indent=2))
"
```

Expected response:
```json
{
  "seeded": 10,
  "store_size": 10
}
```

### Step 3 — Chat with REVEN

```bash
python backend/llm/demo.py --mode chat
```

This launches an interactive console chat. The agent will use the seeded decisions.

**Without API keys**, use test mode:
```bash
python backend/llm/demo.py --mode test
```

### Step 4 — Simulate a Payment Failure

Trigger the webhook server by sending a mock `payment.failed` event:

```bash
python backend/integrations/razorpay/demo.py
```

This sends a test payload to your local webhook server (requires `ngrok` for the URL to be reachable from Razorpay).

---

## Key Questions to Ask REVEN

### 1. "What decisions has REVEN made?"
```
→ Shows total decisions, breakdown by intervention type,
   revenue preserved, intervention rate
```

### 2. "What happened with customer cust_001?"
```
→ Shows the customer's latest decision, execution status,
   and payment link URL (if executed)
```

### 3. "Should we retry the payment for cust_001?"
```
→ REVEN explains what it decided and why.
   It does NOT recommend — it reports what was already decided.
```

### 4. "Execute the approved decision for cust_001"
```
→ Executes the decision via decision_id.
   Shows the Payment Link URL.
   Note: Link created ≠ revenue recovered.
```

### 5. "What's the difference between payment_retry and no_action?"
```
→ Explains the economic rationale for the customer's situation.
```

### 6. "Show me the full decision for cust_001"
```
→ Shows intervention type, confidence score,
   expected net revenue, rationale, and all alternatives considered
```

---

## Expected Behavior

### Payment Failed Flow

1. Razorpay sends `payment.failed` webhook
2. Webhook server validates signature
3. Event mapped to Customer + Subscription + RiskEvent
4. REVEN engine evaluates economics → decision made
5. Execution gateway creates Payment Link (PAYMENT_RETRY only)
6. Audit logged to `data/razorpay_audit.jsonl`

**You see:**
- `intervention_type: "payment_retry"` or `"no_action"`
- `execution_status: "executed"` with a `razorpay_resource_url`
- `revenue_recovered: false` (until `payment.captured` fires)

### Payment Captured Flow (Current Gap)

1. Customer completes payment via Payment Link
2. Razorpay sends `payment.captured` webhook
3. Webhook server logs to audit

**Current behavior:** Decision store is NOT updated. Revenue recovered shows 0.0 in summaries.

### No-Action Decision

1. REVEN evaluates economics
2. Minimum uplift (5%) or minimum net value (₹5) not met
3. Decision: `intervention_type: "no_action"`
4. Execution gateway blocks execution

**You see:**
- `intervention_type: "no_action"`
- `execution_status: "blocked"` with reason: "NO_ACTION cannot be executed"

---

## Testing Without External Services

### Test LLM Agent (No API Key)
```bash
python backend/llm/demo.py --mode test
```

### Test LLM Agent (With Gemini API Key)
```bash
python backend/llm/demo.py --mode live
```

### Test Webhook Server
```bash
python backend/integrations/razorpay/test_webhook_server.py
```

### Test Razorpay Integration
```bash
python backend/integrations/razorpay/test_integration.py
```

### Run All Tests
```bash
python -m pytest backend/llm/tests/ -v
```

---

## Frontend Placeholder

The `frontend/` directory is empty (`.gitkeep`). No frontend has been built yet.

To build the operator console, see the frontend implementation plan in `docs/REVEN_HANDOFF.md` (Part 11).

Recommended first step: Build the **Executive Dashboard** with:
- 4 KPI cards: Revenue Preserved, Decisions Made, Intervention Rate, ROI
- Recent decisions table
- Chat interface
