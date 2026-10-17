"""Classify a tenant message as an order, a policy question, or a product lookup."""

from __future__ import annotations

import re
from typing import Optional

_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

_ORDER_PHRASES = (
    "حالة الطلب", "رقم الطلب", "وين طلبي", "أين طلبي", "اين طلبي", "وين الطلب",
    "تتبع الطلب", "تتبع الشحن", "order status", "track my order", "my order",
)
_POLICY = {
    "shipping": ("الشحن", "شحن", "التوصيل", "توصيل", "shipping", "delivery"),
    "returns": ("الاسترجاع", "استرجاع", "الارجاع", "الإرجاع", "ارجاع", "إرجاع", "الاستبدال", "استبدال", "returns", "refund"),
    "payment": ("طرق الدفع", "طريقة الدفع", "الدفع", "payment", "مدى", "تابي", "تمارا"),
}
_PRODUCT_KEYS = ("هل عندكم", "كم سعر", "التوفر", "متوفر", "المخزون", "منتج", "product", "sku")


def _fold(text: str) -> str:
    return (text or "").translate(_AR).casefold()


def extract_reference(text: str) -> Optional[str]:
    folded = (text or "").translate(_AR)
    match = re.search(r"(?:طلب|order|#)\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9_-]{3,31})", folded, re.IGNORECASE)
    if match:
        return match.group(1)
    if not any(phrase in folded.casefold() for phrase in _ORDER_PHRASES):
        return None
    digits = re.findall(r"\d{5,20}", folded)
    if digits:
        return digits[-1]
    for token in re.findall(r"\b[A-Za-z0-9]{6,20}\b", folded):
        if token.casefold() not in {"status", "order", "tracking"}:
            return token
    return None


def is_order(text: str) -> bool:
    folded = _fold(text)
    if any(phrase in folded for phrase in _ORDER_PHRASES):
        return True
    return re.search(r"(?:طلب|order)\s*[:#]?\s*[A-Za-z0-9]", text or "", re.IGNORECASE) is not None


def policy_topics(text: str) -> tuple[str, ...]:
    folded = _fold(text)
    return tuple(topic for topic, words in _POLICY.items() if any(word in folded for word in words))


def product_query(text: str) -> Optional[str]:
    raw = (text or "").strip()
    folded = _fold(raw)
    if not any(key in folded for key in _PRODUCT_KEYS):
        return None
    cleaned = raw.translate(_AR)
    for key in _PRODUCT_KEYS:
        cleaned = re.sub(re.escape(key), " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ؟?،,.")
    if len(cleaned) < 2:
        return None
    return cleaned[:80]


def classify(text: str) -> Optional[tuple]:
    """Return ('order', reference|None) | ('policy', topics) | ('product', query) | None."""
    if is_order(text):
        return ("order", extract_reference(text))
    topics = policy_topics(text)
    if topics:
        return ("policy", topics)
    query = product_query(text)
    if query:
        return ("product", query)
    return None
