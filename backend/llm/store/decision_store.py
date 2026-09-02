"""Decision storage layer for REVEN LLM agent.

Since RevenueDecision does not have a persistent decision_id, this adapter
layer wraps REVEN decisions with an ID and provides storage/retrieval.

The store must NOT modify frozen REVEN code. It is a thin adapter layer.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

from backend.reven.decision_engine import RevenueDecision
from backend.schemas.streamflix import InterventionType


@dataclass
class StoredDecision:
    """A REVEN decision with an ID and metadata."""
    decision_id: str
    customer_id: str
    intervention_type: InterventionType
    expected_net_revenue: float
    confidence: float
    reason: str
    created_at: datetime
    alternatives: list[dict[str, Any]]  # Serialized InterventionEconomics
    execution_status: str = "pending"
    executed_at: Optional[datetime] = None
    execution_error: Optional[str] = None
    razorpay_result_id: Optional[str] = None

    def to_decision(self) -> RevenueDecision:
        """Reconstruct the original RevenueDecision."""
        # Import here to avoid circular dependency
        from backend.reven.economic_engine import InterventionEconomics

        return RevenueDecision(
            customer_id=self.customer_id,
            intervention_type=self.intervention_type,
            expected_net_revenue=self.expected_net_revenue,
            confidence=self.confidence,
            reason=self.reason,
            alternatives=[
                InterventionEconomics(
                    intervention_type=InterventionType(a["intervention_type"]),
                    success_probability=a["success_probability"],
                    baseline_probability=a["baseline_probability"],
                    gross_revenue_if_success=a["gross_revenue_if_success"],
                    baseline_expected_revenue=a["baseline_expected_revenue"],
                    expected_revenue=a["expected_revenue"],
                    incremental_lift=a["incremental_lift"],
                    incremental_revenue=a["incremental_revenue"],
                    intervention_cost=a["intervention_cost"],
                    offer_cost=a["offer_cost"],
                    expected_net_revenue=a["expected_net_revenue"],
                )
                for a in self.alternatives
            ],
        )


class DecisionStore:
    """Interface for decision storage."""

    def save_decision(
        self,
        decision: RevenueDecision,
        execution_status: str = "pending",
    ) -> str:
        """
        Save a REVEN decision and return its decision_id.

        Args:
            decision: The RevenueDecision from REVEN
            execution_status: Initial execution status

        Returns:
            decision_id: The unique identifier for this decision
        """
        raise NotImplementedError

    def get_decision(self, decision_id: str) -> Optional[StoredDecision]:
        """Retrieve a decision by ID."""
        raise NotImplementedError

    def get_decision_by_customer(
        self,
        customer_id: str,
        limit: int = 10,
    ) -> list[StoredDecision]:
        """Get recent decisions for a customer."""
        raise NotImplementedError

    def update_execution_status(
        self,
        decision_id: str,
        status: str,
        razorpay_result_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> bool:
        """Update execution status after attempt."""
        raise NotImplementedError

    def record_outcome(
        self,
        decision_id: str,
        outcome: dict[str, Any],
    ) -> bool:
        """Record outcome result."""
        raise NotImplementedError

    def get_summary(
        self,
        days: int = 30,
        include_pending: bool = False,
    ) -> dict[str, Any]:
        """Get aggregated recovery metrics."""
        raise NotImplementedError


class InMemoryDecisionStore(DecisionStore):
    """In-memory decision store for buildathon/demo.

    State resets on process restart. For production use, implement
    a file-based or database-backed store.

    Thread safety: Not guaranteed. For single-process use only.
    """

    def __init__(self):
        self._decisions: dict[str, StoredDecision] = {}
        self._customer_index: dict[str, list[str]] = {}

    def save_decision(
        self,
        decision: RevenueDecision,
        execution_status: str = "pending",
    ) -> str:
        """Save decision and return decision_id."""
        decision_id = f"dec_{uuid.uuid4().hex[:12]}"

        alternatives_data = [
            {
                "intervention_type": alt.intervention_type.value,
                "success_probability": alt.success_probability,
                "baseline_probability": alt.baseline_probability,
                "gross_revenue_if_success": alt.gross_revenue_if_success,
                "baseline_expected_revenue": alt.baseline_expected_revenue,
                "expected_revenue": alt.expected_revenue,
                "incremental_lift": alt.incremental_lift,
                "incremental_revenue": alt.incremental_revenue,
                "intervention_cost": alt.intervention_cost,
                "offer_cost": alt.offer_cost,
                "expected_net_revenue": alt.expected_net_revenue,
            }
            for alt in decision.alternatives
        ]

        stored = StoredDecision(
            decision_id=decision_id,
            customer_id=decision.customer_id,
            intervention_type=decision.intervention_type,
            expected_net_revenue=decision.expected_net_revenue,
            confidence=decision.confidence,
            reason=decision.reason,
            created_at=datetime.now(),
            alternatives=alternatives_data,
            execution_status=execution_status,
        )

        self._decisions[decision_id] = stored

        # Update customer index
        if decision.customer_id not in self._customer_index:
            self._customer_index[decision.customer_id] = []
        self._customer_index[decision.customer_id].append(decision_id)

        return decision_id

    def get_decision(self, decision_id: str) -> Optional[StoredDecision]:
        """Retrieve decision by ID."""
        return self._decisions.get(decision_id)

    def get_decision_by_customer(
        self,
        customer_id: str,
        limit: int = 10,
    ) -> list[StoredDecision]:
        """Get recent decisions for a customer."""
        ids = self._customer_index.get(customer_id, [])
        ids.sort(key=lambda d: self._decisions[d].created_at, reverse=True)
        return [self._decisions[id] for id in ids[:limit]]

    def update_execution_status(
        self,
        decision_id: str,
        status: str,
        razorpay_result_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> bool:
        """Update execution status."""
        stored = self._decisions.get(decision_id)
        if stored is None:
            return False

        stored.execution_status = status
        stored.executed_at = datetime.now() if status == "executed" else None
        stored.razorpay_result_id = razorpay_result_id
        stored.execution_error = error
        return True

    def record_outcome(
        self,
        decision_id: str,
        outcome: dict[str, Any],
    ) -> bool:
        """Record outcome result."""
        stored = self._decisions.get(decision_id)
        if stored is None:
            return False

        stored.execution_status = outcome.get("execution_status", stored.execution_status)
        return True

    def get_summary(
        self,
        days: int = 30,
        include_pending: bool = False,
    ) -> dict[str, Any]:
        """Get aggregated recovery metrics."""
        cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        total = 0
        executed = 0
        pending = 0
        failed = 0
        revenue_preserved = 0.0
        revenue_recovered = 0.0
        breakdown: dict[str, int] = {}

        for stored in self._decisions.values():
            # Skip old decisions
            if (cutoff - stored.created_at).days > days:
                continue

            total += 1

            if stored.intervention_type.value not in breakdown:
                breakdown[stored.intervention_type.value] = 0
            breakdown[stored.intervention_type.value] += 1

            if stored.execution_status == "executed":
                executed += 1
                # Estimate revenue from expected_net_revenue
                # Note: actual recovery confirmed via webhook
                revenue_preserved += stored.expected_net_revenue
            elif stored.execution_status == "failed":
                failed += 1
            elif include_pending or stored.execution_status == "pending":
                pending += 1

        return {
            "total_decisions": total,
            "executed_decisions": executed,
            "pending_decisions": pending,
            "failed_executions": failed,
            "revenue_preserved": round(revenue_preserved, 2),
            "revenue_recovered": round(revenue_recovered, 2),
            "breakdown_by_type": breakdown,
        }
