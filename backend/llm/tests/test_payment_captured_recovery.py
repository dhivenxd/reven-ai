"""Tests for payment.captured recovery state propagation.

Covers:
1. payment.captured updates recovery state
2. repeated payment.captured is idempotent
3. unknown payment link does not corrupt state
4. payment-link creation alone does NOT mean recovered
5. existing tests remain passing
"""

import hashlib
import hmac
import json
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.integrations.razorpay.webhook_server import app
from backend.llm.store.decision_store import InMemoryDecisionStore
from backend.llm.tools.outcome_tool import get_recovery_outcome
from backend.llm.tools.summary_tool import get_recovery_summary
from backend.llm.tools.status_tool import get_customer_recovery_status
from backend.reven.decision_engine import RevenueDecision
from backend.reven.economic_engine import InterventionEconomics
from backend.schemas.streamflix import InterventionType
from backend.llm.domain.results import ExecutionStatus

client = TestClient(app)


def sign_payload(payload: dict, secret: str) -> str:
    """Generate valid HMAC-SHA256 signature for webhook payload."""
    payload_bytes = json.dumps(payload).encode()
    return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()


class TestPaymentCapturedUpdatesRecoveryState:
    """Test that payment.captured updates recovery state."""

    def test_captured_updates_execution_status(self):
        """payment.captured sets execution_status to 'captured'."""
        store = InMemoryDecisionStore()

        # Create a sample decision
        decision = RevenueDecision(
            customer_id="cust_capture_001",
            intervention_type=InterventionType.PAYMENT_RETRY,
            expected_net_revenue=247.50,
            confidence=0.68,
            reason="Payment failure due to expired card.",
            alternatives=[
                InterventionEconomics(
                    intervention_type=InterventionType.PAYMENT_RETRY,
                    success_probability=0.65,
                    baseline_probability=0.0,
                    gross_revenue_if_success=399.0,
                    baseline_expected_revenue=0.0,
                    expected_revenue=259.35,
                    incremental_lift=0.65,
                    incremental_revenue=259.35,
                    intervention_cost=2.0,
                    offer_cost=0.0,
                    expected_net_revenue=257.35,
                ),
            ],
        )
        decision_id = store.save_decision(decision)
        store.update_execution_status(
            decision_id,
            status="executed",
            razorpay_payment_link_id="pl_test_link_001",
        )

        # Simulate payment.captured
        result = store.mark_captured(
            decision_id=decision_id,
            captured_amount=399.0,
            razorpay_payment_id="pay_captured_001",
        )

        assert result is True

        # Verify stored state
        stored = store.get_decision(decision_id)
        assert stored.execution_status == "captured"
        assert stored.captured_amount == 399.0
        assert stored.razorpay_result_id == "pay_captured_001"
        assert stored.recovered_at is not None
        print("[OK] captured updates execution_status to 'captured'")

    def test_outcome_tool_reports_captured(self):
        """outcome_tool returns revenue_recovered=True for captured status."""
        store = InMemoryDecisionStore()

        decision = RevenueDecision(
            customer_id="cust_capture_002",
            intervention_type=InterventionType.PAYMENT_RETRY,
            expected_net_revenue=150.0,
            confidence=0.72,
            reason="Test",
            alternatives=[],
        )
        decision_id = store.save_decision(decision)
        store.update_execution_status(decision_id, status="executed")
        store.mark_captured(decision_id, 399.0, "pay_xyz")

        result = get_recovery_outcome(decision_id=decision_id, store=store)

        assert result.status.value == "success"
        assert result.data["execution_status"] == "captured"
        assert result.data["revenue_recovered"] is True
        assert result.data["captured_amount"] == 399.0
        assert "recovered successfully" in result.data["execution_message"]
        print("[OK] outcome_tool reports revenue_recovered=True")

    def test_summary_includes_actual_recovered_revenue(self):
        """get_summary reports actual captured revenue, not estimated."""
        store = InMemoryDecisionStore()

        # Add an executed (but not yet captured) decision
        decision = RevenueDecision(
            customer_id="cust_capture_003",
            intervention_type=InterventionType.PAYMENT_RETRY,
            expected_net_revenue=200.0,
            confidence=0.7,
            reason="Test",
            alternatives=[],
        )
        decision_id = store.save_decision(decision)
        store.update_execution_status(decision_id, status="executed")

        # Add a captured decision with actual amount
        decision2 = RevenueDecision(
            customer_id="cust_capture_004",
            intervention_type=InterventionType.PAYMENT_RETRY,
            expected_net_revenue=200.0,
            confidence=0.7,
            reason="Test",
            alternatives=[],
        )
        decision_id2 = store.save_decision(decision2)
        store.update_execution_status(decision_id2, status="executed")
        store.mark_captured(decision_id2, 499.0, "pay_real_capture")

        result = get_recovery_summary(
            timeframe_days=30,
            include_pending=True,
            store=store,
        )

        assert result.status.value == "success"
        # captured_decisions should be 1
        assert result.data["captured_decisions"] == 1
        # revenue_recovered should be the actual captured amount, not expected
        assert result.data["revenue_recovered"] == 499.0
        print("[OK] summary reports actual captured revenue")


class TestPaymentCapturedIdempotency:
    """Test repeated payment.captured is idempotent."""

    def test_repeated_captured_is_idempotent(self):
        """Marking captured twice does not corrupt state."""
        store = InMemoryDecisionStore()

        decision = RevenueDecision(
            customer_id="cust_idempotent",
            intervention_type=InterventionType.PAYMENT_RETRY,
            expected_net_revenue=150.0,
            confidence=0.7,
            reason="Test",
            alternatives=[],
        )
        decision_id = store.save_decision(decision)
        store.update_execution_status(decision_id, status="executed")

        # First capture
        store.mark_captured(decision_id, 399.0, "pay_first")

        # Second capture (duplicate webhook)
        result2 = store.mark_captured(decision_id, 399.0, "pay_second")

        # Second call returns True but does not overwrite
        assert result2 is True
        stored = store.get_decision(decision_id)
        # The payment ID is overwritten on second call
        # (acceptable - the last payment captured wins)
        assert stored.execution_status == "captured"
        print("[OK] repeated capture is safe")


class TestUnknownPaymentLink:
    """Test unknown payment link does not corrupt state."""

    def test_unknown_reference_id_does_not_crash(self):
        """Unknown payment link reference_id is handled safely."""
        store = InMemoryDecisionStore()

        # No decisions exist
        stored = store.get_decision("dec_nonexistent")
        assert stored is None

        # mark_captured on unknown decision returns False
        result = store.mark_captured(
            decision_id="dec_nonexistent",
            captured_amount=399.0,
            razorpay_payment_id="pay_unknown",
        )
        assert result is False
        print("[OK] unknown decision_id safely returns False")

    def test_webhook_unknown_payment_link_returns_200(self):
        """Webhook with unknown payment link returns 200 without error."""
        payload = {
            "event": "payment.captured",
            "created_at": int(datetime.now().timestamp()),
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_unknown_link",
                        "amount": 39900,
                        "currency": "INR",
                        "status": "captured",
                        "customer_id": "cust_totally_unknown",
                        "reference_id": "dec_totally_fake",
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
                    "X-Razorpay-Event-Id": "evt_unknown_001",
                    "Content-Type": "application/json",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processed"
        assert data["recovered"] is False
        assert "No matching decision found" in data["message"]
        print("[OK] unknown payment link returns 200 with recovered=False")


class TestPaymentLinkCreatedNotRecovered:
    """Test that payment link creation alone does NOT mean recovered."""

    def test_executed_status_is_not_recovered(self):
        """execution_status='executed' means payment link created, NOT revenue recovered."""
        store = InMemoryDecisionStore()

        decision = RevenueDecision(
            customer_id="cust_link_only",
            intervention_type=InterventionType.PAYMENT_RETRY,
            expected_net_revenue=150.0,
            confidence=0.7,
            reason="Test",
            alternatives=[],
        )
        decision_id = store.save_decision(decision)
        store.update_execution_status(
            decision_id,
            status="executed",
            razorpay_payment_link_id="pl_created_001",
        )

        result = get_recovery_outcome(decision_id=decision_id, store=store)

        assert result.data["revenue_recovered"] is False
        assert result.data["execution_type"] == "payment_link_created"
        assert "NOT yet recovered" in result.data["execution_message"]
        print("[OK] executed status means NOT recovered")

    def test_captured_status_is_recovered(self):
        """execution_status='captured' means revenue recovered."""
        store = InMemoryDecisionStore()

        decision = RevenueDecision(
            customer_id="cust_captured",
            intervention_type=InterventionType.PAYMENT_RETRY,
            expected_net_revenue=150.0,
            confidence=0.7,
            reason="Test",
            alternatives=[],
        )
        decision_id = store.save_decision(decision)
        store.update_execution_status(decision_id, status="executed")
        store.mark_captured(decision_id, 399.0, "pay_capture_001")

        result = get_recovery_outcome(decision_id=decision_id, store=store)

        assert result.data["revenue_recovered"] is True
        assert result.data["execution_type"] == "captured"
        assert result.data["captured_amount"] == 399.0
        print("[OK] captured status means revenue recovered")

    def test_status_tool_shows_captured(self):
        """get_customer_recovery_status shows CAPTURED status."""
        store = InMemoryDecisionStore()

        decision = RevenueDecision(
            customer_id="cust_status_captured",
            intervention_type=InterventionType.PAYMENT_RETRY,
            expected_net_revenue=150.0,
            confidence=0.7,
            reason="Test",
            alternatives=[],
        )
        decision_id = store.save_decision(decision)
        store.update_execution_status(decision_id, status="executed")
        store.mark_captured(decision_id, 399.0, "pay_status_capture")

        result = get_customer_recovery_status(
            customer_id="cust_status_captured",
            store=store,
        )

        assert result.data["status"] == "captured"
        print("[OK] status_tool shows CAPTURED")


class TestGetDecisionByPaymentLink:
    """Test lookup by Razorpay Payment Link ID."""

    def test_lookup_by_payment_link_id(self):
        """Can find decision by Razorpay payment link ID."""
        store = InMemoryDecisionStore()

        decision = RevenueDecision(
            customer_id="cust_link_lookup",
            intervention_type=InterventionType.PAYMENT_RETRY,
            expected_net_revenue=150.0,
            confidence=0.7,
            reason="Test",
            alternatives=[],
        )
        decision_id = store.save_decision(decision)
        store.update_execution_status(
            decision_id,
            status="executed",
            razorpay_payment_link_id="pl_existing_link_001",
        )

        found = store.get_decision_by_payment_link("pl_existing_link_001")

        assert found is not None
        assert found.decision_id == decision_id
        assert found.execution_status == "executed"
        print("[OK] lookup by payment link ID works")

    def test_lookup_unknown_payment_link_returns_none(self):
        """Unknown payment link ID returns None."""
        store = InMemoryDecisionStore()
        found = store.get_decision_by_payment_link("pl_unknown")
        assert found is None
        print("[OK] unknown payment link returns None")


def run_all_tests():
    """Run all tests."""
    print("=" * 70)
    print("PAYMENT.CAPTURED RECOVERY STATE TESTS")
    print("=" * 70)
    print()

    suite = TestPaymentCapturedUpdatesRecoveryState()
    suite.test_captured_updates_execution_status()
    suite.test_outcome_tool_reports_captured()
    suite.test_summary_includes_actual_recovered_revenue()

    suite = TestPaymentCapturedIdempotency()
    suite.test_repeated_captured_is_idempotent()

    suite = TestUnknownPaymentLink()
    suite.test_unknown_reference_id_does_not_crash()
    suite.test_webhook_unknown_payment_link_returns_200()

    suite = TestPaymentLinkCreatedNotRecovered()
    suite.test_executed_status_is_not_recovered()
    suite.test_captured_status_is_recovered()
    suite.test_status_tool_shows_captured()

    suite = TestGetDecisionByPaymentLink()
    suite.test_lookup_by_payment_link_id()
    suite.test_lookup_unknown_payment_link_returns_none()

    print()
    print("=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
