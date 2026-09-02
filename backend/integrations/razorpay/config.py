"""Razorpay integration configuration.

Reads credentials from environment variables ONLY. No credentials are
hardcoded, printed, or committed.

Environment variables:
    RAZORPAY_KEY_ID        - Razorpay API key id (sandbox or production)
    RAZORPAY_KEY_SECRET    - Razorpay API key secret
    RAZORPAY_WEBHOOK_SECRET - Webhook signing secret
    RAZORPAY_MODE          - "sandbox" (default) or "production"

Loads from .env file at repository root if present. Requires python-dotenv.
Shell environment variables take precedence over .env values.
"""

from __future__ import annotations

import os
from pathlib import Path

# Load .env file from repository root if present
try:
    from dotenv import load_dotenv

    # Find repository root (3 levels up from this file)
    repo_root = Path(__file__).parents[3]
    env_file = repo_root / ".env"

    if env_file.exists():
        # override=False ensures shell env vars take precedence
        load_dotenv(env_file, override=False)
except ImportError:
    # python-dotenv not installed - continue without .env loading
    pass

# ------------------------------------------------------------------
# Credential loading
# ------------------------------------------------------------------

RAZORPAY_KEY_ID: str | None = os.environ.get("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET: str | None = os.environ.get("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET: str | None = os.environ.get(
    "RAZORPAY_WEBHOOK_SECRET"
)

RAZORPAY_MODE: str = (
    os.environ.get("RAZORPAY_MODE", "sandbox").strip().lower()
)

# Base URLs per mode. Sandbox is the default and only mode implemented
# for Phase 2.
SANDBOX_BASE_URL = "https://api.razorpay.com/v1"
PRODUCTION_BASE_URL = "https://api.razorpay.com/v1"

BASE_URL = (
    SANDBOX_BASE_URL
    if RAZORPAY_MODE == "sandbox"
    else PRODUCTION_BASE_URL
)

# Razorpay API version used by the REST endpoints.
API_VERSION = "v1"


def is_configured() -> bool:
    """Return True only when API credentials are present."""
    return bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)


def is_sandbox() -> bool:
    """Return True when running against Razorpay Sandbox."""
    return RAZORPAY_MODE == "sandbox"


def is_production() -> bool:
    """Return True when running against Razorpay Production."""
    return RAZORPAY_MODE == "production"


def masked_key_id() -> str:
    """Return a safe, never-secret representation for logs."""
    if not RAZORPAY_KEY_ID:
        return "<not set>"
    return RAZORPAY_KEY_ID[:6] + "***"


def validate_for_api() -> None:
    """Raise if credentials are missing for an API call."""
    if not is_configured():
        raise RuntimeError(
            "Razorpay API credentials are not configured. "
            "Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET."
        )


def validate_for_webhook() -> None:
    """Raise if the webhook signing secret is missing."""
    if not RAZORPAY_WEBHOOK_SECRET:
        raise RuntimeError(
            "RAZORPAY_WEBHOOK_SECRET is not configured. "
            "Webhook signature validation is impossible without it."
        )