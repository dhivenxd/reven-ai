"""Razorpay webhook and API response schemas.

These dataclasses represent Razorpay's webhook payload structure
and API responses, not REVEN's internal schemas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class RazorpayCustomer:
    """Razorpay customer entity from webhook/API."""
    id: str
    email: str | None = None
    contact: str | None = None
    name: str | None = None


@dataclass
class RazorpaySubscription:
    """Razorpay subscription entity from webhook."""
    id: str
    customer_id: str
    plan_id: str
    status: str
    current_start: int | None = None
    current_end: int | None = None
    charge_at: int | None = None
    start_at: int | None = None
    end_at: int | None = None
    quantity: int = 1
    total_count: int = 0
    paid_count: int = 0
    remaining_count: int = 0


@dataclass
class RazorpayPayment:
    """Razorpay payment entity from webhook."""
    id: str
    entity: str
    amount: int
    currency: str
    status: str
    order_id: str | None = None
    invoice_id: str | None = None
    method: str | None = None
    description: str | None = None
    email: str | None = None
    contact: str | None = None
    customer_id: str | None = None
    error_code: str | None = None
    error_description: str | None = None
    error_source: str | None = None
    error_step: str | None = None
    error_reason: str | None = None
    created_at: int | None = None


@dataclass
class RazorpayWebhookEvent:
    """Razorpay webhook envelope."""
    event: str
    payload: dict
    created_at: int


@dataclass
class PaymentLinkResponse:
    """Response from Razorpay Payment Link creation API."""
    id: str
    short_url: str
    amount: int
    currency: str
    description: str
    customer: dict | None = None
    status: str = "created"
    created_at: int | None = None
