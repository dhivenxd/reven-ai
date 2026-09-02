# REVEN LLM Agent Layer

AI orchestration layer for the REVEN revenue recovery system.

## Architecture

```
Frontend
    ↓
LLM Agent (this layer)
    ↓
Tool Layer (5 safe tools)
    ↓
REVEN Policy Engine (frozen)
    ↓
Razorpay Execution Gateway (frozen)
    ↓
Razorpay Sandbox
```

## Safety Model

The LLM agent is constrained to prevent financial authority:

- **LLM CANNOT**: Choose interventions, modify decisions, call Razorpay directly, fabricate data
- **LLM CAN**: Query recovery status, explain REVEN decisions, summarize metrics, execute approved decisions (via decision_id only)

## Components

### Agent (`backend/llm/agent/`)
- `core.py`: Agent orchestrator with tool-calling loop
- `prompts.py`: System instructions for Claude

### Tools (`backend/llm/tools/`)
1. **get_customer_recovery_status**: Query recovery status for a customer
2. **get_reven_decision**: Retrieve specific REVEN decision by ID
3. **get_recovery_outcome**: Check execution outcome and payment status
4. **get_recovery_summary**: Aggregate recovery metrics
5. **execute_approved_decision**: Execute approved decision (decision_id only)

### Store (`backend/llm/store/`)
- `decision_store.py`: In-memory decision storage (buildathon-ready)

### Client (`backend/llm/client/`)
- `base.py`: Abstract LLM provider interface
- `anthropic_client.py`: Claude implementation

### API (`backend/llm/api/`)
- `server.py`: FastAPI server with `/agent/chat` endpoint

## Setup

### Environment Variables

```bash
# Required for live LLM
ANTHROPIC_API_KEY=your-api-key

# Optional configuration
REVEN_LLM_MODEL=claude-3-5-sonnet-20241022
REVEN_LLM_PORT=8080
```

### Install Dependencies

```bash
pip install -r backend/llm/requirements.txt
```

## Running

### API Server

```bash
# Start server
python -m backend.llm.api.server

# Or with uvicorn
uvicorn backend.llm.api.server:app --reload --port 8080
```

### Demo

```bash
# Test mode (no API key needed)
python backend/llm/demo.py --mode test

# Live mode (requires ANTHROPIC_API_KEY)
python backend/llm/demo.py --mode live

# Interactive chat
python backend/llm/demo.py --mode chat
```

## API Endpoints

### POST /agent/chat
Send a message to the REVEN agent.

**Request:**
```json
{
  "message": "What recovery action for customer cust_123?",
  "session_id": "optional-session-id"
}
```

**Response:**
```json
{
  "message": "REVEN approved a PAYMENT_RETRY...",
  "session_id": "abc123",
  "status": "success",
  "timestamp": "2026-09-02T18:00:00"
}
```

### GET /health
Health check endpoint.

### GET /agent/status
Agent status and metrics.

### GET /agent/decisions/{customer_id}
Direct query for customer decisions.

### POST /agent/demo/seed
Seed demo data for testing.

## Testing

All tests are deterministic and do NOT require ANTHROPIC_API_KEY.

```bash
# Run all tests
python -m pytest backend/llm/tests/ -v

# Run with coverage
python -m pytest backend/llm/tests/ -v --cov=backend.llm
```

## Security Boundaries

### Execution Tool Contract

The `execute_approved_decision` tool:

- Accepts ONLY `decision_id` (no intervention_type, amount, or Razorpay params)
- Server loads decision from trusted store
- Server validates decision exists and is approved
- Server rejects NO_ACTION
- Server prevents duplicate execution
- Server calls ExecutionGateway (frozen)
- Returns actual ExecutionResult

### Tool Input Validation

```python
# GOOD: Server controls all parameters
execute_approved_decision(decision_id="dec_abc123")

# BAD: LLM cannot specify these
execute_approved_decision(
    intervention_type="payment_retry",  # ❌ NOT ALLOWED
    amount=399.0,                       # ❌ NOT ALLOWED
    razorpay_params={...}               # ❌ NOT ALLOWED
)
```

## Data Truth

The agent distinguishes between:

1. **Decision**: REVEN approved an intervention
2. **Execution**: Gateway attempted the action
3. **Payment Link Created**: Razorpay returned a link URL
4. **Payment Captured**: Webhook confirmed payment
5. **Revenue Recovered**: Actual money recovered

Payment link created ≠ Revenue recovered

## Buildathon Notes

- Uses in-memory store (state resets on restart)
- For persistence, implement file-based or database-backed store
- Demo mode works without API key (mock responses)
- All safety boundaries enforced even in demo mode

## Files

```
backend/llm/
├── __init__.py
├── requirements.txt
├── README.md
├── demo.py
├── agent/
│   ├── __init__.py
│   ├── core.py
│   └── prompts.py
├── api/
│   ├── __init__.py
│   └── server.py
├── client/
│   ├── __init__.py
│   ├── base.py
│   └── anthropic_client.py
├── domain/
│   ├── __init__.py
│   └── results.py
├── store/
│   ├── __init__.py
│   └── decision_store.py
├── tests/
│   ├── __init__.py
│   └── test_agent.py
└── tools/
    ├── __init__.py
    ├── base.py
    ├── decision_tool.py
    ├── execute_tool.py
    ├── outcome_tool.py
    ├── status_tool.py
    └── summary_tool.py
```

## Frozen Files (DO NOT MODIFY)

- `backend/reven/**` - REVEN policy engine
- `backend/integrations/razorpay/**` - Razorpay integration
- `backend/schemas/streamflix.py` - Domain schemas
- `backend/simulator/**` - Test fixtures
