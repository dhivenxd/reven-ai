# REVEN API Documentation

## Running the Servers

```bash
# Webhook server — receives Razorpay webhooks (port 8000)
python -m backend.integrations.razorpay.webhook_server

# LLM agent API — natural language queries (port 8080)
python -m backend.llm.api.server
```

## Webhook Server — Port 8000

### `GET /health`

Health check. No authentication.

**Response 200:**
```json
{"status": "ok"}
```

---

### `POST /webhooks/razorpay`

Receive Razorpay webhook events. Signature-validated via `X-Razorpay-Signature` header.

**Headers:**
- `X-Razorpay-Signature`: HMAC-SHA256 of raw request body
- `X-Razorpay-Event-Id`: Used for idempotency

**Request body** — standard Razorpay webhook payload:

```json
{
  "event": "payment.failed",
  "payload": {
    "payment": {
      "entity": {
        "id": "pay_ABC123",
        "amount": 39900,
        "currency": "INR",
        "error_code": "BAD_REQUEST_ERROR",
        "error_description": "Invalid card number",
        "customer_id": "cust_123",
        "subscription_id": "sub_456"
      }
    },
    "subscription": {
      "entity": {
        "id": "sub_456",
        "customer_id": "cust_123",
        "plan_id": "plan_BASIC",
        "status": "active",
        "current_start": 1704067200,
        "current_end": 1735689600
      }
    }
  },
  "created_at": 1704067200
}
```

**Response 200 (processed):**
```json
{
  "status": "processed",
  "decision": {
    "decision_id": "dec_abc123",
    "customer_id": "cust_123",
    "intervention_type": "payment_retry",
    "expected_net_revenue": 247.50,
    "confidence": 0.85,
    "reason": "High risk: payment failure on active subscription..."
  },
  "execution": {
    "execution_status": "executed",
    "razorpay_operation": "payment_link_created",
    "razorpay_resource_id": "pl_ABC123",
    "razorpay_resource_url": "https://rzp.io/i/ABC123",
    "message": "Payment recovery link created"
  }
}
```

**Response 200 (duplicate):**
```json
{"status": "duplicate"}
```

**Response 400 (bad signature):**
```json
{"error": "invalid_signature"}
```

**Response 422 (unsupported event):**
```json
{"error": "unsupported_event"}
```

---

## LLM Agent API — Port 8080

### `GET /health`

Health check.

**Response 200:**
```json
{"status": "ok"}
```

---

### `GET /agent/status`

Agent metrics and system health.

**Response 200:**
```json
{
  "status": "ready",
  "total_sessions": 5,
  "total_requests": 23,
  "llm_configured": true,
  "razorpay_configured": true,
  "store_size": 8
}
```

---

### `POST /agent/chat`

Send a message to the REVEN agent.

**Request:**
```json
{
  "message": "What happened with customer cust_123?"
}
```

**Response 200:**
```json
{
  "response": "Customer cust_123 had a payment failure on September 1st. REVEN decided to create a payment recovery link. The link was created on September 1st at 14:30 UTC. Revenue has NOT yet been recovered — we're waiting for the customer to complete the payment.",
  "session_id": "sess_abc123"
}
```

**Response 503 (LLM not configured):**
```json
{"error": "LLM agent not configured. Set GEMINI_API_KEY."}
```

---

### `GET /agent/decisions/{customer_id}`

Direct decision lookup without going through the LLM.

**Response 200:**
```json
{
  "customer_id": "cust_123",
  "decisions": [
    {
      "decision_id": "dec_abc123",
      "intervention_type": "payment_retry",
      "expected_net_revenue": 247.50,
      "confidence": 0.85,
      "reason": "High risk: payment failure on active subscription...",
      "execution_status": "executed",
      "razorpay_resource_url": "https://rzp.io/i/ABC123",
      "created_at": "2024-09-01T14:30:00Z",
      "alternatives": [
        {
          "intervention_type": "no_action",
          "expected_net_revenue": 0.0,
          "success_probability": 0.35,
          "incremental_lift": 0.0
        },
        {
          "intervention_type": "personalized_offer",
          "expected_net_revenue": 180.20,
          "success_probability": 0.52,
          "incremental_lift": 0.17
        }
      ]
    }
  ]
}
```

**Response 200 (no decisions):**
```json
{
  "customer_id": "cust_999",
  "decisions": []
}
```

---

### `POST /agent/demo/seed`

Seed the decision store with demo decisions for testing.

**Request:**
```json
{
  "count": 10
}
```

**Response 200:**
```json
{
  "seeded": 10,
  "store_size": 10
}
```

---

## Port Summary

| Server | Port | Purpose |
|---|---|---|
| Webhook Server | 8000 | Receives Razorpay webhooks |
| LLM Agent API | 8080 | Natural language queries to REVEN |

## Webhook Testing

To test the webhook server locally, use curl with a mock payload:

```bash
# Generate a mock signature (for testing only — in production, use Razorpay dashboard)
curl -X POST http://localhost:8000/webhooks/razorpay \
  -H "Content-Type: application/json" \
  -H "X-Razorpay-Signature: <hmac>" \
  -H "X-Razorpay-Event-Id: evt_test_001" \
  -d @test_payload.json
```
