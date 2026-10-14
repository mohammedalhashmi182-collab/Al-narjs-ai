"""Founding-customer offer: the first ``catalog.FOUNDING_OFFER["seats"]`` (15).

Seats are held by
  * activated founding projects that were not revoked, and
  * founding orders still awaiting payment (created within ``HOLD``), so a
    burst of checkouts cannot sell more than 15 discounted seats.
New (non-renewal) orders get the founding price automatically while a seat is
free: 30% off annual or 20% off monthly with a 3-month commitment, setup fee
waived. A founding project keeps the price on renewals until
``founding_locked_until`` (activation + ``locked_months``). The owner can
revoke a seat; that frees it and stops the discount on future renewals.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.services import catalog

HOLD = timedelta(hours=72)
UNPAID_STATUSES = ("pending", "invoice", "initiated")


def _utc(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


async def seats_used(session: AsyncSession, now: Optional[datetime] = None) -> int:
    from src.models import ClientProject, Payment

    now = _utc(now) or datetime.now(timezone.utc)
    projects = (await session.execute(
        select(ClientProject.id).where(ClientProject.founding.is_(True), ClientProject.founding_revoked_at.is_(None))
    )).scalars().all()
    held = set(str(p) for p in projects)
    pending = (await session.execute(
        select(Payment.project_id, Payment.id, Payment.created_at).where(
            Payment.founding.is_(True), Payment.is_renewal.is_(False), Payment.status.in_(UNPAID_STATUSES),
        )
    )).all()
    extra = 0
    seen = set()
    for project_id, payment_id, created in pending:
        created = _utc(created)
        if created is not None and now - created > HOLD:
            continue
        key = str(project_id) if project_id else f"pay:{payment_id}"
        if key in held or key in seen:
            continue
        seen.add(key)
        extra += 1
    return len(held) + extra


async def seats_remaining(session: AsyncSession, now: Optional[datetime] = None) -> int:
    return max(0, int(catalog.FOUNDING_OFFER["seats"]) - await seats_used(session, now))


async def status(session: AsyncSession, now: Optional[datetime] = None) -> dict:
    used = await seats_used(session, now)
    total = int(catalog.FOUNDING_OFFER["seats"])
    return {**catalog.FOUNDING_OFFER, "seats_total": total, "seats_used": min(used, total),
            "seats_remaining": max(0, total - used), "available": used < total}


async def project_has_founding_price(project, now: Optional[datetime] = None) -> bool:
    if project is None or not getattr(project, "founding", False) or project.founding_revoked_at is not None:
        return False
    now = _utc(now) or datetime.now(timezone.utc)
    until = _utc(project.founding_locked_until)
    return until is None or now < until


async def eligible_for_order(session: AsyncSession, package: str, *, is_renewal: bool, project=None,
                             now: Optional[datetime] = None) -> bool:
    """Should this order be priced at the founding rate?"""
    if package not in catalog.PACKAGES:
        return False  # legacy renewals stay on their grandfathered price
    if project is not None and getattr(project, "founding", False):
        return await project_has_founding_price(project, now)
    if is_renewal:
        return False
    if project is not None and project.founding_revoked_at is not None:
        return False  # revoked by the owner: never re-applied automatically
    return await seats_remaining(session, now) > 0


def mark_project(project, payment, now: datetime) -> None:
    """On activation of a founding order: take the seat and stamp the terms."""
    from src.services.payments import add_months

    if getattr(project, "founding", False) or project.founding_revoked_at is not None:
        return
    project.founding = True
    project.founding_at = now
    project.founding_locked_until = add_months(now, int(catalog.FOUNDING_OFFER.get("locked_months", 12)))
    if catalog.resolve_billing_period(payment.billing_period) == "monthly":
        project.founding_commitment_until = add_months(now, int(catalog.FOUNDING_OFFER["monthly_commitment_months"]))


async def revoke(session: AsyncSession, project, now: Optional[datetime] = None) -> dict:
    now = _utc(now) or datetime.now(timezone.utc)
    if not getattr(project, "founding", False):
        return {"revoked": False, "reason": "not a founding customer"}
    project.founding = False
    project.founding_revoked_at = now
    await session.commit()
    return {"revoked": True, "project_id": str(project.id), "seats_remaining": await seats_remaining(session, now)}


async def founding_projects(session: AsyncSession) -> list[dict]:
    from src.models import ClientProject

    rows = (await session.execute(
        select(ClientProject).where((ClientProject.founding.is_(True)) | (ClientProject.founding_revoked_at.isnot(None)))
        .order_by(ClientProject.founding_at)
    )).scalars().all()
    return [{
        "project_id": str(p.id), "client_name": p.client_name, "package": p.package,
        "billing_period": p.billing_period, "founding": bool(p.founding),
        "founding_at": _utc(p.founding_at).isoformat() if p.founding_at else None,
        "locked_until": _utc(p.founding_locked_until).isoformat() if p.founding_locked_until else None,
        "commitment_until": _utc(p.founding_commitment_until).isoformat() if p.founding_commitment_until else None,
        "revoked_at": _utc(p.founding_revoked_at).isoformat() if p.founding_revoked_at else None,
    } for p in rows]
