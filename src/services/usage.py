"""Usage metering per subscription (client project).

Monthly counters for smart conversations, voice minutes and Meta fees, reset
by billing period: every subscription has monthly usage windows anchored on
its ``current_period_end`` day (annual plans also reset monthly). Projects
without a period end use the calendar month (UTC).

Rules:
- A conversation is one customer contact in a 24h window on one project, any
  number of messages (``catalog.PACKAGES[..]["limits"]`` wording).
- Meta fees are recorded once per provider message id.
- At 80% and 100% of any limit the owner is alerted once per window
  (Telegram War Room via ``telegram_sender.send_owner_alert``).
- Over the limit service is NEVER cut: the window is flagged ``over_limit``
  and the excess is recorded as overage for add-on billing.

All public ``record_*`` functions are best-effort for the caller: they flush
but do not commit, so the caller's transaction decides.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.services import catalog

logger = logging.getLogger(__name__)

CONVERSATION_WINDOW = timedelta(hours=24)
METRICS = ("conversations", "voice_minutes", "meta_fees")


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _add_months(dt: datetime, months: int) -> datetime:
    from src.services.payments import add_months

    return add_months(dt, months)


def usage_window(project, now: Optional[datetime] = None) -> tuple[datetime, datetime]:
    """[start, end) of the monthly usage window that contains ``now``."""
    now = _utc(now) or datetime.now(timezone.utc)
    anchor = _utc(getattr(project, "current_period_end", None))
    if anchor is None:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, _add_months(start, 1)
    # Step from the anchor by whole months (from the anchor itself, so month-end
    # clamping never drifts) until the window contains now.
    k = (anchor.year - now.year) * 12 + (anchor.month - now.month) + 1
    for _ in range(40):
        end = _add_months(anchor, -k + 1)
        start = _add_months(anchor, -k)
        if start <= now < end:
            return start, end
        k += 1 if now < start else -1
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, _add_months(start, 1)


def project_limits(project) -> dict:
    return catalog.plan_limits(
        project.package,
        int(getattr(project, "addon_conversation_packs", 0) or 0),
        int(getattr(project, "addon_voice_packs", 0) or 0),
    )


async def current_usage(session: AsyncSession, project, now: Optional[datetime] = None):
    """The project's counter row for the current window (created on demand)."""
    from src.models.usage import SubscriptionUsage

    start, end = usage_window(project, now)
    row = (await session.execute(
        select(SubscriptionUsage).where(
            SubscriptionUsage.project_id == project.id,
            SubscriptionUsage.period_start == start,
        )
    )).scalar_one_or_none()
    limits = project_limits(project)
    if row is None:
        row = SubscriptionUsage(
            project_id=project.id, period_start=start, period_end=end,
            conversations=0, voice_seconds=0, meta_fees=0,
            over_limit=False, overage_conversations=0, overage_voice_minutes=0, overage_meta_fees=0,
            alerts_sent=[],
        )
        session.add(row)
    # Limits follow the plan and packs bought during the window.
    row.limit_conversations = int(limits["conversations"])
    row.limit_voice_minutes = int(limits["voice_minutes"])
    row.limit_meta_cap = int(limits["meta_cap"])
    _recompute(row)
    await session.flush()
    return row


def _voice_minutes(row) -> int:
    # Minutes are billed rounded up.
    return -(-int(row.voice_seconds or 0) // 60)


def _used_and_limit(row) -> dict:
    return {
        "conversations": (int(row.conversations or 0), int(row.limit_conversations or 0)),
        "voice_minutes": (_voice_minutes(row), int(row.limit_voice_minutes or 0)),
        "meta_fees": (int(row.meta_fees or 0), int(row.limit_meta_cap or 0)),
    }


def _recompute(row) -> None:
    ul = _used_and_limit(row)
    row.overage_conversations = max(0, ul["conversations"][0] - ul["conversations"][1])
    row.overage_voice_minutes = max(0, ul["voice_minutes"][0] - ul["voice_minutes"][1])
    row.overage_meta_fees = max(0, ul["meta_fees"][0] - ul["meta_fees"][1])
    row.over_limit = bool(row.overage_conversations or row.overage_voice_minutes or row.overage_meta_fees)


def pending_alerts(row) -> list[tuple[str, int, int, int]]:
    """(metric, threshold, used, limit) crossings not alerted yet this window."""
    sent = set(row.alerts_sent or [])
    out = []
    for metric, (used, limit) in _used_and_limit(row).items():
        if used <= 0:
            continue
        for threshold in catalog.USAGE_ALERT_THRESHOLDS:
            key = f"{metric}:{threshold}"
            # A zero allowance (e.g. no voice on ردّ) is crossed by any use.
            crossed = used * 100 >= threshold * limit if limit > 0 else True
            if crossed and key not in sent:
                out.append((metric, threshold, used, limit))
    return out


_METRIC_AR = {"conversations": "المحادثات", "voice_minutes": "دقائق الصوت", "meta_fees": "رسوم ميتا"}


def alert_text(project, metric: str, threshold: int, used: int, limit: int) -> str:
    fmt = (lambda v: f"{v / 100:,.2f} ر.س") if metric == "meta_fees" else (lambda v: f"{v:,}")
    head = "تجاوز الحد" if threshold >= 100 else f"وصل {threshold}٪"
    tail = (" — الخدمة مستمرة، والزيادة مسجّلة للفوترة كإضافة." if threshold >= 100 else "")
    return (
        f"⚠️ استهلاك العميل {project.client_name} ({project.package}): {head} في {_METRIC_AR[metric]} "
        f"{fmt(used)} من {fmt(limit)}{tail}"
    )


async def _notify(project, row, alerts) -> list[str]:
    if not alerts:
        return []
    sent = list(row.alerts_sent or [])
    keys = []
    for metric, threshold, used, limit in alerts:
        key = f"{metric}:{threshold}"
        sent.append(key)
        keys.append(key)
        try:
            from src.services import telegram_sender

            await telegram_sender.send_owner_alert(alert_text(project, metric, threshold, used, limit))
        except Exception:  # alerts are best-effort; metering never fails on them
            logger.warning("usage alert delivery failed for project %s", project.id)
    row.alerts_sent = sent  # reassign so JSON change is persisted
    return keys


async def _apply(session: AsyncSession, project, now, *, conversations=0, voice_seconds=0, meta_fees=0) -> dict:
    row = await current_usage(session, project, now)
    row.conversations = int(row.conversations or 0) + int(conversations)
    row.voice_seconds = int(row.voice_seconds or 0) + int(voice_seconds)
    row.meta_fees = int(row.meta_fees or 0) + int(meta_fees)
    _recompute(row)
    alerted = await _notify(project, row, pending_alerts(row))
    await session.flush()
    return {"counted": True, "usage_id": str(row.id), "over_limit": row.over_limit, "alerts": alerted}


async def _project(session: AsyncSession, project_or_id):
    from src.models import ClientProject

    if isinstance(project_or_id, ClientProject):
        return project_or_id
    try:
        pid = project_or_id if isinstance(project_or_id, UUID) else UUID(str(project_or_id))
    except (TypeError, ValueError):
        return None
    return (await session.execute(select(ClientProject).where(ClientProject.id == pid))).scalar_one_or_none()


async def project_for_whatsapp_number(session: AsyncSession, phone_number_id) -> Optional[object]:
    """The subscription whose own WhatsApp number (Meta phone_number_id) this is."""
    from src.models import ClientProject

    pnid = str(phone_number_id or "").strip()
    if not pnid:
        return None
    return (await session.execute(
        select(ClientProject).where(ClientProject.wa_phone_number_id == pnid).limit(1)
    )).scalar_one_or_none()


async def record_conversation(session: AsyncSession, project_or_id, contact: str, channel: str = "whatsapp",
                              *, now: Optional[datetime] = None, ref: Optional[str] = None) -> dict:
    """Count a smart conversation unless this contact already opened one in the last 24h."""
    from src.models.usage import UsageEvent

    project = await _project(session, project_or_id)
    if project is None:
        return {"counted": False, "reason": "no project"}
    now = _utc(now) or datetime.now(timezone.utc)
    key = str(contact or "").strip()[:128]
    if not key:
        return {"counted": False, "reason": "no contact"}
    recent = (await session.execute(
        select(UsageEvent.occurred_at).where(
            UsageEvent.project_id == project.id,
            UsageEvent.kind == "conversation",
            UsageEvent.contact_key == key,
        ).order_by(UsageEvent.occurred_at.desc()).limit(1)
    )).scalar_one_or_none()
    if recent is not None and now - _utc(recent) < CONVERSATION_WINDOW:
        return {"counted": False, "reason": "open conversation"}
    session.add(UsageEvent(project_id=project.id, kind="conversation", channel=(channel or "")[:20],
                           contact_key=key, ref=(ref or None) and str(ref)[:255], quantity=1, occurred_at=now))
    return await _apply(session, project, now, conversations=1)


async def record_voice(session: AsyncSession, project_or_id, seconds: int, *, contact: Optional[str] = None,
                       ref: Optional[str] = None, now: Optional[datetime] = None) -> dict:
    """Add voice-agent call time (seconds). A ``ref`` (call id) is counted once."""
    from src.models.usage import UsageEvent

    project = await _project(session, project_or_id)
    if project is None:
        return {"counted": False, "reason": "no project"}
    seconds = max(0, int(seconds or 0))
    if not seconds:
        return {"counted": False, "reason": "zero duration"}
    now = _utc(now) or datetime.now(timezone.utc)
    if ref and await _seen(session, project.id, "voice", ref):
        return {"counted": False, "reason": "duplicate"}
    session.add(UsageEvent(project_id=project.id, kind="voice", channel="voice", contact_key=(contact or None),
                           ref=(ref or None) and str(ref)[:255], quantity=seconds, occurred_at=now))
    return await _apply(session, project, now, voice_seconds=seconds)


async def record_meta_fee(session: AsyncSession, project_or_id, halalas: int, *, ref: Optional[str] = None,
                          category: Optional[str] = None, now: Optional[datetime] = None) -> dict:
    """Add a Meta conversation/message fee (halalas). A ``ref`` (message id) is counted once."""
    from src.models.usage import UsageEvent

    project = await _project(session, project_or_id)
    if project is None:
        return {"counted": False, "reason": "no project"}
    halalas = max(0, int(halalas or 0))
    if not halalas:
        return {"counted": False, "reason": "free"}
    now = _utc(now) or datetime.now(timezone.utc)
    if ref and await _seen(session, project.id, "meta_fee", ref):
        return {"counted": False, "reason": "duplicate"}
    session.add(UsageEvent(project_id=project.id, kind="meta_fee", channel="whatsapp",
                           ref=(ref or None) and str(ref)[:255], quantity=halalas,
                           meta={"category": category} if category else None, occurred_at=now))
    return await _apply(session, project, now, meta_fees=halalas)


def meta_fee_for_status(status_row: dict) -> tuple[int, Optional[str]]:
    """Fee (halalas) and category for a WhatsApp status webhook row; 0 if not billable."""
    pricing = status_row.get("pricing") or {}
    if not isinstance(pricing, dict) or not pricing.get("billable"):
        return 0, None
    category = str(pricing.get("category") or "").lower() or None
    return int(catalog.META_FEE_RATES.get(category or "", 0)), category


async def _seen(session: AsyncSession, project_id, kind: str, ref: str) -> bool:
    from src.models.usage import UsageEvent

    return (await session.execute(
        select(UsageEvent.id).where(
            UsageEvent.project_id == project_id, UsageEvent.kind == kind, UsageEvent.ref == str(ref)[:255]
        ).limit(1)
    )).scalar_one_or_none() is not None


def suggested_packs(row) -> dict:
    """Add-on packs that would cover this window's overage (for billing)."""
    conv_units = catalog.USAGE_ADDONS["conversations"]["units"]
    voice_units = catalog.USAGE_ADDONS["voice_minutes"]["units"]
    conv = -(-int(row.overage_conversations or 0) // conv_units)
    voice = -(-int(row.overage_voice_minutes or 0) // voice_units)
    return {
        "conversation_packs": conv,
        "voice_packs": voice,
        "packs_amount": catalog.usage_packs_amount(conv, voice),
        "meta_at_cost": int(row.overage_meta_fees or 0),
        "total_due": catalog.usage_packs_amount(conv, voice) + int(row.overage_meta_fees or 0),
    }


def usage_summary(project, row) -> dict:
    ul = _used_and_limit(row)

    def pct(used, limit):
        return round(used * 100 / limit, 1) if limit > 0 else (100.0 if used else 0.0)

    return {
        "project_id": str(project.id),
        "client_name": project.client_name,
        "package": project.package,
        "status": project.status,
        "founding": bool(getattr(project, "founding", False)),
        "period_start": _utc(row.period_start).isoformat(),
        "period_end": _utc(row.period_end).isoformat(),
        "metrics": {
            m: {"used": u, "limit": lim, "pct": pct(u, lim)} for m, (u, lim) in ul.items()
        },
        "over_limit": bool(row.over_limit),
        "overage": {
            "conversations": int(row.overage_conversations or 0),
            "voice_minutes": int(row.overage_voice_minutes or 0),
            "meta_fees": int(row.overage_meta_fees or 0),
        },
        "suggested_billing": suggested_packs(row),
        "alerts_sent": list(row.alerts_sent or []),
    }


async def owner_usage_report(session: AsyncSession, now: Optional[datetime] = None, include_inactive: bool = False) -> list[dict]:
    """Current-window usage for every (active) subscription, over-limit first."""
    from src.models import ClientProject

    query = select(ClientProject)
    if not include_inactive:
        query = query.where(ClientProject.status == "active")
    out = []
    for project in (await session.execute(query.order_by(ClientProject.created_at))).scalars().all():
        row = await current_usage(session, project, now)
        out.append(usage_summary(project, row))
    out.sort(key=lambda r: (not r["over_limit"], -max(m["pct"] for m in r["metrics"].values())))
    return out


# --------------------------------------------------------------------------- media understanding (voice notes / images)

MEDIA_KINDS = {"voice": "media_voice", "image": "media_image"}


async def record_media(session: AsyncSession, project_or_id, kind: str, *, provider: Optional[str] = None,
                       seconds: int = 0, contact: Optional[str] = None, ref: Optional[str] = None,
                       now: Optional[datetime] = None) -> dict:
    """Count one transcribed voice note / described image for this tenant.

    Recorded as a ``UsageEvent`` (``media_voice`` quantity = seconds reported by
    the provider, at least 1; ``media_image`` quantity = 1). It does not consume
    the plan's voice-agent minutes: whether media processing is billed is an
    owner pricing decision, so the counter only records it. A ``ref`` (WhatsApp
    message id) is counted once.
    """
    from src.models.usage import UsageEvent

    ekind = MEDIA_KINDS.get(kind)
    project = await _project(session, project_or_id)
    if project is None or ekind is None:
        return {"counted": False, "reason": "no project" if project is None else "unknown kind"}
    if ref and await _seen(session, project.id, ekind, ref):
        return {"counted": False, "reason": "duplicate"}
    now = _utc(now) or datetime.now(timezone.utc)
    qty = max(1, int(seconds or 0)) if ekind == "media_voice" else 1
    session.add(UsageEvent(project_id=project.id, kind=ekind, channel="whatsapp", contact_key=(contact or None),
                           ref=(ref or None) and str(ref)[:255], quantity=qty, occurred_at=now,
                           meta={"provider": provider} if provider else None))
    await session.flush()
    return {"counted": True, "kind": ekind, "quantity": qty}


async def media_usage(session: AsyncSession, project, now: Optional[datetime] = None) -> dict:
    """This window's voice notes (count + seconds) and images processed for one tenant."""
    from sqlalchemy import func as _f

    from src.models.usage import UsageEvent

    start, end = usage_window(project, now)
    rows = (await session.execute(
        select(UsageEvent.kind, _f.count(), _f.coalesce(_f.sum(UsageEvent.quantity), 0)).where(
            UsageEvent.project_id == project.id, UsageEvent.kind.in_(tuple(MEDIA_KINDS.values())),
            UsageEvent.occurred_at >= start, UsageEvent.occurred_at < end,
        ).group_by(UsageEvent.kind)
    )).all()
    got = {k: (int(n), int(q)) for k, n, q in rows}
    return {"voice_notes": got.get("media_voice", (0, 0))[0], "voice_seconds": got.get("media_voice", (0, 0))[1],
            "images": got.get("media_image", (0, 0))[0]}
