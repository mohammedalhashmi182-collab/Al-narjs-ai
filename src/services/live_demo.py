"""Live demo «جرّب الوكيل الآن»: a fictional Riyadh clinic answered by the tenant reply agent.

Rules:
* The demo tenant is a ``ClientProject`` with ``status="demo"`` so renewals,
  usage reports and every ``status == "active"`` query ignore it. It has its
  own KB (``KnowledgeDoc`` rows with its ``project_id``).
* Replies come from ``tenant_reply.handle_inbound`` (KB only, no LLM, no pitch).
  ``reply_mode`` is ``review`` and no token is stored, so nothing is sent on
  WhatsApp from here; drafts are stored with status ``demo``.
* No payments: the demo never creates orders, payment links or invoices, and
  any payment/booking question gets a fixed "this is a demo" answer.
* Retention: demo drafts and contacts older than 24h are deleted
  (``purge_expired``), on every chat call and from the hourly scheduler hook.
* Rate-limited per IP and per day globally; every reply is labelled as demo.
"""
from __future__ import annotations

import hashlib
import os
import re
from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import ClientProject
from src.models.agent_tools import KnowledgeDoc
from src.models.automation import ReplyDraft
from src.models.tenant import TenantContact
from src.utils.rate_limit import SlidingWindowLimiter

DEMO_STATUS = "demo"
DEMO_EMAIL = "live-demo@demo.invalid"
DEMO_NAME = "عيادة الياسمين لطب الأسنان (تجريبية)"
DEMO_NAME_EN = "Yasmin Dental Clinic (demo)"
RETENTION = timedelta(hours=24)
MAX_TEXT = 500
LABEL_AR = "🧪 نسخة تجريبية — عيادة خيالية لعرض الوكيل فقط. لا حجوزات ولا مدفوعات حقيقية."
LABEL_EN = "🧪 Demo — a fictional clinic to show the agent. No real bookings or payments."

# Fictional business: every fact below is invented for the demo and labelled as such.
KB = [
    ("أوقات الدوام", "نستقبلكم من الأحد إلى الخميس من 9 صباحاً حتى 9 مساءً، والسبت من 4 عصراً حتى 10 مساءً. الجمعة إجازة."),
    ("الموقع", "العيادة (الخيالية) في حي الياسمين شمال الرياض، طريق أنس بن مالك، ويوجد مواقف للسيارات."),
    ("الخدمات", "تنظيف الأسنان، الحشوات التجميلية، تبييض الأسنان، تقويم الأسنان الشفاف، علاج العصب، وطب أسنان الأطفال."),
    ("الأسعار التقريبية", "أسعار تجريبية للعرض فقط: الكشف 100 ريال، التنظيف 250 ريال، التبييض يبدأ من 900 ريال. السعر النهائي بعد الكشف."),
    ("الحجز", "في النسخة الحقيقية يأخذ الوكيل اسمك والوقت المناسب ويحوّله لموظف الاستقبال للتأكيد. هذه نسخة تجريبية فلا يُسجَّل أي موعد."),
    ("التأمين", "نتعامل (في هذا المثال) مع أغلب شركات التأمين الطبي الكبرى؛ أرسل اسم شركتك ونؤكد لك التغطية."),
    ("الطوارئ", "لآلام الأسنان الشديدة أو التورم نخصص مواعيد طوارئ في نفس اليوم خلال ساعات العمل."),
]

PAYMENT_WORDS = ("ادفع", "دفع", "الدفع", "بطاقة", "مدى", "فيزا", "تحويل", "رابط دفع", "سداد", "عربون",
                 "pay", "payment", "card", "visa", "mada", "transfer", "deposit", "checkout")
PAYMENT_REPLY = ("هذه نسخة تجريبية 🙏 لا يتم فيها أي دفع أو حجز حقيقي. "
                 "في النسخة الحقيقية يحوّلك الوكيل لفريق العيادة لإكمال الحجز.")

ip_limiter = SlidingWindowLimiter(max_requests=int(os.getenv("DEMO_RATE_PER_MIN", "8")), window_seconds=60)
ip_daily_limiter = SlidingWindowLimiter(max_requests=int(os.getenv("DEMO_RATE_PER_DAY", "60")), window_seconds=86400)
global_daily_limiter = SlidingWindowLimiter(max_requests=int(os.getenv("DEMO_GLOBAL_PER_DAY", "2000")), window_seconds=86400)


def reset_limits() -> None:
    for lim in (ip_limiter, ip_daily_limiter, global_daily_limiter):
        lim.reset()


def check_rate(ip: str) -> tuple[bool, int]:
    for lim, key in ((ip_limiter, ip), (ip_daily_limiter, ip), (global_daily_limiter, "all")):
        ok, retry = lim.check(f"demo:{key}")
        if not ok:
            return False, retry
    return True, 0


def whatsapp_config() -> dict:
    """Optional WhatsApp demo number (env only; nothing is configured by default)."""
    number = re.sub(r"\D", "", os.getenv("DEMO_WHATSAPP_NUMBER", ""))
    return {"enabled": bool(number), "number": number or None,
            "link": f"https://wa.me/{number}" if number else None,
            "phone_number_id": os.getenv("DEMO_WA_PHONE_NUMBER_ID", "").strip() or None}


async def ensure_demo_project(session: AsyncSession) -> ClientProject:
    proj = (await session.execute(select(ClientProject).where(
        ClientProject.email == DEMO_EMAIL, ClientProject.status == DEMO_STATUS))).scalar_one_or_none()
    if proj is None:
        proj = ClientProject(client_name=DEMO_NAME, phone="0000000000", email=DEMO_EMAIL, package="radd",
                             status=DEMO_STATUS, reply_mode="review",
                             subscription_note="مشروع العرض التجريبي — لا فوترة ولا مدفوعات")
        session.add(proj)
        await session.flush()
    wa = whatsapp_config()["phone_number_id"]
    if wa and proj.wa_phone_number_id != wa:
        proj.wa_phone_number_id = wa
    have = (await session.execute(select(KnowledgeDoc.title).where(KnowledgeDoc.project_id == proj.id))).scalars().all()
    for title, content in KB:
        if title not in have:
            session.add(KnowledgeDoc(project_id=proj.id, title=title, source="text", content=f"{title}: {content}"))
    await session.flush()
    return proj


def is_demo_project(project: Optional[ClientProject]) -> bool:
    return bool(project is not None and project.status == DEMO_STATUS)


def _contact_key(session_id: str) -> str:
    # Opaque per-browser key; no IP or personal data is stored.
    # tenant_reply normalises contacts to digits, so keep the key numeric.
    return str(int(hashlib.sha256(f"live-demo:{session_id}".encode()).hexdigest()[:15], 16))


async def purge_expired(session: AsyncSession, now: Optional[datetime] = None) -> int:
    now = now or datetime.now(UTC)
    proj = (await session.execute(select(ClientProject.id).where(
        ClientProject.email == DEMO_EMAIL, ClientProject.status == DEMO_STATUS))).scalar_one_or_none()
    if proj is None:
        return 0
    cutoff = now - RETENTION
    d = await session.execute(delete(ReplyDraft).where(ReplyDraft.project_id == proj, ReplyDraft.created_at < cutoff))
    c = await session.execute(delete(TenantContact).where(TenantContact.project_id == proj,
                                                          TenantContact.last_inbound_at < cutoff))
    return int(d.rowcount or 0) + int(c.rowcount or 0)


def _wants_payment(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in PAYMENT_WORDS)


async def chat(session: AsyncSession, session_id: str, text: str, now: Optional[datetime] = None) -> dict:
    from src.services import tenant_reply

    text = (text or "").strip()[:MAX_TEXT]
    if not text:
        return {"reply": "", "demo": True, "label": LABEL_AR}
    await purge_expired(session, now)
    proj = await ensure_demo_project(session)
    key = _contact_key(session_id or "anon")
    if _wants_payment(text):
        reply, kind = PAYMENT_REPLY, "demo_no_payment"
    else:
        draft = await tenant_reply.handle_inbound(session, project=proj, contact=key, text=text)
        if draft is None:
            reply, kind = "تم 👍 (نسخة تجريبية)", "noop"
        else:
            draft.status = "demo"
            reply, kind = draft.draft_text, draft.kind
        # The demo never "parks" a visitor with a human: clear handoff/opt-out so they can keep trying.
        c = (await session.execute(select(TenantContact).where(
            TenantContact.project_id == proj.id, TenantContact.contact == tenant_reply._norm(key)))).scalar_one_or_none()
        if c is not None:
            c.handoff_at = None
            c.opt_out = False
    if tenant_reply.contains_pitch(reply):
        reply = PAYMENT_REPLY
    await session.commit()
    return {"reply": reply, "kind": kind, "demo": True, "label": LABEL_AR, "label_en": LABEL_EN}


def info() -> dict:
    return {"demo": True, "name": DEMO_NAME, "name_en": DEMO_NAME_EN, "label": LABEL_AR, "label_en": LABEL_EN,
            "retention_hours": int(RETENTION.total_seconds() // 3600), "whatsapp": whatsapp_config(),
            "examples": ["متى أوقات الدوام؟", "كم سعر التبييض؟", "وين موقعكم؟", "أبي أكلم موظف"]}


SCHEDULE_NAME = "live_demo_purge"


async def ensure_schedule(scheduler) -> None:
    """Hourly purge of demo chats older than 24h."""
    import logging
    from uuid import uuid4

    from src.automation.scheduler import ScheduleConfig
    from src.models import Schedule

    try:
        async with scheduler.session_factory() as session:
            exists = (await session.execute(select(Schedule).where(Schedule.name == SCHEDULE_NAME))).scalar_one_or_none()
        if exists is None:
            await scheduler.add_schedule(ScheduleConfig(
                name=SCHEDULE_NAME, target_type="demo_purge", target_id=uuid4(),
                cron_expression="17 * * * *", timezone="Asia/Riyadh"))
    except Exception as e:  # pragma: no cover
        logging.getLogger(__name__).warning("Could not register demo purge schedule: %s", e)
