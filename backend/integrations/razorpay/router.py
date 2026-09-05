"""Razorpay Webhook Router.

Provides API endpoints for receiving and processing Razorpay webhooks.
Integrates with REVEN engine and shared decision store.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

from backend.integrations.razorpay.webhook_handler import (
    validate_and_parse_webhook,
    WebhookSignatureError,
    UnsupportedWebhookEvent,
)
from backend.integrations.razorpay.event_mapper import map_razorpay_to_reven
from backend.integrations.razorpay.execution_gateway import ExecutionGateway
from backend.integrations.razorpay.audit import AuditLogger
from backend.reven.reven_engine import run_reven

router = APIRouter(prefix="/webhooks/razorpay", tags=["webhooks"])

async def handle_payment_failed(
    request: Request,
    payload: dict,
    event_id: str | None,
) -> Response:
    """Handle payment.failed webhook.

    Flow:
        1. Map Razorpay payload -> REVEN schemas
        2. Call frozen run_reven()
        3. Execute decision via gateway
        4. Audit trail
        5. Save to shared store
    """
    try:
        audit: AuditLogger = request.app.state.audit
        gateway: ExecutionGateway = request.app.state.gateway
        decision_store = request.app.state.store

        # Extract identifiers for audit
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        customer_id = payment_entity.get("customer_id")
        payment_id = payment_entity.get("id")
        subscription_id = payment_entity.get("subscription_id")

        audit.log_webhook_received(
            event_type="payment.failed",
            customer_id=customer_id,
            payment_id=payment_id,
            subscription_id=subscription_id,
        )

        # Map to REVEN schemas
        customer, subscription, risk_events = map_razorpay_to_reven(payload)

        # Call frozen REVEN engine
        reven_result = run_reven(
            customer=customer,
            subscription=subscription,
            risk_events=risk_events,
            engagement=None,
            seed=None,
        )

        decision = reven_result.decision

        audit.log_reven_decision(
            customer_id=decision.customer_id,
            intervention_type=decision.intervention_type.value,
            expected_net_revenue=decision.expected_net_revenue,
            confidence=decision.confidence,
            reason=decision.reason,
        )

        # Execute decision via gateway
        execution_result = gateway.execute_decision(
            decision=decision,
            subscription=subscription,
            customer_email=payment_entity.get("email"),
            customer_contact=payment_entity.get("contact"),
        )

        audit.log_execution_result(
            customer_id=decision.customer_id,
            intervention_type=decision.intervention_type.value,
            execution_status=execution_result.execution_status,
            razorpay_operation=execution_result.razorpay_operation,
            razorpay_resource_id=execution_result.razorpay_resource_id,
            message=execution_result.message,
        )

        # Save decision to shared store
        decision_id = decision_store.save_decision(
            decision=decision,
            execution_status=execution_result.execution_status,
        )

        # Update with the payment link ID for later capture lookup
        if execution_result.razorpay_resource_id:
            decision_store.update_execution_status(
                decision_id,
                status=execution_result.execution_status,
                razorpay_result_id=execution_result.razorpay_resource_id,
                razorpay_payment_link_id=execution_result.razorpay_resource_id,
            )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "processed",
                "event_type": "payment.failed",
                "event_id": event_id,
                "customer_id": customer_id,
                "decision": {
                    "intervention_type": decision.intervention_type.value,
                    "expected_net_revenue": decision.expected_net_revenue,
                    "confidence": decision.confidence,
                },
                "execution": {
                    "status": execution_result.execution_status,
                    "operation": execution_result.razorpay_operation,
                    "resource_id": execution_result.razorpay_resource_id,
                    "resource_url": execution_result.razorpay_resource_url,
                },
            },
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "processing_error",
                "message": f"Failed to process payment.failed: {e}",
            },
        )

async def handle_payment_captured(
    request: Request,
    payload: dict,
    event_id: str | None,
) -> Response:
    """Handle payment.captured webhook.

    Flow:
        1. Identify decision via reference_id or customer_id
        2. Mark as captured in shared store
        3. Log to audit trail
    """
    try:
        audit: AuditLogger = request.app.state.audit
        decision_store = request.app.state.store

        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        customer_id = payment_entity.get("customer_id")
        payment_id = payment_entity.get("id")
        subscription_id = payment_entity.get("subscription_id")
        amount = payment_entity.get("amount", 0) / 100.0

        reference_id = payment_entity.get("reference_id")

        audit.log_webhook_received(
            event_type="payment.captured",
            customer_id=customer_id,
            payment_id=payment_id,
            subscription_id=subscription_id,
        )

        decision_id = None
        recovered = False

        if reference_id:
            stored = decision_store.get_decision(reference_id)
            if stored:
                decision_id = reference_id
                decision_store.mark_captured(
                    decision_id=decision_id,
                    captured_amount=amount,
                    razorpay_payment_id=payment_id,
                )
                recovered = True

        if not recovered and customer_id:
            customer_decisions = decision_store.get_decision_by_customer(
                customer_id, limit=1
            )
            if customer_decisions:
                decision_id = customer_decisions[0].decision_id
                decision_store.mark_captured(
                    decision_id=decision_id,
                    captured_amount=amount,
                    razorpay_payment_id=payment_id,
                )
                recovered = True

        audit._append({
            "event": "payment_recovered",
            "timestamp": datetime.now().isoformat(),
            "customer_id": customer_id,
            "payment_id": payment_id,
            "subscription_id": subscription_id,
            "amount": amount,
            "decision_id": decision_id,
            "message": (
                "Payment captured successfully. Revenue recovered."
                if recovered
                else "Payment captured but no matching decision found."
            ),
        })

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "processed",
                "event_type": "payment.captured",
                "event_id": event_id,
                "customer_id": customer_id,
                "payment_id": payment_id,
                "amount": amount,
                "decision_id": decision_id,
                "recovered": recovered,
                "message": (
                    "Payment captured. Revenue recovered."
                    if recovered
                    else "Payment captured. No matching decision found."
                ),
            },
        )

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "processing_error",
                "message": f"Failed to process payment.captured: {e}",
            },
        )

@router.post("")
async def razorpay_webhook(request: Request) -> Response:
    """Entry point for Razorpay webhooks."""
    body_bytes = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")
    event_id = request.headers.get("X-Razorpay-Event-Id")

    if not signature:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "missing_signature",
                "message": "X-Razorpay-Signature header is required",
            },
        )

    try:
        payload = validate_and_parse_webhook(body_bytes, signature)
    except WebhookSignatureError as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "invalid_signature",
                "message": str(e),
            },
        )
    except UnsupportedWebhookEvent as e:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "unsupported_event",
                "message": str(e),
            },
        )
    except json.JSONDecodeError as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "malformed_payload",
                "message": f"Invalid JSON: {e}",
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "processing_error",
                "message": f"Failed to validate webhook: {e}",
            },
        )

    event_type = payload.get("event")

    # Idempotency check
    if event_id:
        processed_events: set[str] = request.app.state.processed_events
        if event_id in processed_events:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": "duplicate",
                    "message": f"Event {event_id} already processed",
                    "event_type": event_type,
                },
            )

        processed_events.add(event_id)
        if len(processed_events) > 10000:
            # Remove oldest element to bound memory
            # Since sets are not ordered, we convert to list and pop
            # In a real app, we'd use a deque or Redis
            lst = list(processed_events)
            processed_events.remove(lst[0])

    if event_type == "payment.failed":
        return await handle_payment_failed(request, payload, event_id)
    elif event_type == "payment.captured":
        return await handle_payment_captured(request, payload, event_id)
    else:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "unsupported_event",
                "message": f"Event type '{event_type}' is not supported",
            },
        )
