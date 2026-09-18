"""Transparent, evidence-weighted revenue tier scoring.

Every score is the sum of observable facts about a lead (quotation evidence,
historical recency, invoice count, reachability, existing priority, deal value,
segment relevance). Reasons are returned alongside the score so the owner can
always audit *why* a lead landed in a tier. Tier labels:

    A  -> close enough to pay today: warm signal + reachable + real deal value
    B  -> strong but needs a nudge (one touch)
    C  -> plausible, cold-ish, run in a wave
    D  -> not actionable now (no reachable channel, no evidence, or do-not-contact)

This module is deterministic and requires no LLM key.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import PurePath
from typing import Any, Optional

from src.config.settings import settings
from src.models.crm import ACTIVE_STATUSES

# Deal value in SAR/month (keep in sync with catalog.PACKAGES amount//100).
PRICE_SAR: dict[str, int] = {
    "social": 1500,
    "content": 1200,
    "ecommerce": 1000,
    "growth": 800,
}

# --- evidence weights ---------------------------------------------------------
WEIGHT_QUOTATION = 28          # a quotation was given before but not purchased
WEIGHT_HISTORICAL = 12         # bought from us in the past
WEIGHT_RECENT_2025 = 16        # last invoice in 2025
WEIGHT_RECENT_2024 = 12        # last invoice in 2024
WEIGHT_RECENT_2023 = 8         # last invoice in 2023
WEIGHT_INVOICES_5 = 8          # 5+ invoices ever
WEIGHT_INVOICES_2 = 4          # 2-4 invoices ever
WEIGHT_WHATSAPP = 22           # reachable on WhatsApp right now
WEIGHT_PHONE = 14              # reachable by phone (non-WA valid number)
WEIGHT_EMAIL = 6               # reachable by email
WEIGHT_PRIORITY_HIGH = 12      # existing segmenter priority HIGH
WEIGHT_PRIORITY_MEDIUM = 6     # existing segmenter priority MEDIUM
WEIGHT_DEAL_STEP = 250         # deal-value step used to weight price (SAR)

# Tier boundaries: score >= A goes Tier A, >= B goes Tier B, >= C goes Tier C.
TIER_A_MIN = 62
TIER_B_MIN = 40
TIER_C_MIN = 20

TIER_LABELS = {"A": "A", "B": "B", "C": "C", "D": "D"}

_PHONE_RE = re.compile(r"^[+]?[0-9]{7,15}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class TierScore:
    tier: str
    score: int
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"tier": self.tier, "score": self.score, "reasons": self.reasons}


def _field(lead_like: Any, name: str, default: Any = None) -> Any:
    """Read a field from an ORM object or a plain dict."""
    if isinstance(lead_like, Mapping):
        value = lead_like.get(name)
        return default if value is None else value
    return getattr(lead_like, name, default)


def is_valid_phone(value: Any) -> bool:
    return bool(value) and bool(_PHONE_RE.match(str(value).strip()))


def is_valid_email(value: Any) -> bool:
    return bool(value) and len(str(value)) > 5 and bool(_EMAIL_RE.match(str(value).strip()))


def is_whatsapp_capable(phone: Any) -> bool:
    """Heuristic for SA McDonald's-style WhatsApp reachability (leading 9665 / 05)."""
    p = str(phone or "").replace(" ", "").replace("-", "").replace("+", "")
    return p.startswith("9665") or p.startswith("05")


def _segment_relevance(segment: Optional[str]) -> int:
    from src.services.lead_segmentation import SEGMENT_RELEVANCE
    try:
        return int(SEGMENT_RELEVANCE.get(segment or "", SEGMENT_RELEVANCE.get("unknown", 0)))
    except (TypeError, ValueError):
        return 0


def _invoice_year(lead_like: Any) -> Optional[int]:
    raw = _field(lead_like, "last_activity") or _field(lead_like, "last_invoice_date")
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(str(raw)[:10], fmt).year
        except ValueError:
            continue
    m = re.search(r"(20\d{2})", str(raw))
    return int(m.group(1)) if m else None


def _invoice_count(lead_like: Any) -> int:
    raw = _field(lead_like, "invoice_count", 0) or 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def score_lead(lead_like: Any) -> TierScore:
    """Compute a transparent evidence-based tier for one lead(-like) object."""

    reasons: list[str] = []
    score = 0

    status = _field(lead_like, "lead_status") or _field(lead_like, "status")
    if status == "DO_NOT_CONTACT":
        return TierScore("D", 0, [status])

    quotation = bool(_field(lead_like, "quotation_without_purchase"))
    if quotation:
        score += WEIGHT_QUOTATION
        reasons.append("عرض سعر سابق دون شراء — إشارة شراء فورية")

    historical = bool(_field(lead_like, "historical_customer"))
    if historical:
        score += WEIGHT_HISTORICAL
        reasons.append("عميل تاريخي (سبق الشراء)")

    year = _invoice_year(lead_like)
    if year is not None:
        if year >= 2025:
            score += WEIGHT_RECENT_2025
            reasons.append("آخر فاتورة في عام حديث (2025)")
        elif year == 2024:
            score += WEIGHT_RECENT_2024
            reasons.append("آخر فاتورة 2024")
        elif year >= 2023:
            score += WEIGHT_RECENT_2023
            reasons.append("آخر فاتورة 2023")

    n_invoices = _invoice_count(lead_like)
    if n_invoices >= 5:
        score += WEIGHT_INVOICES_5
        reasons.append("5+ فواتير سابقة (علاقة مستمرة)")
    elif n_invoices >= 2:
        score += WEIGHT_INVOICES_2
        reasons.append("2-4 فواتير سابقة")

    phone = _field(lead_like, "phone_number") or _field(lead_like, "phone")
    email = _field(lead_like, "email") or _field(lead_like, "email_address")
    if is_whatsapp_capable(phone):
        score += WEIGHT_WHATSAPP
        reasons.append("رقم واتساب متاح للتواصل الفوري")
    elif is_valid_phone(phone):
        score += WEIGHT_PHONE
        reasons.append("رقم هاتف صالح")

    if is_valid_email(email):
        score += WEIGHT_EMAIL
        reasons.append("بريد إلكتروني متاح")
    if not (is_whatsapp_capable(phone) or is_valid_phone(phone) or is_valid_email(email)):
        reasons.append("لا قناة تواصل صالحة مسجلة")

    priority = _field(lead_like, "priority")
    if priority == "HIGH":
        score += WEIGHT_PRIORITY_HIGH
        reasons.append("أولوية عالية من المقسم")
    elif priority == "MEDIUM":
        score += WEIGHT_PRIORITY_MEDIUM
        reasons.append("أولوية متوسطة من المقسم")

    segment = _field(lead_like, "segment")
    score += min(10, _segment_relevance(segment))

    package = _field(lead_like, "suggested_package") or "social"
    deal_value = PRICE_SAR.get(package, 1200)
    score += min(8, max(1, round(deal_value / WEIGHT_DEAL_STEP)))

    score = min(100, max(0, score))

    if score >= TIER_A_MIN:
        tier = "A"
    elif score >= TIER_B_MIN:
        tier = "B"
    elif score >= TIER_C_MIN:
        tier = "C"
    else:
        tier = "D"

    return TierScore(tier=tier, score=score, reasons=reasons)


def data_flags(lead_like: Any) -> list[str]:
    """Row-level data-quality and provenance flags (never the original workbook)."""
    flags: list[str] = []
    phone = _field(lead_like, "phone_number") or _field(lead_like, "phone")
    email = _field(lead_like, "email") or _field(lead_like, "email_address")
    phone_raw = _field(lead_like, "phone_raw") or _field(lead_like, "raw_phone")

    reachable = is_whatsapp_capable(phone) or is_valid_phone(phone) or is_valid_email(email)
    if not reachable:
        flags.append("no_reachable_channel")
    if phone_raw and not is_valid_phone(phone) and not is_whatsapp_capable(phone):
        flags.append("unparsed_phone")
    name = _field(lead_like, "company_name") or _field(lead_like, "name", "")
    letters = re.sub(r"[^A-Za-z\u0600-\u06FF]", "", str(name or ""))
    if not letters or len(letters) < 3:
        flags.append("generic_or_missing_name")
    year = _invoice_year(lead_like)
    if year is None and not _invoice_count(lead_like):
        flags.append("no_activity_evidence")
    return flags


def reference_id(lead_like: Any) -> str:
    """Stable reference id: sheet + customer code crosswalk, dedup key fallback."""
    sheet = _field(lead_like, "source_sheet") or ""
    code = _field(lead_like, "source_customer_code")
    if sheet and code:
        return f"{sheet}:{code}"
    dedup = _field(lead_like, "dedup_key")
    if dedup:
        return f"dedup:{dedup}"
    ident = _field(lead_like, "id")
    return f"row:{ident}"


def provenance(lead_like: Any) -> dict:
    """Row-level provenance pointing back to the owner's workbook without paths."""
    return {
        "source": "owner_workbook",
        "source_file_basename": PurePath(settings.leads_excel_path).name,
        "source_sheet": _field(lead_like, "source_sheet"),
        "source_customer_code": _field(lead_like, "source_customer_code"),
        "dedup_key": _field(lead_like, "dedup_key"),
        "reference_id": reference_id(lead_like),
        "record_count": _field(lead_like, "record_count"),
        "raw_rows": _field(lead_like, "raw_rows"),
        "duplicate_protected": bool(_field(lead_like, "dedup_key")),
    }


def tier_counts(scores: list[TierScore]) -> dict[str, int]:
    counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for s in scores:
        counts[s.tier] = counts.get(s.tier, 0) + 1
    return counts


def is_actionable(tier: str, status: str | None = None) -> bool:
    if tier == "D":
        return False
    return status in ACTIVE_STATUSES