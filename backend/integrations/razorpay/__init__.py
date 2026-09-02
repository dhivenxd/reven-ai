"""Razorpay integration layer for REVEN.

Phase 2: Sandbox integration for payment.failed webhook flow.

Entry points:
- webhook_handler.validate_and_parse_webhook()
- event_mapper.map_razorpay_to_reven()
- execution_gateway.ExecutionGateway.execute_decision()
- audit.AuditLogger
"""

from backend.integrations.razorpay.webhook_handler import (
    validate_and_parse_webhook,
    WebhookSignatureError,
    UnsupportedWebhookEvent,
)
from backend.integrations.razorpay.event_mapper import map_razorpay_to_reven
from backend.integrations.razorpay.execution_gateway import (
    ExecutionGateway,
    ExecutionResult,
)
from backend.integrations.razorpay.audit import AuditLogger

__all__ = [
    "validate_and_parse_webhook",
    "WebhookSignatureError",
    "UnsupportedWebhookEvent",
    "map_razorpay_to_reven",
    "ExecutionGateway",
    "ExecutionResult",
    "AuditLogger",
]
