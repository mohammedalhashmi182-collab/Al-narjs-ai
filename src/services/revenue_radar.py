"""Revenue radar: gap-sized waves, interleaved evidence, deterministic.

Builds wave payloads using observable facts only. No LLM key required. Conversion
rates and wave sizing assumptions are explicit constants so the owner can audit
and adjust them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func as sa_func, select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.models import AcquisitionLead, Payment
from src.models.crm import ACTIVE_STATUSES

from .demo_content import get_demo_label, get_package_detail
from .lead_next_action import compute_next_action
from .lead_outreach import generate_message
from .lead_segmentation import SEGMENT_LABELS_AR
from .revenue_tiers import data_flags, provenance, reference_id, score_lead, tier_counts
from .catalog import PACKAGES as _CATALOG
from .whatsapp_sender import send_status

# --- sizing assumptions (documented for owner audit) --------------------------
TARGET_SAR = settings.revenue_target_sar  # default 10 000
CURRENCY = "SAR"

# Warm: quotation or historical with recency. Cold: other active leads.
CONVERSION_WARM = 0.08
CONVERSION_COLD = 0.02

# Fallback average deal when lead pool is empty (content average).
FALLBACK_AVG_DEAL_SAR = 1200

# Wave size hard cap to avoid overwhelming the system in one run.
HARD_MAX_WAVE = 200

# Minimum daily outreach queue so the owner always has an actionable list even
# when the statistical model says fewer contacts are required to close the gap.
MIN_DAILY_WAVE = 25


@dataclass
class WaveMetrics:
    target_sar: int
    verified_sar: int
    gap_sar: int
    potential_sar: int
    potential_count: int
    today_sar: int
    required_contacts: int
    avg_deal: float
    currency: str = CURRENCY

    def to_dict(self) -> dict:
        return {
            "target_sar": self.target_sar,
            "verified_sar": self.verified_sar,
            "gap_sar": self.gap_sar,
            "potential_sar": self.potential_sar,
            "potential_count": self.potential_count,
            "today_sar": self.today_sar,
            "required_contacts": self.required_contacts,
            "avg_deal": round(self.avg_deal, 2),
            "currency": self.currency,
        }


def _package_price_sar(package: str | None) -> int:
    pkg = (package or "social").strip()
    meta = _CATALOG.get(pkg, _CATALOG["social"])
    return meta["amount"] // 100


def _interleave(lists: list[list]) -> list:
    result: list = []
    max_len = max((len(lst) for lst in lists), default=0)
    for idx in range(max_len):
        for lst in lists:
            if idx < len(lst):
                result.append(lst[idx])
    return result


async def revenue_metrics(session: AsyncSession, *, target_sar: int | None = None) -> WaveMetrics:
    target_sar = target_sar or TARGET_SAR

    lead_rows = (
        await session.execute(
            sa_select(AcquisitionLead).where(AcquisitionLead.lead_status.in_(ACTIVE_STATUSES))
        )
    ).scalars().all()

    today_sar = int(
        (
            await session.execute(
                sa_select(sa_func.coalesce(sa_func.sum(Payment.amount), 0)).where(
                    Payment.status == "paid"
                )
            )
        ).scalar_one()
        // 100
    )

    paid_total_sar = int(today_sar)

    total_sar = 0
    for lead in lead_rows:
        total_sar += _package_price_sar(getattr(lead, "suggested_package", None))
    potential_sar = total_sar
    potential_count = len(lead_rows)
    avg_deal = potential_sar / potential_count if potential_count else float(FALLBACK_AVG_DEAL_SAR)
    gap = max(0, target_sar - paid_total_sar)

    if gap <= 0:
        required = 0
    else:
        warm_count = sum(
            1
            for lead in lead_rows
            if getattr(lead, "quotation_without_purchase", None)
            or getattr(lead, "historical_customer", None)
        )
        cold_count = potential_count - warm_count
        warm_value = warm_count * avg_deal * CONVERSION_WARM
        cold_value = cold_count * avg_deal * CONVERSION_COLD
        expected = warm_value + cold_value
        required = math.ceil(gap / expected) if expected > 0 else 0

    return WaveMetrics(
        target_sar=target_sar,
        verified_sar=paid_total_sar,
        gap_sar=gap,
        potential_sar=potential_sar,
        potential_count=potential_count,
        today_sar=today_sar,
        required_contacts=min(required, HARD_MAX_WAVE),
        avg_deal=avg_deal,
    )


async def radar_payload(
    session: AsyncSession, lead: Any, metrics: WaveMetrics
) -> dict:
    pkg = getattr(lead, "suggested_package", None) or "social"
    price = _package_price_sar(pkg)
    vat = math.ceil(price * settings.vat_rate)
    total = price + vat
    phone = getattr(lead, "phone_number", None) or getattr(lead, "phone", None)
    email = getattr(lead, "email", None) or getattr(lead, "email_address", None)

    segment = getattr(lead, "segment", None) or "unknown"
    segment_label = SEGMENT_LABELS_AR.get(segment, "أعمال عامة")
    quotation = bool(getattr(lead, "quotation_without_purchase", None))
    historical = bool(getattr(lead, "historical_customer", None))
    company = getattr(lead, "company_name", None) or "شركتكم"

    if quotation:
        insight = f"{company} طلبت عرض سعر سابق ولم تُكمل الشراء — جاهزة للتحويل."
        problem = f"تحتاج {segment_label} إلى تنفيذ احترافي جاهز بدون توظيف."
    elif historical:
        insight = f"{company} عميل تاريخي — علاقة سابقة تزيد احتمال الرد."
        problem = f"يمكن استئناف تقديم {segment_label} ب đội فني احترافي جاهز."
    else:
        insight = f"{company} نشطة في {segment_label} وتحتاج فريق جاهز."
        problem = f"التوظيف المباشر مكلف؛ فريق AI جاهز بأقل من راتب موظف."

    draft = generate_message(lead, lang="ar")
    next_act = compute_next_action(lead)
    from .lead_normalize import is_whatsapp_capable
    channel = "whatsapp" if is_whatsapp_capable(phone) else ("phone" if phone else ("email" if email else "unknown"))

    lead_id = getattr(lead, "id", None)
    demo_link = f"/acquisition/leads/{lead_id}/demo" if lead_id else None
    proposal_link = f"/acquisition/leads/{lead_id}/proposal" if lead_id else None
    tier_result = score_lead(lead)

    return {
        "lead_id": str(lead_id) if lead_id else None,
        "company": company,
        "segment": segment_label,
        "reference_id": reference_id(lead),
        "tier": tier_result.tier,
        "tier_score": tier_result.score,
        "tier_reasons": tier_result.reasons,
        "insight": insight,
        "problem": problem,
        "offer": pkg,
        "offer_label": _CATALOG.get(pkg, _CATALOG["social"]),
        "price_sar": price,
        "vat": vat,
        "total_sar": total,
        "demo_link": demo_link,
        "proposal_link": proposal_link,
        "invoice_hint": f"POST /api/payments {{package: \"{pkg}\", lead_id: \"{lead_id}\"}}",
        "message_draft": draft.get("message", ""),
        "wa_link": draft.get("wa_link"),
        "wa_number": draft.get("wa_number"),
        "channel": channel,
        "next_action": next_act.get("next_action", ""),
        "next_reason": next_act.get("reason", ""),
        "status": getattr(lead, "lead_status", "NEW"),
        "value_sar": price,
        "provenance": provenance(lead),
        "flags": data_flags(lead),
        "whatsapp": {
            "buying_signal": bool(getattr(lead, "buying_signal", None)),
            "opt_out": bool(getattr(lead, "opt_out", None)),
            "last_reply_at": (
                lead.last_reply_at.isoformat() if getattr(lead, "last_reply_at", None) else None
            ),
            "intent": getattr(lead, "intent", None),
        },
    }


async def build_wave(
    session: AsyncSession,
    *,
    target_sar: int | None = None,
    verified_sar: int | None = None,
    size: int | None = None,
    include_statuses: tuple[str, ...] = ("NEW", "READY"),
) -> dict:
    metrics = await revenue_metrics(session, target_sar=target_sar)

    rows = (
        await session.execute(
            sa_select(AcquisitionLead).where(
                AcquisitionLead.lead_status.in_(include_statuses),
                AcquisitionLead.opt_out.is_(False),
            )
        )
    ).scalars().all()

    hot: list[Any] = []
    quotes: list[Any] = []
    historical: list[Any] = []
    rest: list[Any] = []
    for lead in rows:
        if _is_hot(lead):
            hot.append(lead)
        elif getattr(lead, "quotation_without_purchase", None):
            quotes.append(lead)
        elif getattr(lead, "historical_customer", None):
            historical.append(lead)
        else:
            rest.append(lead)

    hot.sort(key=lambda lead: score_lead(lead).score, reverse=True)
    quotes.sort(key=lambda lead: score_lead(lead).score, reverse=True)
    historical.sort(key=lambda lead: score_lead(lead).score, reverse=True)
    rest.sort(key=lambda lead: score_lead(lead).score, reverse=True)

    interleaved = _interleave([hot, quotes, historical, rest])
    default_size = max(metrics.required_contacts, MIN_DAILY_WAVE)
    wave_size = size if size and size > 0 else default_size
    wave_size = min(wave_size, HARD_MAX_WAVE, len(interleaved))
    wave_leads = interleaved[:wave_size]

    payloads = [await radar_payload(session, lead, metrics) for lead in wave_leads]
    counts = tier_counts([score_lead(lead) for lead in rows])

    return {
        "metrics": metrics.to_dict(),
        "wave_size": wave_size,
        "total_active": len(rows),
        "tier_counts": counts,
        "wave": payloads,
        "top_10": payloads[:10],
        "next_20": payloads[10:30],
        "whatsapp": send_status(),
    }


def _is_hot(lead: Any) -> bool:
    """A lead is hot when a WhatsApp buying signal fired or it replied recently."""
    from datetime import datetime, timedelta, timezone

    if getattr(lead, "buying_signal", None):
        return True
    reply = getattr(lead, "last_reply_at", None)
    if reply is None:
        return False
    try:
        if reply.tzinfo is None:
            reply = reply.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - reply) <= timedelta(hours=48)
    except (TypeError, ValueError):
        return False