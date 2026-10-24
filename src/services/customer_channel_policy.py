"""Launch policy for Al-Narjis customer communication.

The public customer journey is intentionally site-assistant-only:
- sales, replies and inbound customer conversations happen in the on-site assistant;
- email is delivery/authentication only (OTP, invoices, agent results), not a public sales channel;
- WhatsApp, Telegram and Messenger customer messaging stay disabled even when
  credentials remain present in Render for future owner-approved reactivation.

Internal owner alerts are not customer communication and may continue to use
their existing private channel.
"""
from __future__ import annotations

SITE_ASSISTANT_CHANNEL = "site_assistant"
EXTERNAL_CUSTOMER_CHANNELS = frozenset({"whatsapp", "telegram", "messenger"})
CUSTOMER_CHANNEL_POLICY = "site_assistant_only"


def external_customer_channel_enabled(channel: str) -> bool:
    """Fail closed for every external customer messaging channel."""
    return False if channel in EXTERNAL_CUSTOMER_CHANNELS else channel == SITE_ASSISTANT_CHANNEL


def disabled_reason(channel: str) -> str:
    return f"{channel} customer messaging disabled by {CUSTOMER_CHANNEL_POLICY} launch policy"
