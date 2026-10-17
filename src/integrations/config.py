"""Environment for the store integration. Read here, never from settings.py.

Documented names live in ``.env.example``. Values are never logged.
"""

from __future__ import annotations

import os

# Read-only Salla scopes. offline_access is required for a refresh token.
# https://docs.salla.dev/authorization
SALLA_SCOPES = "offline_access orders.read products.read settings.read"

# Zid scopes are chosen in the Partner Dashboard, not on the authorize URL.
# Required there: orders.read, products.read, third_store_details_read.
# https://docs.zid.sa/authorization

# Basic-auth username Zid sends when the webhook is created with this user.
# The password is ZID_WEBHOOK_SECRET. Not a credential by itself.
ZID_WEBHOOK_USER = "narjis"

_ON = {"1", "true", "on", "yes"}


def enabled() -> bool:
    """Default off. The marketing copy stays «قريباً» until the owner sets this."""
    return (os.getenv("STORE_INTEGRATIONS_ENABLED") or "").strip().lower() in _ON


def env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def salla_oauth_ready() -> bool:
    return bool(env("SALLA_CLIENT_ID") and env("SALLA_CLIENT_SECRET") and env("SALLA_REDIRECT_URI"))


def zid_oauth_ready() -> bool:
    return bool(env("ZID_CLIENT_ID") and env("ZID_CLIENT_SECRET") and env("ZID_REDIRECT_URI"))
