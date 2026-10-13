"""Subscription renewals: invoice before expiry, expire after a grace period.

How it works (one pass of :func:`run_renewals`):

1. Every ``active`` client project with a ``current_period_end`` is examined.
   Projects activated before renewals existed have ``current_period_end`` NULL
   and are left alone (no invoice, no expiry) until the owner backfills them.
2. From ``days_before`` days before the end (default
   :data:`RENEWAL_LEAD_DAYS`) the job raises ONE renewal order per period:
   same tier, billing period and add-on agents, at today's catalog price, no
   promo. When Moyasar is configured a hosted invoice is created for the
   VAT-inclusive total (the same ``initiate_moyasar`` path and amount checks
   as a first purchase); otherwise, or when Moyasar errors, it stays a manual
   invoice (``/invoice/<id>``). The order id is kept on
   ``project.renewal_payment_id`` so later passes never duplicate it.
3. A renewal reminder is recorded as an ``OutboundMessage`` with status
   ``draft``. No sender flushes ``draft`` rows: nothing is sent to the client
   until the owner reviews it and moves it to ``queued``.
4. When the renewal order is paid, the normal paid path
   (``payments.activate_subscription``) extends ``current_period_end`` by one
   or twelve months from the old end.
5. If the period ended more than :data:`payments.RENEWAL_GRACE` (3 days) ago
   and nothing was paid, the project is set to ``expired``; the portal already
   refuses to wake or run agents on a non-active project.

The pass is idempotent and safe to run as often as you like. It runs daily from
the in-process APScheduler (``billing.renewals``, 08:00 Asia/Riyadh) and can be
triggered by the owner at ``POST /api/owner/billing/renewals/run``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.services import catalog, payments

logger = logging.getLogger(__name__)

RENEWAL_LEAD_DAYS = 5
RENEWAL_SCHEDULE_NAME = "billing.renewals"
RENEWAL_SCHEDULE_CRON = "0 8 * * *"  # daily, Asia/Riyadh
REMINDER_STATUS = "draft"            # never picked up by telegram/whatsapp flush_queue
REMINDER_TYPE = "renewal"

# A renewal order in one of these states is still payable: do not raise another.
_OPEN_STATES = {"pending", "invoice", "authorized", "paid", payments.REVIEW_STATUS}


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def reminder_text(project, payment, period_end: datetime) -> str:
    pkg = catalog.PACKAGES.get(project.package) or catalog.get_package(project.package) or {}
    total = payments.total_with_vat(payment.amount) / 100
    period = "سنوي" if payment.billing_period == "annual" else "شهري"
    end_riyadh = (period_end + timedelta(hours=3)).strftime("%Y-%m-%d")
    return (
        f"مرحباً {project.client_name}، يقترب موعد تجديد اشتراكك ({period}) في باقة "
        f"{pkg.get('name', project.package)} لدى النرجس. ينتهي الاشتراك في {end_riyadh}. "
        f"قيمة التجديد {total:,.2f} ر.س شاملة ضريبة القيمة المضافة. "
        f"فاتورة التجديد: /invoice/{payment.id} — رقم المرجع {payments.reference(payment)}."
    )


async def _raise_renewal(session: AsyncSession, project, *, base_url: str, use_gateway: bool) -> dict:
    from src.models.company import OutboundMessage

    package = catalog.resolve_tier(project.package)
    payment = await payments.create_payment(
        session,
        package,
        project.client_name,
        project.phone,
        project.email,
        project_id=project.id,
        billing_period=project.billing_period or "monthly",
        addons=int(project.addon_agents or 0),
        is_renewal=True,
    )
    gateway = "invoice"
    checkout_url = None
    if use_gateway:
        try:
            data = await payments.initiate_moyasar(
                session,
                payment,
                payments.source_credit_card(),
                success_url=f"{base_url}/payment/success?id={payment.id}",
                back_url=f"{base_url}/payment/failure?id={payment.id}",
                callback_url=f"{base_url}/webhooks/moyasar",
            )
            gateway = "moyasar"
            checkout_url = data.get("checkout_url")
        except payments.PaymentError as exc:
            logger.warning("renewal %s: Moyasar invoice failed, manual invoice instead: %s", payment.id, exc)
    if gateway == "invoice":
        payment.status = "invoice"

    project.renewal_payment_id = payment.id
    text = reminder_text(project, payment, _aware(project.current_period_end))
    if checkout_url:
        text += f" رابط الدفع: {checkout_url}"
    session.add(OutboundMessage(
        id=uuid4(),
        channel="whatsapp",
        phone=(project.phone or "")[:32] or None,
        text=text,
        status=REMINDER_STATUS,
        message_type=REMINDER_TYPE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    ))
    await session.commit()
    return {
        "project_id": str(project.id),
        "payment_id": str(payment.id),
        "gateway": gateway,
        "amount": payment.amount,
        "total": payments.total_with_vat(payment.amount),
        "billing_period": payment.billing_period,
    }


async def run_renewals(
    session: AsyncSession,
    *,
    now: Optional[datetime] = None,
    days_before: int = RENEWAL_LEAD_DAYS,
    base_url: str = "",
    use_gateway: Optional[bool] = None,
) -> dict:
    """One idempotent renewal pass. Returns what it invoiced and expired."""
    from src.config.settings import get_settings
    from src.models import ClientProject, Payment

    now = _aware(now) or datetime.now(timezone.utc)
    if use_gateway is None:
        use_gateway = bool(get_settings().moyasar_api_secret)
    base_url = (base_url or get_settings().public_base_url or "https://karmaai.online").rstrip("/")
    horizon = now + timedelta(days=max(0, int(days_before)))

    projects = (
        await session.execute(
            select(ClientProject).where(
                ClientProject.status == "active",
                ClientProject.current_period_end.is_not(None),
                ClientProject.current_period_end <= horizon,
            )
        )
    ).scalars().all()

    invoiced, expired, skipped = [], [], []
    for project in projects:
        end = _aware(project.current_period_end)
        if now > end + payments.RENEWAL_GRACE:
            project.status = "expired"
            project.subscription_note = (
                f"expired on {now.isoformat()}: period ended {end.isoformat()}, "
                f"{payments.RENEWAL_GRACE.days}-day grace elapsed without payment"
            )
            await session.commit()
            expired.append(str(project.id))
            continue

        if project.renewal_payment_id is not None:
            existing = (
                await session.execute(select(Payment).where(Payment.id == project.renewal_payment_id))
            ).scalar_one_or_none()
            if existing is not None and existing.status in _OPEN_STATES:
                skipped.append(str(project.id))
                continue
        try:
            invoiced.append(await _raise_renewal(session, project, base_url=base_url, use_gateway=use_gateway))
        except payments.PaymentError as exc:
            await session.rollback()
            logger.warning("renewal for project %s failed: %s", project.id, exc)
            skipped.append(str(project.id))

    return {
        "ran_at": now.isoformat(),
        "days_before": days_before,
        "grace_days": payments.RENEWAL_GRACE.days,
        "invoiced": invoiced,
        "expired": expired,
        "skipped": skipped,
    }


async def ensure_renewal_schedule(scheduler) -> None:
    """Register the daily renewal pass with the app scheduler (once)."""
    from src.automation.scheduler import ScheduleConfig
    from src.models import Schedule

    try:
        async with scheduler.session_factory() as session:
            exists = (
                await session.execute(select(Schedule).where(Schedule.name == RENEWAL_SCHEDULE_NAME))
            ).scalar_one_or_none()
        if exists is not None:
            return
        await scheduler.add_schedule(ScheduleConfig(
            name=RENEWAL_SCHEDULE_NAME,
            target_type="billing_renewals",
            target_id=uuid4(),
            payload={"days_before": RENEWAL_LEAD_DAYS},
            cron_expression=RENEWAL_SCHEDULE_CRON,
            timezone="Asia/Riyadh",
        ))
        logger.info("Registered renewal schedule %s (%s)", RENEWAL_SCHEDULE_NAME, RENEWAL_SCHEDULE_CRON)
    except Exception as e:  # pragma: no cover - defensive on startup
        logger.warning("Could not register renewal schedule: %s", e)
