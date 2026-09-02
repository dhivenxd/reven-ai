"""Map Razorpay webhook payloads to REVEN input schemas.

CRITICAL:
- Razorpay provides NO engagement or behavioral data.
- Do NOT fabricate engagement_declining, inactive, or any engagement metrics.
- Leave engagement=None when calling run_reven().
"""

from __future__ import annotations

from datetime import date, datetime

from backend.schemas.streamflix import (
    Customer,
    RiskEvent,
    RiskEventType,
    RiskSeverity,
    Subscription,
    SubscriptionStatus,
)


def map_razorpay_to_reven(
    webhook_payload: dict,
) -> tuple[Customer, Subscription, list[RiskEvent]]:
    """Convert Razorpay payment.failed webhook to REVEN input schemas.

    Args:
        webhook_payload: Parsed Razorpay webhook payload dict

    Returns:
        (Customer, Subscription, [RiskEvent]) tuple ready for run_reven()

    Raises:
        ValueError: If required fields are missing
    """
    payload_entity = webhook_payload.get("payload", {})
    payment = payload_entity.get("payment", {}).get("entity", {})
    subscription_data = payload_entity.get("subscription", {}).get("entity", {})

    # Extract identifiers
    customer_id = payment.get("customer_id") or subscription_data.get(
        "customer_id"
    )
    if not customer_id:
        raise ValueError("customer_id not found in webhook payload")

    subscription_id = payment.get("subscription_id") or subscription_data.get("id")
    if not subscription_id:
        raise ValueError("subscription_id not found in webhook payload")

    # Payment details
    amount = payment.get("amount", 0)
    currency = payment.get("currency", "INR")
    error_code = payment.get("error_code")
    error_description = payment.get("error_description")
    error_reason = payment.get("error_reason")

    # Map Razorpay error_reason to StreamFlix PaymentFailureReason-compatible string
    # Priority: error_reason (specific) over error_code (general)
    failure_reason = "bank_declined"
    if error_reason in ("insufficient_funds", "insufficient_balance"):
        failure_reason = "insufficient_funds"
    elif error_reason in ("card_expired", "expired_card"):
        failure_reason = "card_expired"
    elif error_reason in ("authentication_failed", "authentication_required"):
        failure_reason = "authentication_required"
    elif error_code in ("BAD_REQUEST_ERROR", "GATEWAY_ERROR"):
        failure_reason = "network_error"

    # Subscription details
    subscription_status_raw = subscription_data.get("status", "active")
    subscription_status = SubscriptionStatus.ACTIVE
    if subscription_status_raw == "halted":
        subscription_status = SubscriptionStatus.PAST_DUE
    elif subscription_status_raw in ("cancelled", "completed", "expired"):
        subscription_status = SubscriptionStatus.CANCELED

    # Parse timestamps (Razorpay uses Unix epoch seconds)
    created_at_ts = webhook_payload.get("created_at", 0)
    created_at = (
        datetime.fromtimestamp(created_at_ts)
        if created_at_ts
        else datetime.now()
    )

    current_start_ts = subscription_data.get("current_start")
    current_end_ts = subscription_data.get("current_end")

    current_period_start = (
        date.fromtimestamp(current_start_ts)
        if current_start_ts
        else date.today()
    )
    current_period_end = (
        date.fromtimestamp(current_end_ts)
        if current_end_ts
        else date.today()
    )

    # Convert amount from paise to rupees (Razorpay sends paise, REVEN uses rupees)
    price = amount / 100.0

    # Build Customer
    customer = Customer(
        customer_id=customer_id,
        signup_date=current_period_start,  # Approximation
        tenure_days=(date.today() - current_period_start).days,
        current_plan_id=subscription_data.get("plan_id", "unknown"),
        current_subscription_status=subscription_status,
        lifetime_value=price,  # Single-period approximation
        created_at=created_at,
    )

    # Build Subscription
    subscription = Subscription(
        subscription_id=subscription_id,
        customer_id=customer_id,
        plan_id=subscription_data.get("plan_id", "unknown"),
        status=subscription_status,
        start_date=current_period_start,
        current_period_start=current_period_start,
        current_period_end=current_period_end,
        price=price,
        currency=currency,
        auto_renew=True,  # Default assumption
        cancellation_requested=False,
        cancelled_at=None,
    )

    # Build RiskEvent for PAYMENT_FAILED
    risk_event = RiskEvent(
        event_id=f"razorpay_{payment.get('id', 'unknown')}",
        customer_id=customer_id,
        event_type=RiskEventType.PAYMENT_FAILED,
        occurred_at=created_at,
        severity=RiskSeverity.HIGH,
        metadata={
            "failure_reason": failure_reason,
            "razorpay_error_code": error_code,
            "razorpay_error_description": error_description,
            "razorpay_payment_id": payment.get("id"),
            "razorpay_subscription_id": subscription_id,
            "amount": amount,
            "currency": currency,
        },
    )

    return customer, subscription, [risk_event]
