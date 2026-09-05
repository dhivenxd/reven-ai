import pytest
from fastapi.testclient import TestClient
from backend.llm.api.server import app
from backend.llm.store.shared import get_shared_store
from backend.integrations.razorpay.execution_gateway import ExecutionGateway
from backend.integrations.razorpay.audit import AuditLogger
from backend.llm.agent.core import RevenAgent
from backend.llm.client.base import RevenLLMClient, LLMResponse, Message
import json
from unittest.mock import patch, MagicMock

client = TestClient(app)

# Manually initialize state for TestClient if lifespan didn't run
app.state.store = app.state.store if hasattr(app.state, 'store') else get_shared_store()
app.state.gateway = app.state.gateway if hasattr(app.state, 'gateway') else ExecutionGateway()
app.state.audit = app.state.audit if hasattr(app.state, 'audit') else AuditLogger()
app.state.processed_events = app.state.processed_events if hasattr(app.state, 'processed_events') else set()
app.state.session_counter = app.state.session_counter if hasattr(app.state, 'session_counter') else 0

# Mock LLM Client to avoid API key requirement
class MockLLMClient(RevenLLMClient):
    async def chat(self, messages, system_instruction, tools, max_tokens=1024):
        # If the message is a tool result, return a final summary
        last_msg = messages[-1].content.lower()
        if "tool results" in last_msg:
            return LLMResponse(
                text="I have retrieved the requested data and updated the store.",
                tool_uses=[],
                stop_reason="end_turn"
            )

        if "execute" in last_msg:
            import re
            match = re.search(r'dec_[a-z0-9]+', last_msg)
            decision_id = match.group(0) if match else "dec_unknown"
            return LLMResponse(
                text=f"Executing decision {decision_id}...",
                tool_uses=[
                    ToolUse(
                        tool_name="execute_approved_decision",
                        tool_input={"decision_id": decision_id},
                        tool_use_id="call_exec_1"
                    )
                ],
                stop_reason="tool_use"
            )
        elif "summary" in last_msg:
            return LLMResponse(
                text="Checking the recovery summary...",
                tool_uses=[
                    ToolUse(
                        tool_name="get_recovery_summary",
                        tool_input={"timeframe_days": 30, "include_pending": True},
                        tool_use_id="call_sum_1"
                    )
                ],
                stop_reason="tool_use"
            )
        elif "why" in last_msg or "decision" in last_msg:
            import re
            match = re.search(r'dec_[a-z0-9]+', last_msg)
            decision_id = match.group(0) if match else "dec_unknown"
            return LLMResponse(
                text=f"Looking up details for decision {decision_id}...",
                tool_uses=[
                    ToolUse(
                        tool_name="get_reven_decision",
                        tool_input={"decision_id": decision_id},
                        tool_use_id="call_det_1"
                    )
                ],
                stop_reason="tool_use"
            )
        return LLMResponse(text="I can't do that.", tool_uses=[], stop_reason="end_turn")
    async def close(self): pass

from backend.llm.client.base import ToolUse

app.state.agent = RevenAgent(
    llm_client=MockLLMClient(),
    decision_store=app.state.store,
    execution_gateway=app.state.gateway
)

def test_payment_failed_flow():
    print("Testing payment.failed flow...")

    # Mock Razorpay payload for payment.failed
    # We need a valid signature for the webhook_handler to pass.
    # In a test environment, we might need to bypass signature check or provide a valid one.
    # Let's check how validate_and_parse_webhook is implemented.

    # Actually, the best way to test is to temporarily disable signature verification
    # or use the real signing logic.

    # For now, let's try to send a request. If it fails with 400, we know signature is required.
    payload = {
        "event": "payment.failed",
        "created_at": 1630000000,
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_123",
                    "customer_id": "cust_test_001",
                    "subscription_id": "sub_test_123",
                    "amount": 39900,
                    "currency": "INR",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_reason": "insufficient_funds",
                    "email": "test@example.com",
                    "contact": "1234567890"
                }
            },
            "subscription": {
                "entity": {
                    "id": "sub_test_123",
                    "customer_id": "cust_test_001",
                    "plan": {"id": "plan_gold"},
                    "status": "active",
                    "current_start": 1620000000,
                    "current_end": 1630000000
                }
            }
        }
    }

    # We'll send the request. Since we don't have a real secret for the TestClient
    # and the server uses a real secret from .env, this will fail unless we mock the validator.

    # Let's use a trick: patch the validate_and_parse_webhook function.
    from backend.integrations.razorpay.webhook_handler import validate_and_parse_webhook
    from unittest.mock import patch

    with patch('backend.integrations.razorpay.router.validate_and_parse_webhook') as mock_val:
        mock_val.return_value = payload

        response = client.post(
            "/webhooks/razorpay",
            headers={"X-Razorpay-Signature": "mock_sig", "X-Razorpay-Event-Id": "evt_test_001"},
            content=json.dumps(payload)
        )

        print(f"Webhook Response: {response.status_code} - {response.json()}")
        assert response.status_code == 200
        assert response.json()["status"] == "processed"

    # Verify decision is visible in API
    decisions_resp = client.get("/agent/decisions")
    # avoid unicode encode errors in terminal
    print(f"Decisions Response: {decisions_resp.status_code}")
    assert decisions_resp.status_code == 200
    assert len(decisions_resp.json()["decisions"]) > 0
    assert decisions_resp.json()["decisions"][0]["customer_id"] == "cust_test_001"

def test_execution_flow():
    print("\nTesting execution flow...")

    # 1. Create a decision first using payment.failed (reuse logic)
    payload = {
        "event": "payment.failed",
        "created_at": 1630000000,
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_exec_123",
                    "customer_id": "cust_exec_001",
                    "subscription_id": "sub_exec_123",
                    "amount": 39900,
                    "currency": "INR",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_reason": "insufficient_funds",
                    "email": "exec@example.com",
                    "contact": "1234567890"
                }
            },
            "subscription": {
                "entity": {
                    "id": "sub_exec_123",
                    "customer_id": "cust_exec_001",
                    "plan": {"id": "plan_gold"},
                    "status": "active",
                    "current_start": 1620000000,
                    "current_end": 1630000000
                }
            }
        }
    }

    with patch('backend.integrations.razorpay.router.validate_and_parse_webhook') as mock_val:
        mock_val.return_value = payload
        client.post(
            "/webhooks/razorpay",
            headers={"X-Razorpay-Signature": "mock_sig", "X-Razorpay-Event-Id": "evt_exec_001"},
            content=json.dumps(payload)
        )

    # Get the decision ID
    dec_resp = client.get("/agent/decisions")
    decision_id = dec_resp.json()["decisions"][0]["decision_id"]
    print(f"Created decision for execution: {decision_id}")

    # 2. Mock create_payment_link to return success
    mock_link = {
        "id": "plink_test_123",
        "short_url": "https://rzp.io/i/test"
    }

    with patch('backend.integrations.razorpay.execution_gateway.create_payment_link') as mock_create:
        mock_create.return_value = mock_link

        # Trigger execution via agent chat
        chat_resp = client.post(
            "/agent/chat",
            json={"message": f"Execute decision {decision_id}"}
        )
        print(f"Chat response: {chat_resp.status_code} - {chat_resp.json()['message']}")

        # Verify decision state in store
        detail_resp = client.get(f"/agent/decisions/{decision_id}")
        detail = detail_resp.json()
        print(f"Decision state: {detail['execution_status']}")
        print(f"Execution error: {detail.get('execution_error')}")

        assert detail["execution_status"] == "executed"
        assert detail["razorpay_payment_link_id"] == "plink_test_123"
        assert detail["razorpay_result_id"] == "plink_test_123"

def test_payment_captured_flow():
    print("\nTesting payment.captured flow...")

    # 1. Setup: Create a decision and execute it to get a payment link
    payload = {
        "event": "payment.failed",
        "created_at": 1630000000,
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_cap_123",
                    "customer_id": "cust_cap_001",
                    "subscription_id": "sub_cap_123",
                    "amount": 39900,
                    "currency": "INR",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_reason": "insufficient_funds",
                    "email": "cap@example.com",
                    "contact": "1234567890"
                }
            },
            "subscription": {
                "entity": {
                    "id": "sub_cap_123",
                    "customer_id": "cust_cap_001",
                    "plan": {"id": "plan_gold"},
                    "status": "active",
                    "current_start": 1620000000,
                    "current_end": 1630000000
                }
            }
        }
    }

    with patch('backend.integrations.razorpay.router.validate_and_parse_webhook') as mock_val:
        mock_val.return_value = payload
        client.post(
            "/webhooks/razorpay",
            headers={"X-Razorpay-Signature": "mock_sig", "X-Razorpay-Event-Id": "evt_cap_001"},
            content=json.dumps(payload)
        )

    dec_resp = client.get("/agent/decisions")
    decision_id = dec_resp.json()["decisions"][0]["decision_id"]

    # Execute to get payment link
    mock_link = {"id": "plink_cap_123", "short_url": "https://rzp.io/i/cap"}
    with patch('backend.integrations.razorpay.execution_gateway.create_payment_link') as mock_create:
        mock_create.return_value = mock_link
        client.post("/agent/chat", json={"message": f"Execute decision {decision_id}"})

    # 2. Trigger payment.captured webhook
    captured_payload = {
        "event": "payment.captured",
        "created_at": 1630001000,
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_captured_123",
                    "customer_id": "cust_cap_001",
                    "subscription_id": "sub_cap_123",
                    "amount": 39900,
                    "reference_id": decision_id, # Using decision_id as reference_id
                }
            }
        }
    }

    with patch('backend.integrations.razorpay.router.validate_and_parse_webhook') as mock_val:
        mock_val.return_value = captured_payload
        response = client.post(
            "/webhooks/razorpay",
            headers={"X-Razorpay-Signature": "mock_sig", "X-Razorpay-Event-Id": "evt_cap_captured_001"},
            content=json.dumps(captured_payload)
        )

        print(f"Capture Webhook Response: {response.status_code} - {response.json()}")
        assert response.status_code == 200
        assert response.json()["recovered"] is True

    # 3. Verify state
    detail_resp = client.get(f"/agent/decisions/{decision_id}")
    detail = detail_resp.json()
    print(f"Decision state: {detail['execution_status']}")
    print(f"Captured amount: {detail['captured_amount']}")

    assert detail["execution_status"] == "captured"
    assert detail["captured_amount"] == 399.0

    # 4. Verify summary
    summary_resp = client.get("/agent/summary")
    summary = summary_resp.json()
    print(f"Summary captured decisions: {summary['captured_decisions']}")
    assert summary["captured_decisions"] >= 1
    assert summary["revenue_recovered"] >= 399.0

def test_gemini_visibility():
    print("\nTesting Gemini state visibility...")

    # 1. Setup: Ensure there is a captured decision
    # We can reuse a decision from previous tests or create a new one.
    # Let's create a new one to be clean.
    payload = {
        "event": "payment.failed",
        "created_at": 1630000000,
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_gem_123",
                    "customer_id": "cust_gem_001",
                    "subscription_id": "sub_gem_123",
                    "amount": 39900,
                    "currency": "INR",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_reason": "insufficient_funds",
                    "email": "gem@example.com",
                    "contact": "1234567890"
                }
            },
            "subscription": {
                "entity": {
                    "id": "sub_gem_123",
                    "customer_id": "cust_gem_001",
                    "plan": {"id": "plan_gold"},
                    "status": "active",
                    "current_start": 1620000000,
                    "current_end": 1630000000
                }
            }
        }
    }

    with patch('backend.integrations.razorpay.router.validate_and_parse_webhook') as mock_val:
        mock_val.return_value = payload
        client.post(
            "/webhooks/razorpay",
            headers={"X-Razorpay-Signature": "mock_sig", "X-Razorpay-Event-Id": "evt_gem_001"},
            content=json.dumps(payload)
        )

    dec_resp = client.get("/agent/decisions")
    decision_id = dec_resp.json()["decisions"][0]["decision_id"]

    # Mark as captured
    captured_payload = {
        "event": "payment.captured",
        "created_at": 1630001000,
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_gem_captured_123",
                    "customer_id": "cust_gem_001",
                    "subscription_id": "sub_gem_123",
                    "amount": 39900,
                    "reference_id": decision_id,
                }
            }
        }
    }

    with patch('backend.integrations.razorpay.router.validate_and_parse_webhook') as mock_val:
        mock_val.return_value = captured_payload
        client.post(
            "/webhooks/razorpay",
            headers={"X-Razorpay-Signature": "mock_sig", "X-Razorpay-Event-Id": "evt_gem_captured_001"},
            content=json.dumps(captured_payload)
        )

    # 2. Query Gemini about the summary
    chat_resp = client.post(
        "/agent/chat",
        json={"message": "What is the current recovery summary?"}
    )
    print(f"Chat Summary Response: {chat_resp.status_code} - {chat_resp.json()['message']}")
    assert chat_resp.status_code == 200
    # Since we use a MockLLMClient, it won't actually query the store unless we implement the tool calls.
    # Wait, the MockLLMClient I wrote only handles "execute".
    # I need it to handle summary queries too if I want to test the agent loop.

    # 3. Query Gemini about the specific decision
    chat_resp_detail = client.post(
        "/agent/chat",
        json={"message": f"Why was decision {decision_id} successful?"}
    )
    print(f"Chat Detail Response: {chat_resp_detail.status_code} - {chat_resp_detail.json()['message']}")
    assert chat_resp_detail.status_code == 200

def test_no_action_and_idempotency():
    print("\nTesting NO_ACTION and Idempotency...")

    # 1. Test NO_ACTION
    # We can mock run_reven to return a NO_ACTION decision
    from backend.reven.decision_engine import RevenueDecision
    from backend.schemas.streamflix import InterventionType
    from backend.reven.economic_engine import InterventionEconomics

    no_action_decision = RevenueDecision(
        customer_id="cust_no_action",
        intervention_type=InterventionType.NO_ACTION,
        expected_net_revenue=0.0,
        confidence=1.0,
        reason="Low risk, no intervention justified",
        alternatives=[]
    )

    payload = {
        "event": "payment.failed",
        "created_at": 1630000000,
        "payload": {
            "payment": {"entity": {"id": "pay_no_123", "customer_id": "cust_no_action", "subscription_id": "sub_no_123"}},
            "subscription": {"entity": {"id": "sub_no_123", "customer_id": "cust_no_action"}}
        }
    }

    with patch('backend.integrations.razorpay.router.run_reven') as mock_reven:
        mock_reven.return_value.decision = no_action_decision
        with patch('backend.integrations.razorpay.router.validate_and_parse_webhook') as mock_val:
            mock_val.return_value = payload
            response = client.post(
                "/webhooks/razorpay",
                headers={"X-Razorpay-Signature": "mock_sig", "X-Razorpay-Event-Id": "evt_no_001"},
                content=json.dumps(payload)
            )
            assert response.status_code == 200

    # Verify NO_ACTION decision was stored and not executed
    dec_resp = client.get("/agent/decisions")
    no_action_dec = next(d for d in dec_resp.json()["decisions"] if d["customer_id"] == "cust_no_action")
    assert no_action_dec["intervention_type"] == "no_action"
    assert no_action_dec["execution_status"] == "blocked"

    # 2. Test Idempotency: payment.failed
    with patch('backend.integrations.razorpay.router.validate_and_parse_webhook') as mock_val:
        mock_val.return_value = payload
        # First call
        client.post(
            "/webhooks/razorpay",
            headers={"X-Razorpay-Signature": "mock_sig", "X-Razorpay-Event-Id": "evt_idem_001"},
            content=json.dumps(payload)
        )
        # Second call with same Event ID
        response = client.post(
            "/webhooks/razorpay",
            headers={"X-Razorpay-Signature": "mock_sig", "X-Razorpay-Event-Id": "evt_idem_001"},
            content=json.dumps(payload)
        )
        assert response.json()["status"] == "duplicate"

    # 3. Test Idempotency: payment.captured
    # Setup: execute a decision
    captured_payload = {
        "event": "payment.captured",
        "created_at": 1630001000,
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_cap_idem_123",
                    "customer_id": "cust_no_action",
                    "subscription_id": "sub_no_123",
                    "amount": 39900,
                    "reference_id": no_action_decision.customer_id, # Use customer_id for fallback
                }
            }
        }
    }

    with patch('backend.integrations.razorpay.router.validate_and_parse_webhook') as mock_val:
        mock_val.return_value = captured_payload
        # First call
        client.post(
            "/webhooks/razorpay",
            headers={"X-Razorpay-Signature": "mock_sig", "X-Razorpay-Event-Id": "evt_cap_idem_001"},
            content=json.dumps(captured_payload)
        )
        # Second call with same Event ID
        response = client.post(
            "/webhooks/razorpay",
            headers={"X-Razorpay-Signature": "mock_sig", "X-Razorpay-Event-Id": "evt_cap_idem_001"},
            content=json.dumps(captured_payload)
        )
        assert response.json()["status"] == "duplicate"

if __name__ == "__main__":
    test_payment_failed_flow()
    print("payment.failed flow verified successfully!")
    test_execution_flow()
    print("execution flow verified successfully!")
    test_payment_captured_flow()
    print("payment.captured flow verified successfully!")
    test_gemini_visibility()
    print("Gemini state visibility verified successfully!")
    test_no_action_and_idempotency()
    print("NO_ACTION and Idempotency verified successfully!")




