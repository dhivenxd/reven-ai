"""Tests for Razorpay webhook HTTP endpoints.

Tests:
- GET /health
- POST /webhooks/razorpay with valid/invalid signatures
- Idempotency (duplicate events)
- payment.failed flow
- payment.captured flow
- Unsupported events
- Malformed payloads
- No credential leakage
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

# Import the server app
from backend.integrations.razorpay.webhook_server import app

client = TestClient(app)


def sign_payload(payload: dict, secret: str) -> str:
    """Generate valid HMAC-SHA256 signature for webhook payload."""
    payload_bytes = json.dumps(payload).encode()
    return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()


def test_health_endpoint():
    """Test GET /health returns status without credentials."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "reven-razorpay-webhook"
    assert "timestamp" in data
    # Should not expose credentials
    assert "RAZORPAY_KEY_SECRET" not in str(data)
    assert "webhook_secret" not in str(data).lower()
    print("[OK] GET /health")


def test_missing_signature():
    """Test webhook rejects request without signature."""
    payload = {"event": "payment.failed"}
    response = client.post(
        "/webhooks/razorpay",
        json=payload,
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "missing_signature"
    print("[OK] Missing signature rejected")


def test_invalid_signature():
    """Test webhook rejects request with invalid signature."""
    payload = {
        "event": "payment.failed",
        "created_at": int(datetime.now().timestamp()),
        "payload": {
            "payment": {"entity": {"id": "pay_test"}},
            "subscription": {"entity": {"id": "sub_test"}},
        },
    }

    with patch("backend.integrations.razorpay.config.RAZORPAY_WEBHOOK_SECRET", "test_secret"):
        response = client.post(
            "/webhooks/razorpay",
            content=json.dumps(payload),
            headers={
                "X-Razorpay-Signature": "invalid_signature_0000",
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "invalid_signature"
    print("[OK] Invalid signature rejected")


def test_unsupported_event():
    """Test webhook rejects unsupported event types."""
    payload = {
        "event": "subscription.charged",  # Not supported
        "created_at": int(datetime.now().timestamp()),
    }

    with patch("backend.integrations.razorpay.config.RAZORPAY_WEBHOOK_SECRET", "test_secret"):
        signature = sign_payload(payload, "test_secret")
        response = client.post(
            "/webhooks/razorpay",
            content=json.dumps(payload),
            headers={
                "X-Razorpay-Signature": signature,
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "unsupported_event"
    print("[OK] Unsupported event rejected")


def test_malformed_payload():
    """Test webhook rejects malformed JSON."""
    malformed = b"not valid json {"

    with patch("backend.integrations.razorpay.config.RAZORPAY_WEBHOOK_SECRET", "test_secret"):
        signature = hmac.new(b"test_secret", malformed, hashlib.sha256).hexdigest()
        response = client.post(
            "/webhooks/razorpay",
            content=malformed,
            headers={
                "X-Razorpay-Signature": signature,
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "malformed_payload"
    print("[OK] Malformed payload rejected")


def test_payment_failed_flow():
    """Test complete payment.failed webhook flow."""
    payload = {
        "event": "payment.failed",
        "created_at": int(datetime.now().timestamp()),
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_failed",
                    "amount": 39900,
                    "currency": "INR",
                    "status": "failed",
                    "customer_id": "cust_test_001",
                    "subscription_id": "sub_test_001",
                    "email": "test@example.com",
                    "error_reason": "insufficient_funds",
                }
            },
            "subscription": {
                "entity": {
                    "id": "sub_test_001",
                    "customer_id": "cust_test_001",
                    "plan_id": "plan_standard",
                    "status": "active",
                    "current_start": int(datetime.now().timestamp()) - (20 * 86400),
                    "current_end": int(datetime.now().timestamp()) + (10 * 86400),
                }
            },
        },
    }

    with patch("backend.integrations.razorpay.config.RAZORPAY_WEBHOOK_SECRET", "test_secret"):
        with patch("backend.integrations.razorpay.config.is_configured", return_value=False):
            # Mock API call to avoid real network request
            signature = sign_payload(payload, "test_secret")
            response = client.post(
                "/webhooks/razorpay",
                content=json.dumps(payload),
                headers={
                    "X-Razorpay-Signature": signature,
                    "X-Razorpay-Event-Id": "evt_test_001",
                    "Content-Type": "application/json",
                },
            )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["event_type"] == "payment.failed"
    assert data["event_id"] == "evt_test_001"
    assert data["customer_id"] == "cust_test_001"
    assert "decision" in data
    assert "execution" in data
    # REVEN should recommend PAYMENT_RETRY or PAYMENT_REMINDER for payment failure
    assert data["decision"]["intervention_type"] in [
        "payment_retry",
        "payment_reminder",
        "no_action",
    ]
    print("[OK] payment.failed flow")


def test_payment_captured_flow():
    """Test payment.captured webhook flow."""
    payload = {
        "event": "payment.captured",
        "created_at": int(datetime.now().timestamp()),
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_captured",
                    "amount": 39900,
                    "currency": "INR",
                    "status": "captured",
                    "customer_id": "cust_test_002",
                    "subscription_id": "sub_test_002",
                }
            }
        },
    }

    with patch("backend.integrations.razorpay.config.RAZORPAY_WEBHOOK_SECRET", "test_secret"):
        signature = sign_payload(payload, "test_secret")
        response = client.post(
            "/webhooks/razorpay",
            content=json.dumps(payload),
            headers={
                "X-Razorpay-Signature": signature,
                "X-Razorpay-Event-Id": "evt_test_002",
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["event_type"] == "payment.captured"
    assert data["customer_id"] == "cust_test_002"
    assert data["amount"] == 399.0
    assert "Revenue recovered" in data["message"]
    print("[OK] payment.captured flow")


def test_duplicate_event_idempotency():
    """Test that duplicate events are not processed twice."""
    payload = {
        "event": "payment.captured",
        "created_at": int(datetime.now().timestamp()),
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_duplicate",
                    "amount": 19900,
                    "currency": "INR",
                    "status": "captured",
                    "customer_id": "cust_duplicate",
                }
            }
        },
    }

    with patch("backend.integrations.razorpay.config.RAZORPAY_WEBHOOK_SECRET", "test_secret"):
        signature = sign_payload(payload, "test_secret")

        # First request
        response1 = client.post(
            "/webhooks/razorpay",
            content=json.dumps(payload),
            headers={
                "X-Razorpay-Signature": signature,
                "X-Razorpay-Event-Id": "evt_duplicate_test",
                "Content-Type": "application/json",
            },
        )

        # Second request with same event ID
        response2 = client.post(
            "/webhooks/razorpay",
            content=json.dumps(payload),
            headers={
                "X-Razorpay-Signature": signature,
                "X-Razorpay-Event-Id": "evt_duplicate_test",
                "Content-Type": "application/json",
            },
        )

    assert response1.status_code == 200
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "duplicate"
    assert "already processed" in data2["message"]
    print("[OK] Duplicate event idempotency")


def test_no_credential_leakage():
    """Test that responses never expose credentials."""
    # Test health endpoint
    health = client.get("/health")
    health_text = json.dumps(health.json()).lower()
    assert "secret" not in health_text
    assert "key_id" not in health_text
    assert "rzp_" not in health_text

    # Test error responses
    error_response = client.post("/webhooks/razorpay", json={})
    error_text = json.dumps(error_response.json()).lower()
    assert "secret" not in error_text
    assert "rzp_" not in error_text

    print("[OK] No credential leakage")


def run_all_tests():
    """Run all webhook endpoint tests."""
    print("=" * 70)
    print("RAZORPAY WEBHOOK ENDPOINT TESTS")
    print("=" * 70)
    print()

    test_health_endpoint()
    test_missing_signature()
    test_invalid_signature()
    test_unsupported_event()
    test_malformed_payload()
    test_payment_failed_flow()
    test_payment_captured_flow()
    test_duplicate_event_idempotency()
    test_no_credential_leakage()

    print()
    print("=" * 70)
    print("ALL WEBHOOK ENDPOINT TESTS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
