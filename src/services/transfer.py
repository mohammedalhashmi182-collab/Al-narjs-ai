"""Guest bank-transfer details for the manual payment path.

The account the guest pays into is read from the environment:

- ``PAYMENT_IBAN``
- ``PAYMENT_ACCOUNT_NAME``
- ``PAYMENT_BANK_NAME``
- ``PAYMENT_BANK_NAME_EN`` (optional English bank name)

The first three are required. If any of those is missing or the IBAN is not a Saudi IBAN,
``bank_details()`` is empty and the invoice hides the QR, showing a
contact-us fallback instead. Nothing here invents an account.

``content/transfer.json`` is no longer the public source. It is left on disk
so older notes still have a file to point at; the invoice does not read it.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

CONTENT_FILE = Path(__file__).resolve().parents[2] / "content" / "transfer.json"

FIELDS = ("bank_name", "account_name", "iban", "swift")

# SA + 22 digits. Spaces are stripped before the check.
_SA_IBAN = re.compile(r"^SA\d{22}$")
_RECEIPT_MAX_BYTES = 2 * 1024 * 1024


def _configured(env_name: str, attr: str) -> str:
    """Call-time value: a live env var wins, otherwise the settings object."""
    if env_name in os.environ:
        return (os.environ.get(env_name) or "").strip()
    from src.config.settings import get_settings

    return (getattr(get_settings(), attr, None) or "").strip()


def _file_values() -> dict[str, str]:
    """Legacy file. Not used for the guest invoice."""
    try:
        raw = CONTENT_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {name: str(data.get(name, "")).strip() for name in FIELDS}


def normalize_iban(raw: str) -> str:
    return re.sub(r"\s+", "", raw or "").upper()


def bank_details() -> dict[str, str]:
    """The guest account, or {} when the three required env vars are not all set.

    ``PAYMENT_BANK_NAME_EN`` is optional. When it is empty the English page
    repeats ``PAYMENT_BANK_NAME``.
    """
    iban = normalize_iban(_configured("PAYMENT_IBAN", "payment_iban"))
    name = _configured("PAYMENT_ACCOUNT_NAME", "payment_account_name")
    bank = _configured("PAYMENT_BANK_NAME", "payment_bank_name")
    bank_en = _configured("PAYMENT_BANK_NAME_EN", "payment_bank_name_en")
    if not (iban and name and bank and _SA_IBAN.fullmatch(iban)):
        return {}
    details = {"iban": iban, "account_name": name, "bank_name": bank}
    if bank_en:
        details["bank_name_en"] = bank_en
    return details


def has_bank_details() -> bool:
    return bool(bank_details().get("iban"))


def format_iban(iban: str) -> str:
    """Groups of four, left to right, so a guest can read it aloud."""
    compact = normalize_iban(iban)
    return " ".join(compact[i : i + 4] for i in range(0, len(compact), 4))


def transfer_qr_payload(
    *,
    bank: dict[str, str],
    amount_sar: str,
    reference: str,
    plan: str,
) -> str:
    """Plain text a phone camera can show. The page repeats the same fields."""
    lines = [
        "SAR transfer",
        f"Bank: {bank.get('bank_name', '')}",
    ]
    if bank.get("bank_name_en"):
        lines.append(f"Bank EN: {bank['bank_name_en']}")
    lines.extend([
        f"Name: {bank.get('account_name', '')}",
        f"IBAN: {bank.get('iban', '')}",
        f"Amount: {amount_sar} SAR",
        f"Reference: {reference}",
    ])
    if plan:
        lines.append(f"Plan: {plan}")
    return "\n".join(lines)


def transfer_qr_svg(
    *,
    bank: dict[str, str],
    amount_sar: str,
    reference: str,
    plan: str,
) -> str:
    """Inline SVG. Empty when there is no account to encode."""
    if not bank.get("iban"):
        return ""
    import segno

    code = segno.make(
        transfer_qr_payload(bank=bank, amount_sar=amount_sar, reference=reference, plan=plan),
        error="m",
    )
    return code.svg_inline(scale=4, dark="#292524", light="#ffffff", svgclass="xfer-qr-svg")


def sniff_receipt(data: bytes) -> str | None:
    """Return a safe MIME type, or None when the bytes are not a receipt we store."""
    if not data or len(data) > _RECEIPT_MAX_BYTES:
        return None
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None


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
