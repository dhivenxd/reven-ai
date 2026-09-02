"""Razorpay REST API client using stdlib only.

This module uses urllib (stdlib) to make authenticated Razorpay API calls.
No external HTTP libraries are required.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from backend.integrations.razorpay import config


def _basic_auth_header() -> str:
    """Generate HTTP Basic Auth header value for Razorpay API."""
    config.validate_for_api()
    credentials = f"{config.RAZORPAY_KEY_ID}:{config.RAZORPAY_KEY_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def verify_webhook_signature(
    payload_bytes: bytes,
    signature: str,
    secret: str,
) -> bool:
    """Verify Razorpay webhook signature using HMAC-SHA256.

    Args:
        payload_bytes: Raw webhook body bytes
        signature: X-Razorpay-Signature header value
        secret: RAZORPAY_WEBHOOK_SECRET

    Returns:
        True if signature is valid
    """
    expected = hmac.new(
        secret.encode(),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def create_payment_link(
    amount: int,
    currency: str,
    description: str,
    customer_email: str | None = None,
    customer_contact: str | None = None,
    customer_name: str | None = None,
    reference_id: str | None = None,
) -> dict[str, Any]:
    """Create a Razorpay Payment Link.

    This is the PRIMARY customer recovery mechanism for failed payments
    in Phase 2. It is NOT an automatic card retry.

    Args:
        amount: Amount in currency subunits (paise for INR)
        currency: Currency code (INR, USD, etc.)
        description: Purpose of the payment link
        customer_email: Optional customer email
        customer_contact: Optional customer phone
        customer_name: Optional customer name
        reference_id: Optional external reference

    Returns:
        Razorpay Payment Link API response dict with keys:
            id, short_url, amount, currency, description, status, etc.

    Raises:
        RuntimeError: If API credentials are missing
        HTTPError: If Razorpay API returns an error
    """
    config.validate_for_api()

    url = f"{config.BASE_URL}/payment_links"

    payload: dict[str, Any] = {
        "amount": amount,
        "currency": currency,
        "description": description,
        "accept_partial": False,
    }

    if customer_email or customer_contact or customer_name:
        payload["customer"] = {}
        if customer_email:
            payload["customer"]["email"] = customer_email
        if customer_contact:
            payload["customer"]["contact"] = customer_contact
        if customer_name:
            payload["customer"]["name"] = customer_name

    if reference_id:
        payload["reference_id"] = reference_id

    body_bytes = json.dumps(payload).encode()

    req = Request(
        url,
        data=body_bytes,
        headers={
            "Authorization": _basic_auth_header(),
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(req) as response:
            return json.loads(response.read().decode())
    except HTTPError as e:
        error_body = e.read().decode()
        raise RuntimeError(
            f"Razorpay API error: {e.code} {e.reason}\n{error_body}"
        ) from e
