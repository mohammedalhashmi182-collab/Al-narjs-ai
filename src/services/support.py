"""Customer-service handoff for the site assistant.

The only phone is the Al-Narjis company number. The assistant and email stay
available; WhatsApp, Telegram and Messenger are not customer-contact channels.
"""

from __future__ import annotations

SUPPORT_EMAIL = "AlNarjisai@gmail.com"
COMPANY_PHONE_E164 = "+966540799266"
COMPANY_PHONE_DISPLAY = "0540799266"


def support_contact() -> dict:
    return {
        "channel": "call",
        "href": f"tel:{COMPANY_PHONE_E164}",
        "value": COMPANY_PHONE_DISPLAY,
        "e164": COMPANY_PHONE_E164,
        "email": SUPPORT_EMAIL,
    }
