"""Comprehensive tests for REVEN LLM Agent.

All tests are deterministic and do NOT require ANTHROPIC_API_KEY.
Tests use mocked LLM provider and real tool implementations.
"""

import pytest
from datetime import datetime, date
from unittest.mock import AsyncMock, MagicMock, patch

from backend.llm.agent.core import RevenAgent
from backend.llm.client.base import Message, ToolUse, LLMResponse
from backend.llm.store.decision_store import InMemoryDecisionStore
from backend.llm.tools.status_tool import get_customer_recovery_status
from backend.llm.tools.decision_tool import get_reven_decision
from backend.llm.tools.outcome_tool import get_recovery_outcome
from backend.llm.tools.summary_tool import get_recovery_summary
from backend.llm.tools.execute_tool import execute_approved_decision
from backend.reven.decision_engine import RevenueDecision
from backend.schemas.streamflix import InterventionType
from backend.integrations.razorpay.execution_gateway import ExecutionGateway, ExecutionResult


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def decision_store():
    """In-memory decision store for testing."""
    return InMemoryDecisionStore()


@pytest.fixture
def sample_decision():
    """Sample REVEN decision for testing."""
    from backend.reven.economic_engine import InterventionEconomics

    return RevenueDecision(
        customer_id="cust_test_001",
        intervention_type=InterventionType.PAYMENT_RETRY,
        expected_net_revenue=150.50,
        confidence=0.72,
        reason="Payment failure detected. Retry expected to recover with 65% success rate.",
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


@pytest.fixture
def mock_llm_client():
    """Mock LLM client."""
    client = AsyncMock()
    return client


@pytest.fixture
def mock_execution_gateway():
    """Mock execution gateway."""
    gateway = MagicMock(spec=ExecutionGateway)
    gateway.execute_decision = MagicMock(
        return_value=ExecutionResult(
            decision_id="cust_test_001",
            intervention_type=InterventionType.PAYMENT_RETRY,
            execution_status="executed",
            razorpay_operation="create_payment_link",
            razorpay_resource_id="link_abc123",
            razorpay_resource_url="https://rzp.io/i/abc123",
            executed_at=datetime.now(),
            message="Payment recovery link created successfully.",
        )
    )
    return gateway


# ============================================================
# TOOL TESTS (Unit)
# ============================================================


class TestGetCustomerRecoveryStatus:
    """Tests for get_customer_recovery_status tool."""

    def test_status_not_found(self, decision_store):
        """Returns NOT_FOUND for unknown customer."""
        result = get_customer_recovery_status(
            customer_id="unknown_customer",
            store=decision_store,
        )
        assert result.status.value == "not_found"

    def test_status_found(self, decision_store, sample_decision):
        """Returns status for customer with decision."""
        decision_id = decision_store.save_decision(sample_decision)

        result = get_customer_recovery_status(
            customer_id=sample_decision.customer_id,
            store=decision_store,
        )

        assert result.status.value == "success"
        assert result.data["customer_id"] == sample_decision.customer_id
        assert result.data["decision_id"] == decision_id
        assert result.data["intervention_type"] == "payment_retry"
        assert result.data["confidence"] == 0.72


class TestGetRevenDecision:
    """Tests for get_reven_decision tool."""

    def test_decision_not_found(self, decision_store):
        """Returns NOT_FOUND for unknown decision_id."""
        result = get_reven_decision(
            decision_id="dec_unknown",
            store=decision_store,
        )
        assert result.status.value == "not_found"

    def test_decision_found(self, decision_store, sample_decision):
        """Returns full decision details."""
        decision_id = decision_store.save_decision(sample_decision)

        result = get_reven_decision(
            decision_id=decision_id,
            store=decision_store,
        )

        assert result.status.value == "success"
        assert result.data["decision_id"] == decision_id
        assert result.data["intervention_type"] == "payment_retry"
        assert result.data["expected_net_revenue"] == 150.50
        assert result.data["confidence"] == 0.72
        assert "alternatives" in result.data


class TestGetRecoveryOutcome:
    """Tests for get_recovery_outcome tool."""

    def test_outcome_not_found(self, decision_store):
        """Returns NOT_FOUND for unknown decision_id."""
        result = get_recovery_outcome(
            decision_id="dec_unknown",
            store=decision_store,
        )
        assert result.status.value == "not_found"

    def test_outcome_pending(self, decision_store, sample_decision):
        """Returns pending status."""
        decision_id = decision_store.save_decision(sample_decision)

        result = get_recovery_outcome(
            decision_id=decision_id,
            store=decision_store,
        )

        assert result.status.value == "success"
        assert result.data["execution_status"] == "pending"

    def test_outcome_executed(self, decision_store, sample_decision):
        """Returns executed status."""
        decision_id = decision_store.save_decision(sample_decision)
        decision_store.update_execution_status(
            decision_id,
            status="executed",
            razorpay_result_id="link_xyz",
        )

        result = get_recovery_outcome(
            decision_id=decision_id,
            store=decision_store,
        )

        assert result.status.value == "success"
        assert result.data["execution_status"] == "executed"
        assert "Payment link created" in result.data["execution_message"]

    def test_outcome_structured_payment_link_truth(self, decision_store, sample_decision):
        """Payment link execution returns structured truth fields."""
        decision_id = decision_store.save_decision(sample_decision)
        decision_store.update_execution_status(
            decision_id,
            status="executed",
            razorpay_result_id="link_xyz",
        )

        result = get_recovery_outcome(
            decision_id=decision_id,
            store=decision_store,
        )

        assert result.status.value == "success"
        # Structured execution type
        assert result.data["execution_type"] == "payment_link_created"
        assert result.data["requires_customer_action"] is True
        assert result.data["revenue_recovered"] is False
        # Currency field
        assert result.data["currency"] == "INR"
        # Critical safety message
        assert "Revenue is NOT yet recovered" in result.data["execution_message"]


class TestGetRecoverySummary:
    """Tests for get_recovery_summary tool."""

    def test_summary_empty(self, decision_store):
        """Returns empty summary for no decisions."""
        result = get_recovery_summary(
            timeframe_days=30,
            include_pending=False,
            store=decision_store,
        )

        assert result.status.value == "success"
        assert result.data["total_decisions"] == 0

    def test_summary_with_decisions(self, decision_store, sample_decision):
        """Returns aggregated metrics."""
        decision_store.save_decision(sample_decision)

        result = get_recovery_summary(
            timeframe_days=30,
            include_pending=True,
            store=decision_store,
        )

        assert result.status.value == "success"
        assert result.data["total_decisions"] == 1
        assert result.data["pending_decisions"] == 1
        assert "payment_retry" in result.data["breakdown_by_type"]


# ============================================================
# EXECUTION TOOL TESTS (Security Critical)
# ============================================================


class TestExecuteApprovedDecision:
    """Tests for execute_approved_decision tool (security critical)."""

    def test_execute_not_found(self, decision_store, mock_execution_gateway):
        """Rejects execution of non-existent decision."""
        result = execute_approved_decision(
            decision_id="dec_unknown",
            store=decision_store,
            gateway=mock_execution_gateway,
        )

        assert result.status.value == "not_found"
        assert "not found" in result.error_message

    def test_execute_no_action_blocked(self, decision_store, mock_execution_gateway):
        """Blocks execution of NO_ACTION decisions."""
        from backend.reven.economic_engine import InterventionEconomics

        no_action_decision = RevenueDecision(
            customer_id="cust_test_002",
            intervention_type=InterventionType.NO_ACTION,
            expected_net_revenue=0.0,
            confidence=1.0,
            reason="No action needed.",
            alternatives=[],
        )

        decision_id = decision_store.save_decision(no_action_decision)

        result = execute_approved_decision(
            decision_id=decision_id,
            store=decision_store,
            gateway=mock_execution_gateway,
        )

        assert result.status.value == "blocked"
        assert "NO_ACTION" in result.error_message

    def test_execute_already_executed(self, decision_store, mock_execution_gateway, sample_decision):
        """Prevents duplicate execution."""
        decision_id = decision_store.save_decision(sample_decision)
        decision_store.update_execution_status(decision_id, status="executed")

        result = execute_approved_decision(
            decision_id=decision_id,
            store=decision_store,
            gateway=mock_execution_gateway,
        )

        assert result.status.value == "blocked"
        assert "already been executed" in result.error_message

    def test_execute_payment_retry(self, decision_store, mock_execution_gateway, sample_decision):
        """Executes payment retry decision."""
        decision_id = decision_store.save_decision(sample_decision)

        result = execute_approved_decision(
            decision_id=decision_id,
            store=decision_store,
            gateway=mock_execution_gateway,
        )

        assert result.status.value == "success"
        assert result.data["execution_status"] == "executed"
        assert mock_execution_gateway.execute_decision.called


class TestSecurityBoundaries:
    """Tests to verify security boundaries."""

    def test_no_arbitrary_intervention_type(self, decision_store, mock_execution_gateway):
        """Confirms LLM cannot specify intervention_type for execution."""
        # The execute_approved_decision tool only accepts decision_id
        # It does NOT accept intervention_type as a parameter
        import inspect
        sig = inspect.signature(execute_approved_decision)
        params = list(sig.parameters.keys())

        assert "intervention_type" not in params
        assert "decision_id" in params

    def test_no_arbitrary_razorpay_parameters(self, decision_store, mock_execution_gateway):
        """Confirms LLM cannot pass arbitrary Razorpay parameters."""
        import inspect
        sig = inspect.signature(execute_approved_decision)
        params = list(sig.parameters.keys())

        # Only allows decision_id, store, and gateway (all server-side)
        assert "amount" not in params
        assert "currency" not in params
        assert "razorpay_params" not in params

    def test_execution_gateway_called(self, decision_store, mock_execution_gateway, sample_decision):
        """Confirms ExecutionGateway is the only Razorpay entry point."""
        decision_id = decision_store.save_decision(sample_decision)

        execute_approved_decision(
            decision_id=decision_id,
            store=decision_store,
            gateway=mock_execution_gateway,
        )

        # Verify gateway was called
        assert mock_execution_gateway.execute_decision.called


class TestPaymentLinkDistinction:
    """Tests that payment link creation is NOT reported as recovered revenue."""

    def test_payment_link_not_recovered(self, decision_store, sample_decision):
        """Payment link result includes clear disclaimer."""
        decision_id = decision_store.save_decision(sample_decision)
        decision_store.update_execution_status(
            decision_id,
            status="executed",
            razorpay_result_id="link_test",
        )

        result = get_recovery_outcome(
            decision_id=decision_id,
            store=decision_store,
        )

        # Check that the message clearly states this is not recovered
        assert "not yet recovered" in result.data["execution_message"].lower()


# ============================================================
# AGENT TESTS (Integration)
# ============================================================


class TestRevenAgent:
    """Tests for RevenAgent orchestration."""

    @pytest.mark.asyncio
    async def test_agent_query_status(self, mock_llm_client, decision_store, mock_execution_gateway, sample_decision):
        """Agent can retrieve and explain recovery status."""
        decision_id = decision_store.save_decision(sample_decision)

        # Mock LLM response: query status, no tool calls
        mock_llm_client.chat.return_value = LLMResponse(
            text="The customer has an approved PAYMENT_RETRY intervention.",
            tool_uses=[],
            stop_reason="end_turn",
        )

        agent = RevenAgent(mock_llm_client, decision_store, mock_execution_gateway)
        response = await agent.chat("What happened with cust_test_001?")

        assert "PAYMENT_RETRY" in response or "recovery" in response

    @pytest.mark.asyncio
    async def test_agent_cannot_create_decision(self, mock_llm_client, decision_store, mock_execution_gateway):
        """Agent cannot invent or create a REVEN decision."""
        mock_llm_client.chat.return_value = LLMResponse(
            text="I don't have an approved decision for that customer.",
            tool_uses=[],
            stop_reason="end_turn",
        )

        agent = RevenAgent(mock_llm_client, decision_store, mock_execution_gateway)
        response = await agent.chat("Execute a PAYMENT_RETRY for customer_xyz")

        # Should explain that REVEN must make the decision
        assert "don't" in response.lower() or "cannot" in response.lower()


# ============================================================
# DATA FABRICATION TESTS
# ============================================================


class TestNoDataFabrication:
    """Tests that data is never fabricated."""

    def test_unknown_customer_not_fabricated(self, decision_store):
        """Does not fabricate data for unknown customers."""
        result = get_customer_recovery_status(
            customer_id="totally_fake_customer",
            store=decision_store,
        )

        # Should be not found, not fabricated
        assert result.status.value == "not_found"
        assert result.data is None or result.data.get("status") == "not_found"

    def test_missing_outcome_not_fabricated(self, decision_store, sample_decision):
        """Does not fabricate outcome for pending decisions."""
        decision_id = decision_store.save_decision(sample_decision)

        result = get_recovery_outcome(
            decision_id=decision_id,
            store=decision_store,
        )

        # Should indicate pending, not fabricate success
        assert result.data["execution_status"] == "pending"
        assert "not yet executed" in result.data.get("execution_message", "").lower()

    def test_inr_currency_not_usd(self, decision_store, sample_decision):
        """All amounts are INR, not USD."""
        decision_id = decision_store.save_decision(sample_decision)
        decision_store.update_execution_status(decision_id, status="executed")

        result = get_recovery_outcome(
            decision_id=decision_id,
            store=decision_store,
        )

        # Must have currency field set to INR
        assert "currency" in result.data
        assert result.data["currency"] == "INR"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
