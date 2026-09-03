"""FastAPI webhook server for Razorpay integration.

This is the HTTP entry point for receiving Razorpay webhooks.

Endpoints:
    POST /webhooks/razorpay - Receive Razorpay webhooks
    GET /health - Health check

Configure Razorpay Dashboard webhook URL to:
    https://<public-host>/webhooks/razorpay

For local development, expose via secure tunnel (ngrok, cloudflare tunnel, etc).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse

from backend.integrations.razorpay.webhook_handler import (
    validate_and_parse_webhook,
    WebhookSignatureError,
    UnsupportedWebhookEvent,
)
from backend.integrations.razorpay.event_mapper import map_razorpay_to_reven
from backend.integrations.razorpay.execution_gateway import ExecutionGateway
from backend.integrations.razorpay.audit import AuditLogger
from backend.integrations.razorpay import config
from backend.reven.reven_engine import run_reven
from backend.llm.store.shared import get_shared_store


# Idempotency: track processed event IDs to prevent duplicate execution
_processed_events: set[str] = set()
_MAX_PROCESSED_EVENTS = 10000  # Bounded memory


app = FastAPI(
    title="REVEN Razorpay Webhook Server",
    description="Webhook endpoint for Razorpay payment events",
    version="1.0.0",
)


audit = AuditLogger()
gateway = ExecutionGateway()
# Shared decision store — the SAME instance used by the LLM API server.
# Decisions from payment.failed webhooks are saved here so that
# payment.captured webhooks can look them up and mark revenue as recovered.
# When both servers run in the same process, they share one store.
decision_store = get_shared_store()


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint.

    Returns basic status without exposing credentials.
    """
    return {
        "status": "healthy",
        "service": "reven-razorpay-webhook",
        "timestamp": datetime.now().isoformat(),
        "razorpay_configured": config.is_configured(),
        "razorpay_mode": config.RAZORPAY_MODE if config.is_configured() else None,
    }


@app.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request) -> Response:
    """Receive and process Razorpay webhooks.

    Supported events:
        - payment.failed: trigger REVEN recovery flow
        - payment.captured: record successful payment outcome

    Returns:
        200: Webhook processed successfully
        400: Invalid signature or malformed payload
        422: Unsupported event type
        500: Internal processing error
    """
    # Step 1: Read raw body bytes (required for signature validation)
    body_bytes = await request.body()

    # Step 2: Extract headers
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

    # Step 3: Validate signature and parse payload
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

    # Step 4: Idempotency check
    if event_id:
        if event_id in _processed_events:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": "duplicate",
                    "message": f"Event {event_id} already processed",
                    "event_type": event_type,
                },
            )

        # Record this event as processed
        _processed_events.add(event_id)

        # Bound memory: remove oldest if exceeding limit
        if len(_processed_events) > _MAX_PROCESSED_EVENTS:
            _processed_events.pop()

    # Step 5: Route by event type
    if event_type == "payment.failed":
        return await handle_payment_failed(payload, event_id)

    elif event_type == "payment.captured":
        return await handle_payment_captured(payload, event_id)

    else:
        # Should not reach here due to webhook_handler validation,
        # but handle gracefully
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "unsupported_event",
                "message": f"Event type '{event_type}' is not supported",
            },
        )


async def handle_payment_failed(
    payload: dict[str, Any],
    event_id: str | None,
) -> Response:
    """Handle payment.failed webhook.

    Flow:
        1. Map Razorpay payload -> REVEN schemas
        2. Call frozen run_reven()
        3. Execute decision via gateway
        4. Audit trail
    """
    try:
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

        # Call frozen REVEN engine (engagement=None: Razorpay provides no engagement data)
        reven_result = run_reven(
            customer=customer,
            subscription=subscription,
            risk_events=risk_events,
            engagement=None,
            seed=None,  # Use non-deterministic seed for production
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

        # Save decision to decision store so payment.captured can mark it as recovered.
        # Store the Razorpay Payment Link ID (razorpay_resource_id) as the reference
        # so the payment.captured webhook can look up this decision.
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

        # Return success response
        response_data = {
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
        }

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=response_data,
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
    payload: dict[str, Any],
    event_id: str | None,
) -> Response:
    """Handle payment.captured webhook.

    IMPORTANT:
        - This marks successful payment outcome
        - Do NOT run a new recovery intervention
        - Do NOT create another Payment Link
        - Only captured payment establishes successful recovery
        - Safely handles unknown payment links (no state corruption)
    """
    try:
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        customer_id = payment_entity.get("customer_id")
        payment_id = payment_entity.get("id")
        subscription_id = payment_entity.get("subscription_id")
        amount = payment_entity.get("amount", 0) / 100.0  # Convert paise to rupees

        # The reference_id field is set when creating the Payment Link.
        # It is the decision_id for REVEN-initiated payment links.
        reference_id = payment_entity.get("reference_id")

        audit.log_webhook_received(
            event_type="payment.captured",
            customer_id=customer_id,
            payment_id=payment_id,
            subscription_id=subscription_id,
        )

        # Try to find and update the corresponding decision.
        # Look up by:
        # 1. Payment link reference_id (decision_id)
        # 2. Fall back to customer_id
        decision_id = None
        recovered = False

        if reference_id:
            # Primary lookup: by payment link reference_id (decision_id)
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
            # Fallback: find latest decision for this customer by customer_id
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

        # Log the recovery to audit trail
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


if __name__ == "__main__":
    import uvicorn

    # Development server
    uvicorn.run(
        "webhook_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
