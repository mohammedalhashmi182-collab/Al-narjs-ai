"""Collections: renewal reminder sequence, overage billing, failed-payment recovery.

One idempotent pass (:func:`run_collections`), run daily right after the
renewal pass and on demand at ``POST /api/owner/billing/collections/run``.

Reminder sequence for an unpaid renewal order (relative to the project's
``current_period_end``): D-5, D-1, D0 (day of expiry) and D+3 (last notice,
the grace ends). Only the latest due stage is handled, each stage once per
order (``collection_reminders`` unique on payment+stage).

Channels per step:

- **Owner Telegram alert**: always sent (internal, no review needed).
- **Customer email**: sent through ``email_service`` only when
  ``BILLING_AUTO_SEND=true`` and SMTP/Brevo is configured; otherwise recorded
  as a ``draft`` ``OutboundMessage`` (channel ``email``) for owner review.
- **Customer WhatsApp**: the sender only supports free text, which Meta
  rejects outside the 24h window, so there is no approved-template mechanism
  yet. Each reminder is queued as a ``draft`` with ``error_code
  'needs_template'`` and flagged in the result (``whatsapp_template_missing``).
  D-5 is skipped here because the renewal job already drafts that one.

Every customer link points at our consent-gated ``/invoice/<id>`` page (it
offers card retry, PayPal and bank transfer), never at a raw gateway URL.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.services import catalog
from src.services import payments as pm

logger = logging.getLogger(__name__)

STAGES = (("d+3", timedelta(days=3)), ("d0", timedelta(0)), ("d-1", timedelta(days=-1)), ("d-5", timedelta(days=-5)))
RECOVERY_WINDOW = timedelta(days=7)
DRAFT = "draft"
WHATSAPP_FLAG = "needs_template"
UNPAID = {"pending", "invoice", "authorized", "failed"}

_STAGE_AR = {
    "d-5": "يقترب موعد تجديد اشتراكك (بعد 5 أيام)",
    "d-1": "تذكير: ينتهي اشتراكك غداً",
    "d0": "ينتهي اشتراكك اليوم",
    "d+3": "تنبيه أخير: انتهت فترة السماح ويُعلَّق الحساب اليوم ما لم يتم السداد",
}


def _aware(dt):
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _base_url(base_url: str = "") -> str:
    from src.config.settings import get_settings

    return (base_url or get_settings().public_base_url or "https://karmaai.online").rstrip("/")


def due_stage(period_end: datetime, now: datetime) -> Optional[str]:
    for name, offset in STAGES:
        if now >= period_end + offset:
            return name
    return None


def reminder_text(stage: str, project, payment, period_end: datetime, base_url: str) -> str:
    total = pm.payment_total(payment) / 100
    end = (period_end + timedelta(hours=3)).strftime("%Y-%m-%d")
    pkg = catalog.PACKAGES.get(project.package, {}).get("name", project.package)
    return (
        f"مرحباً {project.client_name}، {_STAGE_AR[stage]}. باقة {pkg} لدى النرجس، تاريخ الانتهاء {end}. "
        f"المبلغ المستحق {total:,.2f} ر.س{pm.vat_note_ar(payment)}. "
        f"للسداد: {base_url}/invoice/{payment.id} — رقم المرجع {pm.reference(payment)}."
    )


def recovery_text(payment, base_url: str) -> str:
    total = pm.payment_total(payment) / 100
    return (
        f"مرحباً {payment.customer_name or ''}، لم تكتمل عملية الدفع الأخيرة ({total:,.2f} ر.س). "
        f"يمكنك إعادة المحاولة بالبطاقة أو اختيار التحويل البنكي من هنا: {base_url}/invoice/{payment.id} "
        f"— رقم المرجع {pm.reference(payment)}."
    )


def overage_text(project, payment, base_url: str) -> str:
    total = pm.payment_total(payment) / 100
    return (
        f"مرحباً {project.client_name}، تجاوز استهلاكك الشهري الحد المشمول في باقتك، ولم نوقف الخدمة. "
        f"فاتورة الاستهلاك الإضافي {total:,.2f} ر.س{pm.vat_note_ar(payment)}: {base_url}/invoice/{payment.id}."
    )


def _auto_send() -> bool:
    from src.config.settings import get_settings

    return bool(getattr(get_settings(), "billing_auto_send", False))


async def _draft(session, channel: str, to: Optional[str], text: str, message_type: str, error_code: Optional[str] = None):
    from src.models.company import OutboundMessage

    now = datetime.now(timezone.utc)
    msg = OutboundMessage(
        id=uuid4(), channel=channel, phone=(to or "")[:32] or None,
        text=(f"To: {to}\n{text}" if channel == "email" and to else text),
        status=DRAFT, message_type=message_type[:20], error_code=error_code,
        error=("WhatsApp approved template required (free text fails outside the 24h window)"
               if error_code == WHATSAPP_FLAG else None),
        created_at=now, updated_at=now,
    )
    session.add(msg)
    return msg


async def _deliver(session, *, project_phone, email, subject: str, text: str, message_type: str,
                   owner_note: str, whatsapp: bool = True) -> dict:
    """Owner alert always; customer email sent only in auto mode; WhatsApp drafted."""
    from src.services import email_service, telegram_sender

    channels: dict = {}
    try:
        res = await telegram_sender.send_owner_alert(owner_note)
        channels["owner_telegram"] = "sent" if res.get("ok") else f"failed:{res.get('error_code') or 'error'}"
    except Exception as exc:  # pragma: no cover - network
        channels["owner_telegram"] = f"failed:{type(exc).__name__}"

    if email:
        if _auto_send() and email_service.is_configured():
            ok = await email_service.send_email(email, subject, text)
            channels["email"] = "sent" if ok else "failed"
            if not ok:
                await _draft(session, "email", email, text, message_type)
        else:
            await _draft(session, "email", email, text, message_type)
            channels["email"] = DRAFT
    else:
        channels["email"] = "skipped:no_email"

    if whatsapp and project_phone:
        await _draft(session, "whatsapp", project_phone, text, message_type, WHATSAPP_FLAG)
        channels["whatsapp"] = "draft:needs_template"
    return channels


async def _already(session, payment_id, stage: str) -> bool:
    from src.models.billing import CollectionReminder

    return (await session.execute(select(CollectionReminder.id).where(
        CollectionReminder.payment_id == payment_id, CollectionReminder.stage == stage).limit(1)
    )).scalar_one_or_none() is not None


async def _mark(session, project_id, payment_id, stage: str, channels: dict) -> None:
    from src.models.billing import CollectionReminder

    session.add(CollectionReminder(id=uuid4(), project_id=project_id, payment_id=payment_id,
                                   stage=stage, channels=channels))


async def run_reminders(session: AsyncSession, now: datetime, base_url: str) -> list[dict]:
    from src.models import ClientProject, Payment

    out = []
    projects = (await session.execute(select(ClientProject).where(
        ClientProject.renewal_payment_id.is_not(None),
        ClientProject.current_period_end.is_not(None),
        ClientProject.status.in_(("active", "expired")),
    ))).scalars().all()
    for project in projects:
        end = _aware(project.current_period_end)
        stage = due_stage(end, now)
        if stage is None or now > end + timedelta(days=7):
            continue
        payment = (await session.execute(select(Payment).where(Payment.id == project.renewal_payment_id))).scalar_one_or_none()
        if payment is None or payment.status not in UNPAID or await _already(session, payment.id, stage):
            continue
        text = reminder_text(stage, project, payment, end, base_url)
        channels = await _deliver(
            session, project_phone=project.phone, email=project.email,
            subject="تذكير تجديد الاشتراك — النرجس للذكاء الاصطناعي", text=text, message_type="renewal",
            owner_note=f"💳 تحصيل {stage}: {project.client_name} — {pm.payment_total(payment) / 100:,.2f} ر.س غير مسددة ({pm.reference(payment)})",
            whatsapp=stage != "d-5",
        )
        await _mark(session, project.id, payment.id, stage, channels)
        await session.commit()
        out.append({"project_id": str(project.id), "payment_id": str(payment.id), "stage": stage, "channels": channels})
    return out


async def run_recovery(session: AsyncSession, now: datetime, base_url: str) -> list[dict]:
    """A failed charge gets one recovery link (unless the customer paid since)."""
    from src.models import Payment

    out = []
    failed = (await session.execute(select(Payment).where(
        Payment.status == "failed", Payment.created_at >= now - RECOVERY_WINDOW,
    ))).scalars().all()
    for payment in failed:
        if await _already(session, payment.id, "recovery"):
            continue
        if payment.project_id is not None:
            paid_since = (await session.execute(select(Payment.id).where(
                Payment.project_id == payment.project_id, Payment.status == "paid",
                Payment.created_at >= payment.created_at).limit(1))).scalar_one_or_none()
            if paid_since is not None:
                continue
        text = recovery_text(payment, base_url)
        channels = await _deliver(
            session, project_phone=payment.customer_phone, email=payment.customer_email,
            subject="إكمال الدفع — النرجس للذكاء الاصطناعي", text=text, message_type="recovery",
            owner_note=f"⚠️ دفعة فاشلة: {payment.customer_name or '-'} ({pm.reference(payment)}) — رابط الاسترداد جاهز {base_url}/invoice/{payment.id}",
        )
        await _mark(session, payment.project_id, payment.id, "recovery", channels)
        await session.commit()
        out.append({"payment_id": str(payment.id), "stage": "recovery", "channels": channels,
                    "recovery_url": f"{base_url}/invoice/{payment.id}"})
    return out


async def bill_overage(session: AsyncSession, now: datetime, base_url: str) -> list[dict]:
    """One overage invoice per closed usage window that went over the allowance.

    The order uses package ``overage`` and no ``project_id`` so paying it never
    touches the subscription period (``activate_subscription`` finds no
    project); the project is recorded on the collection row and description.
    """
    from src.models import ClientProject, Payment
    from src.models.billing import CollectionReminder
    from src.models.usage import SubscriptionUsage
    from src.services import usage, zatca

    out = []
    rows = (await session.execute(select(SubscriptionUsage).where(
        SubscriptionUsage.over_limit.is_(True), SubscriptionUsage.period_end <= now,
    ))).scalars().all()
    for row in rows:
        stage = f"overage:{_aware(row.period_start).strftime('%Y-%m-%d')}"
        seen = (await session.execute(select(CollectionReminder.id).where(
            CollectionReminder.project_id == row.project_id, CollectionReminder.stage == stage).limit(1)
        )).scalar_one_or_none()
        if seen is not None:
            continue
        bill = usage.suggested_packs(row)
        if int(bill["total_due"]) <= 0:
            continue
        project = (await session.execute(select(ClientProject).where(ClientProject.id == row.project_id))).scalar_one_or_none()
        if project is None:
            continue
        payment = Payment(
            amount=int(bill["total_due"]), total_halalas=pm.total_with_vat(int(bill["total_due"])), currency="SAR", package=zatca.OVERAGE_PACKAGE, billing_period="monthly",
            addon_conversation_packs=int(bill["conversation_packs"]), addon_voice_packs=int(bill["voice_packs"]),
            customer_name=project.client_name, customer_phone=project.phone, customer_email=project.email,
            project_id=None, status="invoice", gateway="invoice",
            description=(f"فاتورة استهلاك إضافي للفترة {_aware(row.period_start).date()} — {_aware(row.period_end).date()} "
                         f"(مشروع {project.id})"),
        )
        session.add(payment)
        await session.flush()
        text = overage_text(project, payment, base_url)
        channels = await _deliver(
            session, project_phone=project.phone, email=project.email,
            subject="فاتورة الاستهلاك الإضافي — النرجس للذكاء الاصطناعي", text=text, message_type="overage",
            owner_note=f"📈 فاتورة استهلاك إضافي: {project.client_name} — {pm.payment_total(payment) / 100:,.2f} ر.س ({base_url}/invoice/{payment.id})",
        )
        session.add(CollectionReminder(id=uuid4(), project_id=project.id, payment_id=payment.id, stage=stage, channels=channels))
        await session.commit()
        out.append({"project_id": str(project.id), "payment_id": str(payment.id), "amount": payment.amount,
                    "total": pm.payment_total(payment), "channels": channels})
    return out


async def run_collections(session: AsyncSession, *, now: Optional[datetime] = None, base_url: str = "") -> dict:
    now = _aware(now) or datetime.now(timezone.utc)
    base = _base_url(base_url)
    reminders = await run_reminders(session, now, base)
    recovery = await run_recovery(session, now, base)
    overage = await bill_overage(session, now, base)
    template_missing = any("whatsapp" in r["channels"] for r in reminders + recovery + overage)
    return {
        "ran_at": now.isoformat(),
        "auto_send": _auto_send(),
        "reminders": reminders,
        "recovery": recovery,
        "overage": overage,
        "whatsapp_template_missing": template_missing,
    }
