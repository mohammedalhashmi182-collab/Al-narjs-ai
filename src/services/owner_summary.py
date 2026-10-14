"""Owner command center: one read-only snapshot of the business.

Feeds both the Arabic owner page (``/owner/command``) and the JSON endpoint
``GET /api/owner/summary`` that an assistant bot reads. Everything here is a
read: no row is modified. Amounts are halalas (pre-VAT) plus a SAR float.
Nothing secret is returned: error texts are cut short and scrubbed of anything
that looks like a key or token.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

RIYADH = timezone(timedelta(hours=3))
RENEWAL_WINDOW_DAYS = 7
USAGE_WARN_PCT = 80.0
USAGE_LIMIT_PCT = 100.0
UNPAID_STATUSES = ("pending", "initiated", "authorized")
_SECRETISH = re.compile(r"(?i)(sk|pk|key|token|secret|bearer|password)[-_=: ]*[A-Za-z0-9._\-]{6,}|[A-Za-z0-9_\-]{32,}")


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    d = _utc(dt)
    return d.isoformat() if d else None


def _sar(halalas) -> float:
    return round(int(halalas or 0) / 100, 2)


def scrub(text: Optional[str], limit: int = 160) -> str:
    """Short, key-free one-liner for an error message."""
    t = " ".join(str(text or "").split())[:limit]
    return _SECRETISH.sub("[redacted]", t)


def month_start(now: datetime) -> datetime:
    """Start of the current calendar month in Riyadh, as UTC."""
    local = _utc(now).astimezone(RIYADH)
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def monthly_value(project) -> int:
    """List-price monthly value (halalas) of an active subscription; annual spread over 12."""
    from src.services import catalog

    pkg = project.package
    if pkg not in catalog.PACKAGES and pkg not in catalog.LEGACY_TIERS:
        return 0
    try:
        return int(catalog.plan_amount(pkg, "monthly", project.addon_agents or 0))
    except Exception:
        return 0


def _plan_name(key: Optional[str]) -> str:
    from src.services import catalog

    pkg = catalog.PACKAGES.get(key or "") or catalog.LEGACY_TIERS.get(key or "") or {}
    return pkg.get("name") or (key or "-")


def _is_bank_transfer(p) -> bool:
    # Manual payments: gateway "invoice" not yet handed to a card gateway.
    return p.gateway not in ("moyasar", "paypal")


async def _revenue(session, now) -> dict:
    from src.models import Payment

    start = month_start(now)
    paid = (await session.execute(select(Payment).where(Payment.status == "paid"))).scalars().all()
    this_month = [p for p in paid if (_utc(p.updated_at or p.created_at) or start) >= start]
    total = sum(int(p.amount or 0) for p in this_month)
    return {"month_start": start.isoformat(), "paid_count": len(this_month),
            "revenue_halalas": total, "revenue_sar": _sar(total),
            "all_time_halalas": sum(int(p.amount or 0) for p in paid),
            "all_time_sar": _sar(sum(int(p.amount or 0) for p in paid))}


async def _subscriptions(session, now) -> tuple[dict, list[dict]]:
    from src.models import ClientProject

    active = (await session.execute(
        select(ClientProject).where(ClientProject.status == "active")
    )).scalars().all()
    by_plan: dict[str, dict] = {}
    mrr = 0
    for p in active:
        v = monthly_value(p)
        mrr += v
        b = by_plan.setdefault(p.package, {"plan": p.package, "name": _plan_name(p.package), "count": 0, "mrr_halalas": 0})
        b["count"] += 1
        b["mrr_halalas"] += v
    for b in by_plan.values():
        b["mrr_sar"] = _sar(b["mrr_halalas"])

    horizon = _utc(now) + timedelta(days=RENEWAL_WINDOW_DAYS)
    renewals = []
    for p in active:
        end = _utc(p.current_period_end)
        if end is not None and end <= horizon:
            renewals.append({
                "project_id": str(p.id), "client_name": p.client_name, "plan": p.package,
                "billing_period": p.billing_period, "period_end": end.isoformat(),
                "days_left": (end - _utc(now)).days, "overdue": end < _utc(now),
                "renewal_invoice_raised": p.renewal_payment_id is not None,
                "amount_sar": _sar(monthly_value(p)),
            })
    renewals.sort(key=lambda r: r["period_end"])
    subs = {"active": len(active), "mrr_halalas": mrr, "mrr_sar": _sar(mrr),
            "mrr_note": "list price, annual plans spread over 12 months",
            "by_plan": sorted(by_plan.values(), key=lambda b: -b["count"])}
    return subs, renewals


async def _orders(session) -> dict:
    from src.models import Payment

    rows = (await session.execute(
        select(Payment).where(Payment.status.in_(UNPAID_STATUSES)).order_by(desc(Payment.created_at)).limit(200)
    )).scalars().all()

    def row(p):
        return {"payment_id": str(p.id), "customer": p.customer_name or p.customer_email or "-",
                "plan": p.package, "status": p.status, "gateway": p.gateway,
                "amount_sar": _sar(p.amount), "is_renewal": bool(p.is_renewal),
                "created_at": _iso(p.created_at), "invoice_url": f"/invoice/{p.id}"}

    transfers = [row(p) for p in rows if _is_bank_transfer(p)]
    others = [row(p) for p in rows if not _is_bank_transfer(p)]
    return {"unpaid_count": len(rows), "unpaid_sar": _sar(sum(int(p.amount or 0) for p in rows)),
            "awaiting_transfer_confirmation": transfers, "pending_gateway": others[:50]}


async def _usage(session, now) -> dict:
    from src.services import usage

    try:
        rows = await usage.owner_usage_report(session, now=now)
    except Exception:
        return {"customers": [], "warn_count": 0, "over_count": 0, "error": "usage_unavailable"}
    out = []
    for r in rows:
        peak = max([m.get("pct", 0.0) for m in r["metrics"].values()] or [0.0])
        flag = "over" if (peak >= USAGE_LIMIT_PCT or r["over_limit"]) else ("warn" if peak >= USAGE_WARN_PCT else "ok")
        out.append({"project_id": r["project_id"], "client_name": r["client_name"], "plan": r["package"],
                    "metrics": r["metrics"], "peak_pct": peak, "flag": flag})
    out.sort(key=lambda r: -r["peak_pct"])
    return {"customers": out, "warn_count": sum(r["flag"] == "warn" for r in out),
            "over_count": sum(r["flag"] == "over" for r in out),
            "thresholds_pct": [USAGE_WARN_PCT, USAGE_LIMIT_PCT]}


async def _review_queue(session) -> dict:
    from src.models.automation import ReplyDraft

    rows = (await session.execute(
        select(ReplyDraft.channel, ReplyDraft.meta).where(ReplyDraft.status == "pending")
    )).all()
    by_project: dict[str, int] = {}
    by_channel: dict[str, int] = {}
    for channel, meta in rows:
        key = str((meta or {}).get("project_id") or "karma")  # no project = our own sales inbox
        by_project[key] = by_project.get(key, 0) + 1
        by_channel[channel] = by_channel.get(channel, 0) + 1
    return {"pending_total": len(rows), "by_project": by_project, "by_channel": by_channel}


async def _leads(session) -> dict:
    from src.models import AcquisitionLead
    from src.models.automation import PIPELINE_STAGES, LeadPipeline

    stages = dict((await session.execute(
        select(LeadPipeline.stage, func.count()).group_by(LeadPipeline.stage))).all())
    statuses = dict((await session.execute(
        select(AcquisitionLead.lead_status, func.count()).group_by(AcquisitionLead.lead_status))).all())
    return {"pipeline": {s: int(stages.get(s, 0)) for s in PIPELINE_STAGES},
            "lead_status": {k: int(v) for k, v in sorted(statuses.items(), key=lambda kv: str(kv[0]))},
            "total_leads": int(sum(statuses.values()))}


async def _health(session, now) -> dict:
    from src.models import WorkflowExecution

    db_ok = True
    try:
        await session.execute(select(1))
    except Exception:
        db_ok = False
    since = _utc(now) - timedelta(hours=24)
    errors = []
    try:
        rows = (await session.execute(
            select(WorkflowExecution).where(WorkflowExecution.status == "failed")
            .order_by(desc(WorkflowExecution.created_at)).limit(10)
        )).scalars().all()
        errors = [{"source": "workflow", "id": str(e.id), "at": _iso(e.created_at),
                   "message": scrub(e.error)} for e in rows]
    except Exception:
        pass
    pay = {}
    try:
        from src.services import payments as pm

        caps = pm.capabilities()  # config booleans only; no live probe here
        pay = {k: v for k, v in (caps.get("methods") or caps).items() if isinstance(v, bool)}
    except Exception:
        pay = {}
    recent = [e for e in errors if e["at"] and e["at"] >= since.isoformat()]
    status = "down" if not db_ok else ("degraded" if recent else "ok")
    return {"status": status, "database": db_ok, "errors_24h": len(recent),
            "payment_methods": pay, "recent_errors": errors}


async def build_summary(session: AsyncSession, now: Optional[datetime] = None) -> dict:
    from src.services import founding

    now = _utc(now) or datetime.now(timezone.utc)
    subs, renewals = await _subscriptions(session, now)
    fstatus = await founding.status(session, now)
    return {
        "generated_at": now.isoformat(),
        "currency": "SAR",
        "revenue": await _revenue(session, now),
        "subscriptions": subs,
        "renewals_due": {"window_days": RENEWAL_WINDOW_DAYS, "count": len(renewals), "items": renewals},
        "orders": await _orders(session),
        "founding": {k: fstatus[k] for k in ("seats_total", "seats_used", "seats_remaining", "available")}
        | {"customers": await founding.founding_projects(session)},
        "usage": await _usage(session, now),
        "review_queue": await _review_queue(session),
        "leads": await _leads(session),
        "health": await _health(session, now),
    }
