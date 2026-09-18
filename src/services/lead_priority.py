"""Explainable lead prioritization.

Every point is attached to a human-readable Arabic reason. There is no opaque
black-box score: the dashboard shows exactly which factors produced the priority,
and if the data does not support a high priority, the score stays low.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from src.services.lead_normalize import (
    is_valid_email,
    is_valid_phone,
    is_whatsapp_capable,
    parse_date,
)
from src.services.lead_segmentation import SEGMENT_LABELS_AR, SEGMENT_RELEVANCE

HIGH_THRESHOLD = 55
MEDIUM_THRESHOLD = 30


@dataclass
class PriorityResult:
    score: int
    priority: str
    reasons: list[str] = field(default_factory=list)


def _year_of(value: Any) -> Optional[int]:
    parsed = parse_date(value) if not isinstance(value, datetime) else value
    return parsed.year if parsed else None


def score_lead(
    *,
    company_name: str = "",
    contact_name: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    historical_customer: bool = False,
    quotation_without_purchase: bool = False,
    last_activity: Any = None,
    invoice_count: int = 0,
    segment: str = "unknown",
) -> PriorityResult:
    score = 0
    reasons: list[str] = []

    if quotation_without_purchase:
        score += 25
        reasons.append("طلب عرض سعر سابق لم يتحول إلى شراء — جاهز للمتابعة")

    if historical_customer:
        score += 15
        reasons.append("عميل سابق — علاقة تجارية قائمة")

    year = _year_of(last_activity)
    if year is not None:
        if year >= 2025:
            score += 12
            reasons.append(f"نشاط حديث ({year})")
        elif year == 2024:
            score += 9
            reasons.append("نشاط خلال 2024")
        elif year == 2023:
            score += 5
            reasons.append("نشاط خلال 2023")

    if is_valid_phone(phone):
        if is_whatsapp_capable(phone):
            score += 18
            reasons.append("رقم جوال صالح يدعم واتساب")
        else:
            score += 14
            reasons.append("رقم هاتف صالح")
    else:
        reasons.append("لا يوجد رقم جوال صالح — يلزم إيجاده قبل التواصل")

    if is_valid_email(email):
        score += 6
        reasons.append("بريد إلكتروني متاح")

    if contact_name:
        score += 4
        reasons.append("اسم مسؤول تواصل متوفر")

    if invoice_count >= 5:
        score += 6
        reasons.append(f"تاريخ شراء متكرر ({invoice_count} فواتير)")
    elif invoice_count >= 2:
        score += 3
        reasons.append(f"أكثر من فاتورة ({invoice_count})")

    relevance = SEGMENT_RELEVANCE.get(segment, 0)
    if relevance >= 8:
        score += 10
        reasons.append(f"قطاع مستهدف: {SEGMENT_LABELS_AR.get(segment, segment)}")
    elif relevance > 0:
        score += 4
        reasons.append(f"قطاع محتمل: {SEGMENT_LABELS_AR.get(segment, segment)}")

    if company_name and is_valid_phone(phone) and is_valid_email(email):
        score += 4
        reasons.append("ملف الشركة مكتمل (اسم + جوال + بريد)")

    score = max(0, min(100, score))
    if score >= HIGH_THRESHOLD:
        priority = "HIGH"
    elif score >= MEDIUM_THRESHOLD:
        priority = "MEDIUM"
    else:
        priority = "LOW"
    return PriorityResult(score=score, priority=priority, reasons=reasons)
