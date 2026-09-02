"""Tests for Razorpay integration layer.

Tests cover:
- Webhook signature validation
- Event mapping (Razorpay → REVEN)
- Execution gateway safety boundaries
- End-to-end flow
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime

from backend.integrations.razorpay.razorpay_client import verify_webhook_signature
from backend.integrations.razorpay.webhook_handler import (
    validate_and_parse_webhook,
    WebhookSignatureError,
    UnsupportedWebhookEvent,
)
from backend.integrations.razorpay.event_mapper import map_razorpay_to_reven
from backend.integrations.razorpay.execution_gateway import ExecutionGateway
from backend.reven.decision_engine import RevenueDecision
from backend.schemas.streamflix import InterventionType, Subscription, SubscriptionStatus


def test_webhook_signature_validation():
    """Test HMAC-SHA256 webhook signature validation."""
    secret = "test_webhook_secret_12345"
    payload = b'{"event":"payment.failed"}'

    # Compute valid signature
    valid_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    assert verify_webhook_signature(payload, valid_signature, secret) is True

    # Invalid signature
    invalid_signature = "0" * 64
    assert verify_webhook_signature(payload, invalid_signature, secret) is False

    print("[OK] Webhook signature validation")


def test_event_mapper():
    """Test Razorpay webhook → REVEN schema mapping."""
    webhook_payload = {
        "event": "payment.failed",
        "created_at": int(datetime.now().timestamp()),
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test123",
                    "amount": 39900,
                    "currency": "INR",
                    "status": "failed",
                    "customer_id": "cust_test001",
                    "subscription_id": "sub_test001",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_reason": "insufficient_funds",
                }
            },
            "subscription": {
                "entity": {
                    "id": "sub_test001",
                    "customer_id": "cust_test001",
                    "plan_id": "plan_standard",
                    "status": "active",
                    "current_start": int(datetime.now().timestamp()) - (20 * 86400),
                    "current_end": int(datetime.now().timestamp()) + (10 * 86400),
                }
            },
        },
    }

    customer, subscription, risk_events = map_razorpay_to_reven(webhook_payload)

    assert customer.customer_id == "cust_test001"
    assert subscription.subscription_id == "sub_test001"
    assert subscription.price == 399.0  # Converted from paise
    assert subscription.currency == "INR"
    assert len(risk_events) == 1
    assert risk_events[0].event_type.value == "payment_failed"
    assert risk_events[0].metadata["failure_reason"] == "insufficient_funds"

    print("[OK] Event mapper (Razorpay -> REVEN)")


def test_execution_gateway_blocks_no_action():
    """Test that execution gateway blocks NO_ACTION decisions."""
    decision = RevenueDecision(
        customer_id="cust_test001",
        intervention_type=InterventionType.NO_ACTION,
        expected_net_revenue=0.0,
        confidence=1.0,
        reason="No intervention needed",
        alternatives=[],
    )

    subscription = Subscription(
        subscription_id="sub_test001",
        customer_id="cust_test001",
        plan_id="plan_standard",
        status=SubscriptionStatus.ACTIVE,
        start_date=datetime.now().date(),
        current_period_start=datetime.now().date(),
        current_period_end=datetime.now().date(),
        price=399.0,
        currency="INR",
        auto_renew=True,
        cancellation_requested=False,
        cancelled_at=None,
    )

    gateway = ExecutionGateway()
    result = gateway.execute_decision(decision, subscription)

    assert result.execution_status == "blocked"
    assert result.razorpay_operation is None
    assert "NO_ACTION decisions are not executed" in result.message

    print("[OK] Execution gateway blocks NO_ACTION")


def test_execution_gateway_handles_unsupported_interventions():
    """Test that execution gateway returns no_api_available for unsupported types."""
    decision = RevenueDecision(
        customer_id="cust_test001",
        intervention_type=InterventionType.CANCELLATION_SAVE,
        expected_net_revenue=25.0,
        confidence=0.75,
        reason="Test",
        alternatives=[],
    )

    subscription = Subscription(
        subscription_id="sub_test001",
        customer_id="cust_test001",
        plan_id="plan_standard",
        status=SubscriptionStatus.ACTIVE,
        start_date=datetime.now().date(),
        current_period_start=datetime.now().date(),
        current_period_end=datetime.now().date(),
        price=399.0,
        currency="INR",
        auto_renew=True,
        cancellation_requested=False,
        cancelled_at=None,
    )

    gateway = ExecutionGateway()
    result = gateway.execute_decision(decision, subscription)

    assert result.execution_status == "no_api_available"
    assert "requires customer-facing channel" in result.message

    print("[OK] Execution gateway handles unsupported interventions")


def test_end_to_end_payment_failed_flow():
    """Test complete flow: webhook → REVEN → execution (without real API)."""
    from backend.reven.reven_engine import run_reven

    # Synthetic webhook
    webhook_payload = {
        "event": "payment.failed",
        "created_at": int(datetime.now().timestamp()),
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_e2e_test",
                    "amount": 39900,
                    "currency": "INR",
                    "status": "failed",
                    "customer_id": "cust_e2e_test",
                    "subscription_id": "sub_e2e_test",
                    "error_reason": "insufficient_funds",
                }
            },
            "subscription": {
                "entity": {
                    "id": "sub_e2e_test",
                    "customer_id": "cust_e2e_test",
                    "plan_id": "plan_standard",
                    "status": "active",
                    "current_start": int(datetime.now().timestamp()) - (20 * 86400),
                    "current_end": int(datetime.now().timestamp()) + (10 * 86400),
                }
            },
        },
    }

    # Map to REVEN
    customer, subscription, risk_events = map_razorpay_to_reven(webhook_payload)

    # Run REVEN (frozen backend)
    result = run_reven(
        customer=customer,
        subscription=subscription,
        risk_events=risk_events,
        engagement=None,  # Razorpay provides no engagement data
        seed=42,
    )

    decision = result.decision

    # REVEN should recommend PAYMENT_RETRY or PAYMENT_REMINDER for payment failure
    assert decision.intervention_type in [
        InterventionType.PAYMENT_RETRY,
        InterventionType.PAYMENT_REMINDER,
        InterventionType.NO_ACTION,
    ]

    # If REVEN recommends action, gateway should handle it
    if decision.intervention_type != InterventionType.NO_ACTION:
        gateway = ExecutionGateway()
        exec_result = gateway.execute_decision(decision, subscription)

        # Without real API credentials, execution will fail or be attempted
        assert exec_result.intervention_type == decision.intervention_type

    print("[OK] End-to-end payment.failed flow")


def run_all_tests():
    """Run all integration tests."""
    print("=" * 70)
    print("RAZORPAY INTEGRATION TESTS")
    print("=" * 70)
    print()

    test_webhook_signature_validation()
    test_event_mapper()
    test_execution_gateway_blocks_no_action()
    test_execution_gateway_handles_unsupported_interventions()
    test_end_to_end_payment_failed_flow()

    print()
    print("=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
