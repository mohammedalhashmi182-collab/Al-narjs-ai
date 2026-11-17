"""Reply classification. The stored evidence is the provider Message-ID, not the body."""

from __future__ import annotations

import re

_OPT_OUT = (
    "unsubscribe",
    "opt out",
    "opt-out",
    "stop emailing",
    "do not contact",
    "لا تراسل",
    "لا تراسلون",
    "اوقفوا",
    "أوقفوا",
    "الغاء الاشتراك",
    "إلغاء الاشتراك",
    "الغاء الرسائل",
    "إلغاء الرسائل",
    "لا أرغب",
    "لا ارغب",
)
_NOT_NOW = (
    "not now",
    "later",
    "not interested now",
    "ليس الآن",
    "ليس الان",
    "لاحقاً",
    "لاحقا",
    "بعدين",
    "في وقت لاحق",
)
_INTERESTED = (
    "interested",
    "send the proposal",
    "send proposal",
    "مهتم",
    "أرسل العرض",
    "ارسل العرض",
    "أبغى العرض",
    "ابغى العرض",
    "أبغى الباقة",
    "ابغى الباقة",
    "نرغب بالمتابعة",
)


def _norm(text: str) -> str:
    value = (text or "").strip().lower()
    value = value.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    value = value.replace("ة", "ه").replace("ى", "ي")
    value = re.sub(r"\s+", " ", value)
    return value


def classify_reply(text: str) -> str:
    """Return interested, not_now, opt_out, or unknown. Opt-out wins."""
    folded = _norm(text)
    if not folded:
        return "unknown"
    if any(_norm(phrase) in folded for phrase in _OPT_OUT):
        return "opt_out"
    if any(_norm(phrase) in folded for phrase in _NOT_NOW):
        return "not_now"
    if any(_norm(phrase) in folded for phrase in _INTERESTED):
        return "interested"
    return "unknown"
