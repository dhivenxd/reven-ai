"""Razorpay webhook signature validation and parsing."""

from __future__ import annotations

import json
from typing import Any

from backend.integrations.razorpay import config
from backend.integrations.razorpay.razorpay_client import (
    verify_webhook_signature,
)


class WebhookSignatureError(Exception):
    """Raised when webhook signature validation fails."""
    pass


class UnsupportedWebhookEvent(Exception):
    """Raised when webhook event type is not supported in Phase 2."""
    pass


def validate_and_parse_webhook(
    payload_bytes: bytes,
    signature: str,
) -> dict[str, Any]:
    """Validate webhook signature and parse payload.

    Args:
        payload_bytes: Raw webhook body bytes
        signature: X-Razorpay-Signature header value

    Returns:
        Parsed webhook payload dict

    Raises:
        WebhookSignatureError: If signature is invalid
        UnsupportedWebhookEvent: If event is not payment.failed
    """
    config.validate_for_webhook()

    is_valid = verify_webhook_signature(
        payload_bytes,
        signature,
        config.RAZORPAY_WEBHOOK_SECRET,  # type: ignore
    )

    if not is_valid:
        raise WebhookSignatureError(
            "Webhook signature validation failed. "
            "Payload may be forged or RAZORPAY_WEBHOOK_SECRET is incorrect."
        )

    payload = json.loads(payload_bytes.decode())

    # Supported events
    event_type = payload.get("event")
    supported_events = {"payment.failed", "payment.captured"}

    if event_type not in supported_events:
        raise UnsupportedWebhookEvent(
            f"Event type '{event_type}' is not supported. "
            f"Supported events: {', '.join(supported_events)}"
        )

    return payload
