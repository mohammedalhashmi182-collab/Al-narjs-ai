"""Founding-customer offer: the first ``catalog.FOUNDING_OFFER["seats"]`` (15).

Seats are held ONLY by activated (paid/confirmed) founding projects that were
not revoked. Unpaid orders are shown the founding price while a seat is free,
and availability is re-checked at activation: if the seats ran out meanwhile
the order's price is honoured but no seat is granted (never more than 15).
New (non-renewal) orders get the founding price automatically while a seat is
free: 30% off annual or 20% off monthly with a 3-month commitment, setup fee
waived. A founding project keeps the price on renewals until
``founding_locked_until`` (activation + ``locked_months``). The owner can
revoke a seat; that frees it and stops the discount on future renewals.
"""

from __future__ import annotations

import logging

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.services import catalog

logger = logging.getLogger(__name__)

HOLD = timedelta(hours=72)  # kept for backwards compatibility; no longer holds seats
UNPAID_STATUSES = ("pending", "invoice", "initiated")


def _utc(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


async def seats_used(session: AsyncSession, now: Optional[datetime] = None) -> int:
    """Seats are taken only by activated (paid/confirmed) founding projects.

    Unpaid orders (pending/invoice/initiated) never hold a seat, so abandoned
    or spam checkouts cannot exhaust the offer.
    """
    from sqlalchemy import func

    from src.models import ClientProject

    return int((await session.execute(
        select(func.count(ClientProject.id)).where(
            ClientProject.founding.is_(True), ClientProject.founding_revoked_at.is_(None))
    )).scalar() or 0)


async def seats_remaining(session: AsyncSession, now: Optional[datetime] = None) -> int:
    return max(0, int(catalog.FOUNDING_OFFER["seats"]) - await seats_used(session, now))


async def status(session: AsyncSession, now: Optional[datetime] = None) -> dict:
    if not catalog.founding_enabled():
        return {"enabled": False, "seats_total": 0, "seats_used": 0, "seats_remaining": 0, "available": False}
    used = await seats_used(session, now)
    total = int(catalog.FOUNDING_OFFER["seats"])
    return {**catalog.FOUNDING_OFFER, "enabled": True, "seats_total": total, "seats_used": min(used, total),
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
    if not catalog.founding_enabled():
        return False  # offer removed by the owner: no founding discount anywhere
    if package not in catalog.PACKAGES:
        return False  # legacy renewals stay on their grandfathered price
    if project is not None and getattr(project, "founding", False):
        return await project_has_founding_price(project, now)
    if is_renewal:
        return False
    if project is not None and project.founding_revoked_at is not None:
        return False  # revoked by the owner: never re-applied automatically
    return await seats_remaining(session, now) > 0


async def mark_project(session: AsyncSession, project, payment, now: datetime) -> bool:
    """On activation of a founding order: take a seat (if one is free) and stamp the terms.

    Returns True when a seat was granted. If all seats were taken between the
    order and its payment, the paid price is honoured but no seat is taken.
    """
    from src.services.payments import add_months

    if getattr(project, "founding", False) or project.founding_revoked_at is not None:
        return False
    if await seats_remaining(session, now) <= 0:
        logger.warning("founding seats full at activation; honouring price without seat "
                       "(project=%s payment=%s)", getattr(project, "id", None), getattr(payment, "id", None))
        return False
    project.founding = True
    project.founding_at = now
    project.founding_locked_until = add_months(now, int(catalog.FOUNDING_OFFER.get("locked_months", 12)))
    if catalog.resolve_billing_period(payment.billing_period) == "monthly":
        project.founding_commitment_until = add_months(now, int(catalog.FOUNDING_OFFER["monthly_commitment_months"]))
    return True


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
