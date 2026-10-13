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
from urllib.parse import quote

from src.config.settings import get_settings

CONTENT_FILE = Path(__file__).resolve().parents[2] / "content" / "transfer.json"

FIELDS = ("bank_name", "account_name", "iban", "swift")

TELEGRAM_BOT = "https://t.me/AlNarjs7BOT"


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


def _whatsapp_e164() -> str:
    from src.services.lead_normalize import normalize_mobile_e164

    return normalize_mobile_e164(get_settings().whatsapp_business_number) or ""


CONTACT_FILE = Path(__file__).resolve().parents[2] / "content" / "contact.json"


def _contact_file() -> dict[str, str]:
    try:
        data = json.loads(CONTACT_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def messenger_page() -> str:
    """Facebook Page username for m.me links; empty until the owner sets it."""
    raw = str(_contact_file().get("messenger_page", "")).strip().lstrip("@")
    return raw if raw and all(c.isalnum() or c in "._-" for c in raw) else ""


def telegram_contact_handle() -> str:
    """The person/channel handle published as the Telegram contact.

    Distinct from TELEGRAM_BOT (the production bot that plan deep links use).
    """
    raw = str(_contact_file().get("telegram_handle", "")).strip().lstrip("@")
    return raw if raw and all(c.isalnum() or c == "_" for c in raw) else TELEGRAM_BOT.rsplit("/", 1)[-1]


def contact_channels(message: str = "") -> dict[str, str]:
    """One-tap links a buyer can use instead of guessing how to reach us.

    A channel the owner has not configured is an empty string, so the UI can
    hide it instead of rendering a dead button.
    """
    number = _whatsapp_e164()
    whatsapp = f"https://wa.me/{number}" if number else ""
    if whatsapp and message:
        whatsapp = f"{whatsapp}?text={quote(message)}"
    page = messenger_page()
    messenger = f"https://m.me/{page}" if page else ""
    return {"whatsapp": whatsapp, "telegram": TELEGRAM_BOT, "messenger": messenger}


def contact_buttons(reference: str, amount_sar: float, customer: str | None = None) -> dict[str, str]:
    """The same links, pre-filled with the invoice reference and amount."""
    who = str(customer).strip() if customer else ""
    message = (
        f"مرحباً، أرسلت فاتورة رقم {reference} بمبلغ {amount_sar:.2f} ر.س"
        + (f" — {who}" if who else "")
        + " عبر موقع النرجس للذكاء الاصطناعي."
    )
    return contact_channels(message)
