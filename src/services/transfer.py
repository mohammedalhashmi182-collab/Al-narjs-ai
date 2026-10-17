"""Public bank-transfer details for the manual payment path.

An IBAN is not a secret — it is printed on every invoice — so it does not belong
in an environment variable. It lives in ``content/transfer.json`` and the owner
publishes or corrects it by editing that one file, with no deploy and no change
to any env-var name.

Nothing in this module invents a value. A field the owner has not filled in is
absent from the output, and the UI falls back to the one-tap contact links,
which always work.
"""

from __future__ import annotations

import json
from pathlib import Path

CONTENT_FILE = Path(__file__).resolve().parents[2] / "content" / "transfer.json"

FIELDS = ("bank_name", "account_name", "iban", "swift")


def _file_values() -> dict[str, str]:
    try:
        raw = CONTENT_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {name: str(data.get(name, "")).strip() for name in FIELDS}


def bank_details() -> dict[str, str]:
    """Only the fields the owner actually filled in."""
    return {name: value for name, value in _file_values().items() if value}


def has_bank_details() -> bool:
    return bool(bank_details().get("iban"))


def messenger_page() -> str:
    """Messenger is not a customer-contact channel."""
    return ""


def telegram_contact_handle() -> str:
    """Telegram is not published as a customer-contact handle."""
    return ""


def contact_channels(message: str = "") -> dict[str, str]:
    """Customer contact: company phone, email, and the on-site assistant.

    WhatsApp, Telegram and Messenger stay empty so templates hide those buttons.
    ``message`` is accepted for callers that used to pre-fill a chat link.
    """
    del message  # no chat deep-link is published
    from src.services.support import COMPANY_PHONE_DISPLAY, COMPANY_PHONE_E164, SUPPORT_EMAIL

    return {
        "phone": f"tel:{COMPANY_PHONE_E164}",
        "phone_display": COMPANY_PHONE_DISPLAY,
        "email": f"mailto:{SUPPORT_EMAIL}",
        "whatsapp": "",
        "telegram": "",
        "messenger": "",
    }


def contact_buttons(reference: str, amount_sar: float, customer: str | None = None) -> dict[str, str]:
    """The same links, pre-filled with the invoice reference and amount."""
    who = str(customer).strip() if customer else ""
    message = (
        f"مرحباً، أرسلت فاتورة رقم {reference} بمبلغ {amount_sar:.2f} ر.س"
        + (f" — {who}" if who else "")
        + " عبر موقع النرجس للذكاء الاصطناعي."
    )
    return contact_channels(message)
