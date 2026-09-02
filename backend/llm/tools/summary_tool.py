"""Tool: get_recovery_summary

Aggregates recovery metrics across all decisions.
Read-only. Does not fabricate aggregate values.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from backend.llm.domain.results import (
    RecoverySummaryResult,
    ToolResult,
    ToolStatus,
)

if TYPE_CHECKING:
    from backend.llm.store.decision_store import DecisionStore


def get_recovery_summary(
    timeframe_days: int,
    include_pending: bool,
    store: "DecisionStore",
) -> ToolResult:
    """
    Get aggregated recovery metrics.

    Args:
        timeframe_days: Number of days to look back
        include_pending: Whether to include pending decisions
        store: Decision store (injected, not LLM-controlled)

    Returns:
        ToolResult with RecoverySummaryResult data

    Security:
        - Read-only
        - Aggregates actual decisions only
        - Does not fabricate metrics
        - Distinguishes expected vs recovered revenue
    """
    try:
        summary_data = store.get_summary(
            days=timeframe_days,
            include_pending=include_pending,
        )

        result = RecoverySummaryResult(
            total_decisions=summary_data["total_decisions"],
            executed_decisions=summary_data["executed_decisions"],
            pending_decisions=summary_data["pending_decisions"],
            failed_executions=summary_data["failed_executions"],
            revenue_preserved=summary_data["revenue_preserved"],
            revenue_recovered=summary_data["revenue_recovered"],
            breakdown_by_type=summary_data["breakdown_by_type"],
            generated_at=datetime.now(),
        )

        return ToolResult(
            status=ToolStatus.SUCCESS,
            data=result.to_dict(),
        )

    except Exception as e:
        return ToolResult(
            status=ToolStatus.ERROR,
            error_message=f"Failed to generate summary: {str(e)}",
        )
