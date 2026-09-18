"""Normalization helpers for the lead-acquisition pipeline.

Pure, side-effect-free functions so they are easy to test and reuse from both
the importer CLI and the sales API. The guiding rule is *preserve the original
data*: callers keep the raw value too, these functions only produce a canonical
form for matching and display.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any, Optional

_ARABIC_INDIC = {ord(c): str(i) for i, c in enumerate("٠١٢٣٤٥٦٧٨٩")}
_EXTENDED_ARABIC_INDIC = {ord(c): str(i) for i, c in enumerate("۰۱۲۳۴۵۶۷۸۹")}

_TASHKEEL = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
_TATWEEL = "\u0640"
_WHITESPACE = re.compile(r"\s+")
_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)

# Generic legal/business prefixes/suffixes that should not distinguish companies.
# Patterns are written in the post-unification form (ة -> ه, hamza dropped),
# because company_name_key normalizes letters before removing these words.
_COMPANY_NOISE = re.compile(
    r"\b(شركة|شركه|مؤسسة|مؤسسه|موسسه|موسسة|مكتب|مؤسسات|companies|company|co|co\.|ltd|ltd\.|llc|"
    r"est|est\.|establishment|incorporated|inc|holding|group)\b",
    re.IGNORECASE,
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def to_latin_digits(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    return text.translate(_ARABIC_INDIC).translate(_EXTENDED_ARABIC_INDIC)


def clean_text(value: Any) -> str:
    """Trim, collapse whitespace and strip control characters."""
    if value is None:
        return ""
    text = to_latin_digits(value)
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch for ch in text if ch == "\t" or ch == "\n" or unicodedata.category(ch)[0] != "C")
    text = text.replace("\u00a0", " ")
    return _WHITESPACE.sub(" ", text).strip()


def _strip_arabic_marks(text: str) -> str:
    text = _TASHKEEL.sub("", text)
    text = text.replace(_TATWEEL, "")
    return text


def _unify_arabic_letters(text: str) -> str:
    replacements = {
        "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ٲ": "ا", "ٳ": "ا",
        "ى": "ي", "ئ": "ي", "ؤ": "و", "ة": "ه", "ۀ": "ه",
    }
    return "".join(replacements.get(ch, ch) for ch in text)


def normalize_company_name(value: Any) -> str:
    """Canonical display form: cleaned but otherwise untouched."""
    return clean_text(value)


def company_name_key(value: Any) -> str:
    """Aggressive key used only for duplicate detection.

    Lower-cases, removes Arabic diacritics, unifies letter variants, drops
    punctuation and generic legal words. Never shown to users.
    """
    text = clean_text(value).lower()
    text = _strip_arabic_marks(text)
    text = _unify_arabic_letters(text)
    text = _NON_WORD.sub(" ", text)
    text = _COMPANY_NOISE.sub(" ", text)
    text = _WHITESPACE.sub(" ", text).strip()
    return text


def _digits_only(value: Any) -> str:
    return re.sub(r"\D", "", to_latin_digits(value))


def normalize_phone(value: Any, default_country: str = "966") -> Optional[str]:
    """Normalize a phone number, KSA-first, to an E.164 string.

    Conservative by design: returns ``None`` rather than guessing. A number is
    accepted only when it is a full KSA national number (9 digits starting with
    ``5`` for mobile or ``1`` for landline) or an explicit international number
    carrying its own country code (10-15 digits). Ambiguous short values such as
    a 7-digit local exchange are rejected — the importer must never invent
    digits, because outreach depends on the number being real.
    """
    digits = _digits_only(value)
    if not digits or set(digits) == {"0"}:
        return None

    if digits.startswith("00"):
        digits = digits[2:]

    # Full KSA international form: 966 + 9 national digits.
    if digits.startswith(default_country) and len(digits) == len(default_country) + 9:
        national = digits[len(default_country):]
        if national[0] in ("5", "1"):
            return f"+{default_country}{national}"
        return None

    national = digits[1:] if digits.startswith("0") else digits

    # KSA national number, with or without the trunk 0.
    if len(national) == 9 and national[0] in ("5", "1"):
        return f"+{default_country}{national}"

    # Explicit international number that carries its own country code.
    if 10 <= len(digits) <= 15 and not digits.startswith("0"):
        return f"+{digits}"

    return None


def is_valid_phone(value: Any) -> bool:
    if isinstance(value, str) and value.startswith("+"):
        digits = _digits_only(value)
        return 10 <= len(digits) <= 15 and not digits.startswith("0")
    return bool(normalize_phone(value))


_WHATSAPP_MOBILE = re.compile(r"^\+9665\d{8}$")


def is_whatsapp_capable(value: Any) -> bool:
    normalized = normalize_phone(value)
    return bool(normalized and _WHATSAPP_MOBILE.match(normalized))


def wa_me_number(value: Any) -> Optional[str]:
    """Digits suitable for https://wa.me/<number> (no plus, no leading zeros)."""
    normalized = normalize_phone(value)
    if not normalized:
        return None
    return normalized.lstrip("+")


def normalize_email(value: Any) -> Optional[str]:
    text = clean_text(value).strip().strip("<>\"'").lower()
    if not text:
        return None
    return text


def is_valid_email(value: Any) -> bool:
    text = normalize_email(value)
    return bool(text and _EMAIL_RE.match(text))


def parse_date(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    text = clean_text(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    # Excel serial date: when a workbook is read without type conversion a date
    # cell arrives as a plain number (e.g. "45292"). Convert the 1900 date
    # system (epoch 1899-12-30, with Excel's leap-year bug already accounted
    # for) only inside a plausible modern window so phone-like values are never
    # mistaken for dates.
    if re.fullmatch(r"\d{1,6}(?:\.\d+)?", text):
        serial = float(text)
        if 20000 <= serial <= 80000:
            try:
                return datetime(1899, 12, 30) + timedelta(days=serial)
            except (OverflowError, ValueError):
                return None
    return None


def parse_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    digits = re.sub(r"\D", "", to_latin_digits(value))
    if not digits:
        return default
    try:
        return int(digits)
    except ValueError:
        return default


def activity_year(value: Any) -> Optional[int]:
    parsed = parse_date(value)
    return parsed.year if parsed else None
