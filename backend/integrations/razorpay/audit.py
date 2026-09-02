"""Audit trail for Razorpay integration events.

Records:
- Webhook receipts
- REVEN decisions
- Execution results

NEVER logs credentials or sensitive customer data beyond identifiers.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_AUDIT_FILE = Path(__file__).parents[3] / "data" / "razorpay_audit.jsonl"


class AuditLogger:
    """Append-only audit log in JSONL format."""

    def __init__(self, audit_file: Path | None = None):
        self.audit_file = audit_file or DEFAULT_AUDIT_FILE
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)

    def log_webhook_received(
        self,
        event_type: str,
        customer_id: str,
        payment_id: str | None = None,
        subscription_id: str | None = None,
    ) -> None:
        """Log webhook receipt."""
        self._append(
            {
                "event": "webhook_received",
                "timestamp": datetime.now().isoformat(),
                "webhook_event_type": event_type,
                "customer_id": customer_id,
                "payment_id": payment_id,
                "subscription_id": subscription_id,
            }
        )

    def log_reven_decision(
        self,
        customer_id: str,
        intervention_type: str,
        expected_net_revenue: float,
        confidence: float,
        reason: str,
    ) -> None:
        """Log REVEN decision."""
        self._append(
            {
                "event": "reven_decision",
                "timestamp": datetime.now().isoformat(),
                "customer_id": customer_id,
                "intervention_type": intervention_type,
                "expected_net_revenue": expected_net_revenue,
                "confidence": confidence,
                "reason": reason,
            }
        )

    def log_execution_result(
        self,
        customer_id: str,
        intervention_type: str,
        execution_status: str,
        razorpay_operation: str | None,
        razorpay_resource_id: str | None,
        message: str,
    ) -> None:
        """Log execution gateway result."""
        self._append(
            {
                "event": "execution_result",
                "timestamp": datetime.now().isoformat(),
                "customer_id": customer_id,
                "intervention_type": intervention_type,
                "execution_status": execution_status,
                "razorpay_operation": razorpay_operation,
                "razorpay_resource_id": razorpay_resource_id,
                "message": message,
            }
        )

    def _append(self, record: dict[str, Any]) -> None:
        """Append a single JSONL record to the audit file."""
        with open(self.audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
