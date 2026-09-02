"""Domain result types for LLM tools.

Typed structures that tools return to the LLM.
All results are read-only and must not be fabricated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Any

from backend.reven.decision_engine import RevenueDecision
from backend.reven.intervention_engine import InterventionPlan
from backend.reven.state_engine import CustomerState
from backend.schemas.streamflix import InterventionType, Outcome
from backend.integrations.razorpay.execution_gateway import ExecutionResult


class ExecutionStatus(str, Enum):
    """Status of an execution attempt."""
    PENDING = "pending"
    EXECUTED = "executed"
    FAILED = "failed"
    BLOCKED = "blocked"
    NOT_FOUND = "not_found"
    ALREADY_EXECUTED = "already_executed"


class ToolStatus(str, Enum):
    """Status of a tool operation."""
    SUCCESS = "success"
    NOT_FOUND = "not_found"
    ERROR = "error"
    BLOCKED = "blocked"


@dataclass
class ToolResult:
    """Result from any tool call."""
    status: ToolStatus
    data: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    timestamp: datetime = None  # type: ignore

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class ToolError(Exception):
    """Error raised by tool operations."""
    message: str
    tool_name: str
    error_type: str

    @classmethod
    def not_found(cls, tool_name: str, item_id: str) -> "ToolError":
        return cls(
            message=f"Item not found: {item_id}",
            tool_name=tool_name,
            error_type="not_found",
        )

    @classmethod
    def blocked(cls, tool_name: str, reason: str) -> "ToolError":
        return cls(
            message=reason,
            tool_name=tool_name,
            error_type="blocked",
        )

    @classmethod
    def execution_failed(cls, tool_name: str, reason: str) -> "ToolError":
        return cls(
            message=f"Execution failed: {reason}",
            tool_name=tool_name,
            error_type="execution_failed",
        )


# ============================================================
# TOOL RESULT TYPES
# ============================================================


@dataclass
class RecoveryStatusResult:
    """Result from get_customer_recovery_status."""
    customer_id: str
    status: ExecutionStatus
    decision: Optional[RevenueDecision] = None
    decision_id: Optional[str] = None
    intervention_type: Optional[InterventionType] = None
    confidence: Optional[float] = None
    expected_net_revenue: Optional[float] = None
    reven_rationale: Optional[str] = None
    execution_status: Optional[str] = None
    outcome: Optional[Outcome] = None
    execution_result: Optional[ExecutionResult] = None
    decision_history: list[dict[str, Any]] = None  # type: ignore
    last_updated: datetime = None  # type: ignore

    def __post_init__(self):
        if self.decision_history is None:
            self.decision_history = []
        if self.last_updated is None:
            self.last_updated = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert to serializable dict for LLM."""
        result: dict[str, Any] = {
            "customer_id": self.customer_id,
            "status": self.status.value,
        }

        if self.decision_id:
            result["decision_id"] = self.decision_id

        if self.intervention_type:
            result["intervention_type"] = self.intervention_type.value

        if self.confidence is not None:
            result["confidence"] = self.confidence

        if self.expected_net_revenue is not None:
            result["expected_net_revenue"] = self.expected_net_revenue

        if self.reven_rationale:
            result["reven_rationale"] = self.reven_rationale

        if self.execution_status:
            result["execution_status"] = self.execution_status

        if self.outcome:
            result["outcome"] = {
                "revenue_preserved": self.outcome.revenue_preserved,
                "intervention_cost": self.outcome.intervention_cost,
                "net_revenue": self.outcome.net_revenue,
                "subscription_renewed": self.outcome.subscription_renewed,
                "payment_recovered": self.outcome.payment_recovered,
                "reason": self.outcome.reason,
            }

        if self.decision_history:
            result["decision_history"] = self.decision_history

        return result


@dataclass
class DecisionOutcome:
    """Full decision with outcome information."""
    decision_id: str
    decision: RevenueDecision
    execution_result: Optional[ExecutionResult] = None
    outcome: Optional[Outcome] = None
    execution_status: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to serializable dict for LLM."""
        result: dict[str, Any] = {
            "decision_id": self.decision_id,
            "intervention_type": self.decision.intervention_type.value,
            "expected_net_revenue": self.decision.expected_net_revenue,
            "confidence": self.decision.confidence,
            "reason": self.decision.reason,
            "alternatives": [
                {
                    "intervention_type": alt.intervention_type.value,
                    "expected_net_revenue": alt.expected_net_revenue,
                    "success_probability": alt.success_probability,
                }
                for alt in self.decision.alternatives
            ],
        }

        if self.execution_result:
            result["execution"] = {
                "status": self.execution_result.execution_status,
                "operation": self.execution_result.razorpay_operation,
                "resource_id": self.execution_result.razorpay_resource_id,
                "resource_url": self.execution_result.razorpay_resource_url,
                "message": self.execution_result.message,
            }

        if self.outcome:
            result["outcome"] = {
                "revenue_preserved": self.outcome.revenue_preserved,
                "intervention_cost": self.outcome.intervention_cost,
                "net_revenue": self.outcome.net_revenue,
                "subscription_renewed": self.outcome.subscription_renewed,
                "payment_recovered": self.outcome.payment_recovered,
                "reason": self.outcome.reason,
            }

        return result


@dataclass
class RecoverySummaryResult:
    """Result from get_recovery_summary."""
    total_decisions: int
    executed_decisions: int
    pending_decisions: int
    failed_executions: int
    revenue_preserved: float
    revenue_recovered: float
    breakdown_by_type: dict[str, int]
    generated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to serializable dict for LLM."""
        return {
            "total_decisions": self.total_decisions,
            "executed_decisions": self.executed_decisions,
            "pending_decisions": self.pending_decisions,
            "failed_executions": self.failed_executions,
            "revenue_preserved": self.revenue_preserved,
            "revenue_recovered": self.revenue_recovered,
            "breakdown_by_type": self.breakdown_by_type,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class ExecutionConfirmation:
    """Result from execute_approved_decision."""
    decision_id: str
    intervention_type: InterventionType
    execution_status: str
    razorpay_operation: Optional[str]
    razorpay_resource_id: Optional[str]
    razorpay_resource_url: Optional[str]
    message: str
    executed_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to serializable dict for LLM."""
        return {
            "decision_id": self.decision_id,
            "intervention_type": self.intervention_type.value,
            "execution_status": self.execution_status,
            "razorpay_operation": self.razorpay_operation,
            "razorpay_resource_id": self.razorpay_resource_id,
            "razorpay_resource_url": self.razorpay_resource_url,
            "message": self.message,
            "executed_at": self.executed_at.isoformat(),
        }
