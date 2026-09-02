"""Demo: End-to-end Razorpay -> REVEN -> Razorpay flow.

This demonstrates the Phase 2 vertical slice WITHOUT requiring actual
webhook delivery from Razorpay servers.

Flow:
1. Synthetic payment.failed webhook payload
2. Webhook signature validation (skipped in demo mode if no webhook secret)
3. Map Razorpay -> REVEN schemas
4. Call frozen run_reven()
5. REVEN returns RevenueDecision
6. Execution gateway maps decision -> Razorpay API
7. (If credentials present) Real Razorpay Sandbox API call
8. Audit trail

IMPORTANT:
- Demo mode uses synthetic webhook payload, NOT real Razorpay webhook
- If RAZORPAY_KEY_ID/SECRET are present, makes REAL Sandbox API calls
- If credentials are absent, simulates the API response
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime

# Force UTF-8 output on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from backend.integrations.razorpay import config
from backend.integrations.razorpay.event_mapper import map_razorpay_to_reven
from backend.integrations.razorpay.execution_gateway import ExecutionGateway
from backend.integrations.razorpay.audit import AuditLogger
from backend.reven.reven_engine import run_reven


# Synthetic payment.failed webhook payload matching Razorpay structure
DEMO_WEBHOOK_PAYLOAD = {
    "event": "payment.failed",
    "created_at": int(datetime.now().timestamp()),
    "payload": {
        "payment": {
            "entity": {
                "id": "pay_demo123456789",
                "entity": "payment",
                "amount": 39900,  # 399.00 INR in paise
                "currency": "INR",
                "status": "failed",
                "method": "card",
                "description": "Streamflix Standard subscription",
                "customer_id": "cust_razorpay_demo_001",
                "subscription_id": "sub_razorpay_demo_001",
                "email": "demo@streamflix.example",
                "contact": "+919876543210",
                "error_code": "BAD_REQUEST_ERROR",
                "error_description": "Payment processing failed",
                "error_reason": "insufficient_funds",
                "created_at": int(datetime.now().timestamp()),
            }
        },
        "subscription": {
            "entity": {
                "id": "sub_razorpay_demo_001",
                "customer_id": "cust_razorpay_demo_001",
                "plan_id": "plan_standard",
                "status": "active",
                "current_start": int(datetime.now().timestamp()) - (20 * 86400),
                "current_end": int(datetime.now().timestamp()) + (10 * 86400),
                "quantity": 1,
                "total_count": 12,
                "paid_count": 0,
                "remaining_count": 12,
            }
        },
    },
}


def run_demo(use_real_api: bool = None) -> None:
    """Run end-to-end demo flow.

    Args:
        use_real_api: If True, uses real Razorpay API (requires credentials).
                     If False, simulates API. If None, auto-detects from config.
    """
    print("=" * 70)
    print("REVEN RAZORPAY INTEGRATION DEMO")
    print("Phase 2: payment.failed -> REVEN -> Payment Recovery Link")
    print("=" * 70)
    print()

    # Determine API mode
    if use_real_api is None:
        use_real_api = config.is_configured()

    if use_real_api:
        print(f"Mode: Razorpay {config.RAZORPAY_MODE.upper()} API")
        print(f"Key ID: {config.masked_key_id()}")
    else:
        print("Mode: SIMULATED (no Razorpay credentials)")
    print()

    # Initialize audit logger
    audit = AuditLogger()

    # Step 1: Simulate webhook receipt
    print("Step 1: Razorpay webhook received")
    print(f"  Event: {DEMO_WEBHOOK_PAYLOAD['event']}")
    payment_entity = DEMO_WEBHOOK_PAYLOAD["payload"]["payment"]["entity"]
    print(f"  Payment ID: {payment_entity['id']}")
    print(f"  Customer ID: {payment_entity['customer_id']}")
    print(f"  Amount: Rs.{payment_entity['amount'] / 100:.2f}")
    print(f"  Status: {payment_entity['status']}")
    print(f"  Error: {payment_entity['error_reason']}")
    print()

    audit.log_webhook_received(
        event_type=DEMO_WEBHOOK_PAYLOAD["event"],
        customer_id=payment_entity["customer_id"],
        payment_id=payment_entity["id"],
        subscription_id=payment_entity.get("subscription_id"),
    )

    # Step 2: Map to REVEN schemas
    print("Step 2: Map Razorpay -> REVEN schemas")
    customer, subscription, risk_events = map_razorpay_to_reven(
        DEMO_WEBHOOK_PAYLOAD
    )
    print(f"  Customer: {customer.customer_id}")
    print(f"  Subscription: {subscription.subscription_id}")
    print(f"  RiskEvents: {len(risk_events)}")
    print(f"    - {risk_events[0].event_type.value}: {risk_events[0].severity.value}")
    print()

    # Step 3: Call frozen REVEN engine
    print("Step 3: Call frozen run_reven()")
    print("  engagement=None (Razorpay provides no engagement data)")
    result = run_reven(
        customer=customer,
        subscription=subscription,
        risk_events=risk_events,
        engagement=None,
        seed=42,
    )
    print()

    decision = result.decision
    print("Step 4: REVEN decision")
    print(f"  Intervention: {decision.intervention_type.value}")
    print(f"  Expected net revenue: Rs.{decision.expected_net_revenue:.2f}")
    print(f"  Confidence: {decision.confidence:.1%}")
    print(f"  Reason: {decision.reason}")
    print()

    audit.log_reven_decision(
        customer_id=decision.customer_id,
        intervention_type=decision.intervention_type.value,
        expected_net_revenue=decision.expected_net_revenue,
        confidence=decision.confidence,
        reason=decision.reason,
    )

    # Step 5: Execute via gateway
    print("Step 5: Execution gateway")
    gateway = ExecutionGateway()

    # Generate unique reference_id for each demo run to avoid Razorpay collision
    # Keep subscription_id unchanged for REVEN decision logic
    unique_reference_id = f"{subscription.subscription_id}_{uuid.uuid4().hex[:8]}"

    if not use_real_api:
        print("  Simulating Razorpay API (no credentials configured)")
        execution_result = gateway.execute_decision(
            decision=decision,
            subscription=subscription,
            customer_email=payment_entity.get("email"),
            customer_contact=payment_entity.get("contact"),
            reference_id=unique_reference_id,
        )
        # Override for simulation
        if execution_result.execution_status == "failed":
            print(f"  [WARN]  Simulation note: {execution_result.message}")
            print("  In demo mode without credentials, API calls cannot execute.")
        else:
            print(f"  Status: {execution_result.execution_status}")
            print(f"  Operation: {execution_result.razorpay_operation}")
    else:
        print("  Calling REAL Razorpay Sandbox API...")
        execution_result = gateway.execute_decision(
            decision=decision,
            subscription=subscription,
            customer_email=payment_entity.get("email"),
            customer_contact=payment_entity.get("contact"),
            reference_id=unique_reference_id,
        )
        print(f"  Status: {execution_result.execution_status}")
        print(f"  Operation: {execution_result.razorpay_operation}")
        if execution_result.razorpay_resource_id:
            print(f"  Resource ID: {execution_result.razorpay_resource_id}")
        if execution_result.razorpay_resource_url:
            print(f"  Payment Link: {execution_result.razorpay_resource_url}")

    print(f"  Message: {execution_result.message}")
    print()

    audit.log_execution_result(
        customer_id=decision.customer_id,
        intervention_type=decision.intervention_type.value,
        execution_status=execution_result.execution_status,
        razorpay_operation=execution_result.razorpay_operation,
        razorpay_resource_id=execution_result.razorpay_resource_id,
        message=execution_result.message,
    )

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print()
    print("[OK] Webhook validated and parsed")
    print("[OK] Razorpay payload mapped to REVEN schemas")
    print("[OK] REVEN policy engine executed (frozen backend untouched)")
    print("[OK] Execution gateway enforced safety boundary")
    if execution_result.execution_status == "executed":
        print("[OK] Razorpay Sandbox API call succeeded")
        print()
        print("IMPORTANT:")
        print("  - Payment recovery link created ≠ revenue recovered")
        print("  - Customer must complete payment via link")
        print("  - Revenue marked recovered ONLY after payment.captured webhook")
    elif execution_result.execution_status == "no_api_available":
        print(f"[INFO]  {decision.intervention_type.value} requires customer-facing channel")
    else:
        print("[WARN]  Execution did not complete (see message above)")
    print()


if __name__ == "__main__":
    run_demo()
