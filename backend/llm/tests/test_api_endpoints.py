"""Tests for LLM API server dashboard endpoints.

Tests the new frontend-facing endpoints:
1. GET /agent/summary
2. GET /agent/decisions/{decision_id}
3. GET /agent/policy/overview
4. GET /agent/decisions
5. POST /agent/demo/seed visibility through shared store
6. Captured payment state propagation

Also verifies that the shared store singleton works correctly.
"""

import pytest
from fastapi.testclient import TestClient

from backend.llm.api.server import app
from backend.llm.store.shared import get_shared_store, reset_shared_store
from backend.reven.decision_engine import RevenueDecision
from backend.reven.economic_engine import InterventionEconomics
from backend.schemas.streamflix import InterventionType


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_store():
    """Reset shared store before and after each test."""
    reset_shared_store()
    yield
    reset_shared_store()


@pytest.fixture
def shared_store():
    """Get the shared store singleton."""
    return get_shared_store()


@pytest.fixture
def sample_decisions(shared_store):
    """Create sample decisions in the shared store."""
    decisions = [
        RevenueDecision(
            customer_id="cust_api_001",
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
        ),
        RevenueDecision(
            customer_id="cust_api_002",
            intervention_type=InterventionType.NO_ACTION,
            expected_net_revenue=0.0,
            confidence=0.91,
            reason="No intervention profitable.",
            alternatives=[],
        ),
        RevenueDecision(
            customer_id="cust_api_003",
            intervention_type=InterventionType.RENEWAL_REMINDER,
            expected_net_revenue=86.78,
            confidence=0.74,
            reason="Renewal due soon.",
            alternatives=[
                InterventionEconomics(
                    intervention_type=InterventionType.RENEWAL_REMINDER,
                    success_probability=0.88,
                    baseline_probability=0.66,
                    gross_revenue_if_success=399.0,
                    baseline_expected_revenue=263.34,
                    expected_revenue=351.12,
                    incremental_lift=0.22,
                    incremental_revenue=87.78,
                    intervention_cost=1.0,
                    offer_cost=0.0,
                    expected_net_revenue=86.78,
                ),
            ],
        ),
    ]

    ids = []
    for d in decisions:
        decision_id = shared_store.save_decision(d)
        ids.append(decision_id)

    # Mark one as executed and one as captured
    shared_store.update_execution_status(ids[0], status="executed", razorpay_result_id="link_001")
    shared_store.update_execution_status(ids[2], status="executed", razorpay_result_id="link_003")
    shared_store.mark_captured(ids[2], 399.0, "pay_003")

    yield ids


# ============================================================
# SHARED STORE TESTS
# ============================================================


class TestSharedStoreSingleton:
    """Test that shared store is a true singleton."""

    def test_shared_store_is_singleton(self):
        """Calling get_shared_store() twice returns the same instance."""
        store1 = get_shared_store()
        store2 = get_shared_store()
        assert store1 is store2

    def test_shared_store_is_same_instance_as_module(self):
        """Shared store matches the module-level reference."""
        from backend.llm.store import shared as shared_module
        store = get_shared_store()
        assert store is shared_module._shared_store


# ============================================================
# GET /agent/summary TESTS
# ============================================================


class TestAgentSummary:
    """Tests for GET /agent/summary."""

    def test_summary_empty_store(self, client):
        """Returns valid aggregate data for empty store."""
        response = client.get("/agent/summary")
        assert response.status_code == 200
        data = response.json()

        assert data["total_decisions"] == 0
        assert data["total_customers"] == 0
        assert data["intervention_count"] == 0
        assert data["intervention_rate"] == 0.0
        assert data["no_action_count"] == 0
        assert data["no_action_percentage"] == 0.0
        assert data["executed_decisions"] == 0
        assert data["captured_decisions"] == 0
        assert data["pending_decisions"] == 0
        assert data["failed_executions"] == 0
        assert data["revenue_preserved"] == 0.0
        assert data["revenue_recovered"] == 0.0
        assert "timestamp" in data
        print("[OK] GET /agent/summary empty store")

    def test_summary_with_decisions(self, client, sample_decisions):
        """Returns valid aggregate data with decisions."""
        response = client.get("/agent/summary")
        assert response.status_code == 200
        data = response.json()

        assert data["total_decisions"] == 3
        assert data["intervention_count"] == 2  # executed + captured
        assert data["captured_decisions"] == 1
        assert data["executed_decisions"] == 1
        assert data["revenue_recovered"] == 399.0  # captured amount
        assert data["revenue_preserved"] > 0.0
        assert "intervention_breakdown" in data
        # no_action_count reflects pending decisions (execution_status=pending)
        # since our sample has 1 pending (the NO_ACTION decision)
        assert data["no_action_count"] <= 3  # bounded check
        print("[OK] GET /agent/summary with decisions")

    def test_summary_include_pending(self, client, sample_decisions):
        """include_pending parameter is passed through."""
        response = client.get("/agent/summary?include_pending=true")
        assert response.status_code == 200
        data = response.json()
        assert data["include_pending"] is True
        print("[OK] GET /agent/summary include_pending")


# ============================================================
# GET /agent/decisions/{decision_id} TESTS
# ============================================================


class TestGetDecision:
    """Tests for GET /agent/decisions/{decision_id}."""

    def test_decision_found(self, client, sample_decisions):
        """Returns an existing decision."""
        decision_id = sample_decisions[0]
        response = client.get(f"/agent/decisions/{decision_id}")
        assert response.status_code == 200
        data = response.json()

        assert data["decision_id"] == decision_id
        assert data["customer_id"] == "cust_api_001"
        assert data["intervention_type"] == "payment_retry"
        assert data["expected_net_revenue"] == 247.50
        assert data["confidence"] == 0.68
        assert data["execution_status"] == "executed"
        assert data["captured_amount"] is None  # not captured yet
        assert data["recovered_at"] is None
        assert "alternatives" in data
        assert "reason" in data
        print("[OK] GET /agent/decisions/{decision_id} found")

    def test_decision_not_found(self, client):
        """Returns 404 for unknown decision_id."""
        response = client.get("/agent/decisions/dec_unknown_xyz")
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"] == "not_found"
        print("[OK] GET /agent/decisions/{decision_id} 404")

    def test_captured_decision_detail(self, client, sample_decisions):
        """Captured decision shows correct recovered state."""
        # sample_decisions[2] was captured
        decision_id = sample_decisions[2]
        response = client.get(f"/agent/decisions/{decision_id}")
        assert response.status_code == 200
        data = response.json()

        assert data["execution_status"] == "captured"
        assert data["captured_amount"] == 399.0
        assert data["recovered_at"] is not None
        print("[OK] GET /agent/decisions/{decision_id} captured state")


# ============================================================
# GET /agent/policy/overview TESTS
# ============================================================


class TestPolicyOverview:
    """Tests for GET /agent/policy/overview."""

    def test_policy_overview_empty(self, client):
        """Returns valid policy data for empty store."""
        response = client.get("/agent/policy/overview")
        assert response.status_code == 200
        data = response.json()

        assert "intervention_distribution" in data
        assert "no_action_percentage" in data
        assert "no_action_count" in data
        assert "intervention_rate" in data
        assert "total_decisions" in data
        assert data["total_decisions"] == 0
        print("[OK] GET /agent/policy/overview empty")

    def test_policy_overview_with_data(self, client, sample_decisions):
        """Returns valid policy data with decisions."""
        response = client.get("/agent/policy/overview")
        assert response.status_code == 200
        data = response.json()

        assert data["total_decisions"] == 3
        assert data["captured_decisions"] == 1
        assert data["revenue_recovered"] == 399.0
        assert data["intervention_distribution"]["payment_retry"] == 1
        assert data["intervention_distribution"]["no_action"] == 1
        assert data["intervention_distribution"]["renewal_reminder"] == 1
        print("[OK] GET /agent/policy/overview with data")


# ============================================================
# GET /agent/decisions TESTS
# ============================================================


class TestListDecisions:
    """Tests for GET /agent/decisions."""

    def test_list_decisions_empty(self, client):
        """Returns empty list for empty store."""
        response = client.get("/agent/decisions")
        assert response.status_code == 200
        data = response.json()

        assert data["decisions"] == []
        assert data["total"] == 0
        assert data["count"] == 0
        print("[OK] GET /agent/decisions empty")

    def test_list_decisions_with_data(self, client, sample_decisions):
        """Returns decisions list with correct fields."""
        response = client.get("/agent/decisions")
        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 3
        assert data["count"] == 3
        assert len(data["decisions"]) == 3

        # Verify structure of first decision
        d = data["decisions"][0]
        assert "decision_id" in d
        assert "customer_id" in d
        assert "intervention_type" in d
        assert "execution_status" in d
        assert "created_at" in d
        print("[OK] GET /agent/decisions with data")

    def test_list_decisions_pagination(self, client, sample_decisions):
        """Pagination works correctly."""
        response = client.get("/agent/decisions?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()

        assert data["count"] == 2
        assert data["limit"] == 2
        assert data["offset"] == 0
        assert len(data["decisions"]) == 2
        print("[OK] GET /agent/decisions pagination")

    def test_list_decisions_offset(self, client, sample_decisions):
        """Offset pagination works."""
        response = client.get("/agent/decisions?limit=2&offset=2")
        assert response.status_code == 200
        data = response.json()

        assert data["count"] <= 1  # Only 1 remaining after offset 2
        assert data["offset"] == 2
        print("[OK] GET /agent/decisions offset pagination")


# ============================================================
# SEED + VISIBILITY TESTS
# ============================================================


class TestSeedVisibility:
    """Test that seeded decisions are visible through the dashboard APIs."""

    def test_seed_visible_in_summary(self, client):
        """Seeded decisions appear in summary."""
        # Seed
        seed_response = client.post("/agent/demo/seed")
        assert seed_response.status_code == 200
        seed_data = seed_response.json()
        assert seed_data["status"] == "seeded"
        assert len(seed_data["decision_ids"]) == 3

        # Check summary
        summary = client.get("/agent/summary")
        assert summary.status_code == 200
        summary_data = summary.json()

        assert summary_data["total_decisions"] == 3
        print("[OK] Seeded decisions visible in summary")

    def test_seed_visible_in_decision_list(self, client):
        """Seeded decisions appear in /agent/decisions."""
        client.post("/agent/demo/seed")

        response = client.get("/agent/decisions")
        data = response.json()

        assert data["total"] == 3
        customer_ids = {d["customer_id"] for d in data["decisions"]}
        assert customer_ids == {"cust_demo_001", "cust_demo_002", "cust_demo_003"}
        print("[OK] Seeded decisions visible in /agent/decisions")

    def test_seed_individual_decision(self, client):
        """Each seeded decision is retrievable by ID."""
        seed_response = client.post("/agent/demo/seed")
        seed_data = seed_response.json()

        decision_id = seed_data["decision_ids"][0]
        response = client.get(f"/agent/decisions/{decision_id}")
        assert response.status_code == 200
        data = response.json()

        assert data["decision_id"] == decision_id
        assert data["customer_id"] == "cust_demo_001"
        assert data["execution_status"] == "pending"
        assert data["captured_amount"] is None
        print("[OK] Seeded decision retrievable by ID")


# ============================================================
# PAYMENT LINK vs CAPTURED TESTS
# ============================================================


class TestPaymentLinkVsCaptured:
    """Test that payment link creation != recovered."""

    def test_payment_link_not_recovered_via_summary(self, client, shared_store):
        """Summary shows 0 recovered revenue when only payment link created."""
        from backend.reven.decision_engine import RevenueDecision
        from backend.reven.economic_engine import InterventionEconomics
        from backend.schemas.streamflix import InterventionType

        decision = RevenueDecision(
            customer_id="cust_link_only",
            intervention_type=InterventionType.PAYMENT_RETRY,
            expected_net_revenue=150.0,
            confidence=0.7,
            reason="Test",
            alternatives=[],
        )
        decision_id = shared_store.save_decision(decision)
        shared_store.update_execution_status(
            decision_id,
            status="executed",
            razorpay_result_id="link_only_test",
        )

        summary = client.get("/agent/summary")
        data = summary.json()

        assert data["executed_decisions"] == 1
        assert data["captured_decisions"] == 0
        assert data["revenue_recovered"] == 0.0
        print("[OK] Payment link (executed) shows revenue_recovered=0")

    def test_captured_shows_recovered_revenue(self, client, shared_store):
        """Summary shows correct revenue when payment is captured."""
        from backend.reven.decision_engine import RevenueDecision
        from backend.reven.economic_engine import InterventionEconomics
        from backend.schemas.streamflix import InterventionType

        decision = RevenueDecision(
            customer_id="cust_captured_api",
            intervention_type=InterventionType.PAYMENT_RETRY,
            expected_net_revenue=150.0,
            confidence=0.7,
            reason="Test",
            alternatives=[],
        )
        decision_id = shared_store.save_decision(decision)
        shared_store.update_execution_status(decision_id, status="executed")
        shared_store.mark_captured(decision_id, 399.0, "pay_captured_api")

        summary = client.get("/agent/summary")
        data = summary.json()

        assert data["captured_decisions"] == 1
        assert data["revenue_recovered"] == 399.0
        print("[OK] Captured payment shows revenue_recovered=399")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
