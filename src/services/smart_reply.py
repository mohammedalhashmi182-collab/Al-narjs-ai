"""Smart auto-reply: the single CEO advisor answers inbound WhatsApp / Telegram /
Messenger messages, gated by the owner's per-channel mode.

Modes (``automation_channel_settings``):

* ``off``    - inbound is still recorded by the channel webhook; no draft, no reply.
* ``review`` - DEFAULT. A draft lands in the owner's queue; nothing reaches the
               customer until the owner approves (optionally after editing).
* ``auto``   - the draft is sent immediately; the row is still kept for audit.

The wording is deterministic Arabic built from ``ceo_advisor.diagnose`` (rules,
optionally refined by the configured LLM, which can only pick catalog agents).
Prices always come from ``catalog`` / ``payments``, never from a model.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings
from src.models import AcquisitionLead, LeadEvent
from src.models.automation import (
    CHANNEL_MODES,
    CHANNELS,
    DEFAULT_CHANNEL_MODE,
    ChannelSetting,
    ReplyDraft,
)
from src.services import catalog, ceo_advisor
from src.services.intent_classify import classify_intent

log = logging.getLogger(__name__)

VISION_LINE = "هدفنا نساعد المنشآت السعودية تتحول رقمياً وتشتغل بكفاءة أعلى، تماشياً مع مستهدفات رؤية 2030."
NO_CLAIMS_LINE = "ما نوعدك بأرقام قبل ما نفهم نشاطك؛ نبدأ صغار ونقيس النتيجة معك."


# --------------------------------------------------------------------------- modes

def _default_mode() -> str:
    mode = (get_settings().automation_default_mode or DEFAULT_CHANNEL_MODE).strip().lower()
    return mode if mode in CHANNEL_MODES else DEFAULT_CHANNEL_MODE


async def get_mode(session: AsyncSession, channel: str) -> str:
    row = await session.get(ChannelSetting, channel)
    return row.mode if row is not None and row.mode in CHANNEL_MODES else _default_mode()


async def all_modes(session: AsyncSession) -> dict[str, str]:
    return {ch: await get_mode(session, ch) for ch in CHANNELS}


async def set_mode(session: AsyncSession, channel: str, mode: str) -> str:
    if channel not in CHANNELS:
        raise ValueError(f"unknown channel: {channel}")
    if mode not in CHANNEL_MODES:
        raise ValueError(f"unknown mode: {mode}")
    row = await session.get(ChannelSetting, channel)
    if row is None:
        session.add(ChannelSetting(channel=channel, mode=mode))
    else:
        row.mode = mode
    await session.flush()
    return mode


# --------------------------------------------------------------------------- wording

def _sar(halalas: int) -> str:
    return f"{halalas // 100:,}"


def plan_lines(plan_key: str, addons: int = 0) -> str:
    key = catalog.purchasable_plan_key(plan_key)
    pkg = catalog.PACKAGES[key]
    monthly = catalog.plan_amount(key, "monthly", addons)
    annual = catalog.plan_amount(key, "annual", addons)
    extra = f" مع {addons} وكيل إضافي" if addons else ""
    return (
        f"باقة «{pkg['name']}»{extra}: {_sar(monthly)} ريال شهرياً، "
        f"أو {_sar(annual)} ريال سنوياً (تدفع 10 أشهر وتاخذ 12). "
        f"تشمل {pkg['limits']['conversations']:,} محادثة ذكية شهرياً"
        + (f" و{pkg['limits']['voice_minutes']} دقيقة صوت عند إطلاق الوكيل الصوتي (قريباً)" if pkg['limits']['voice_minutes'] else "")
        + f"، ورسوم ميتا مشمولة حتى {_sar(pkg['limits']['meta_cap'])} ريال. "
        f"وتقدر تضيف أي وكيل إضافي بـ {_sar(catalog.ADDON_AGENT['amount'])} ريال شهرياً. "
        "ضريبة القيمة المضافة موضّحة في الفاتورة."
    )


def ladder_text() -> str:
    rows = []
    for _key, pkg in catalog.PACKAGES.items():
        rows.append(f"• {pkg['name']}: {_sar(pkg['amount'])} ريال/شهر – "
                    f"{pkg['limits']['conversations']:,} محادثة")
    return "\n".join(rows)


def compose_offer(result: dict) -> str:
    plan = result["plan"]
    titles = "، ".join(a.get("title_ar", a.get("slug", "")) for a in result.get("agents", [])[:6])
    diagnosis = (result.get("diagnosis_ar") or "").strip()
    parts = [
        "هلا والله 👋 معك المدير التنفيذي الافتراضي في «النرجس للذكاء الاصطناعي».",
    ]
    if diagnosis:
        parts.append(f"من كلامك فهمت: {diagnosis}")
    if titles:
        parts.append(f"الفريق اللي أرشّحه لك: {titles}.")
    parts.append(plan_lines(plan["key"], int(plan.get("addons") or 0)))
    parts.append(VISION_LINE)
    parts.append(NO_CLAIMS_LINE)
    parts.append("تبي أرسل لك رابط الاشتراك والدفع، ولا تحب نوضّح أكثر عن نشاطك أول؟")
    return "\n\n".join(parts)


def compose_greeting() -> str:
    return "\n\n".join([
        "هلا والله 👋 معك المدير التنفيذي الافتراضي في «النرجس للذكاء الاصطناعي».",
        "عشان أرشّح لك الفريق المناسب: وش نشاطك، ووش أكثر شي متعبك حالياً؟ (تسويق، مبيعات، ردود العملاء، محتوى، متجر…)",
        "باقاتنا الشهرية:\n" + ladder_text(),
        VISION_LINE,
    ])


def compose_closing() -> str:
    return "تمام، نحترم قرارك 🌷 لو احتجتنا مستقبلاً نحن موجودين. يومك سعيد!"


def compose_followup(stage: str, attempt: int, plan_key: str | None, payment_url: str | None) -> str:
    plan = catalog.PACKAGES.get(plan_key or "", {}).get("name", "")
    if stage == "payment_link_sent" and payment_url:
        return (f"هلا مجدداً 👋 حبيت أذكّرك برابط الاشتراك في باقة «{plan}»:\n{payment_url}\n"
                "لو عندك أي سؤال قبل الدفع أنا موجود.")
    if attempt == 0:
        return f"هلا 👋 هل اطّلعت على عرض باقة «{plan}»؟ أقدر أجاوب أي سؤال أو أعدّل الترشيح حسب احتياجك."
    return ("آخر تذكير مني 🙏 لو الوقت مو مناسب الحين ما في مشكلة، "
            "ولو حاب نبدأ أرسل لك رابط الاشتراك مباشرة.")


# --------------------------------------------------------------------------- leads

async def _lead_for(session: AsyncSession, channel: str, recipient: str, lead_id: Any) -> AcquisitionLead:
    if lead_id:
        lead = await session.get(AcquisitionLead, lead_id if isinstance(lead_id, UUID) else UUID(str(lead_id)))
        if lead is not None:
            return lead
    from src.models.automation import LeadPipeline

    pipe = (await session.execute(
        select(LeadPipeline).where(LeadPipeline.channel == channel, LeadPipeline.recipient == recipient)
    )).scalars().first()
    if pipe is not None:
        lead = await session.get(AcquisitionLead, pipe.lead_id)
        if lead is not None:
            return lead
    lead = AcquisitionLead(
        company_name=f"عميل {channel} {recipient[-6:]}",
        phone=recipient[:32] if channel == "whatsapp" else None,
        source=f"{channel}_inbound",
        segment="unknown",
        lead_status="REPLIED",
    )
    session.add(lead)
    await session.flush()
    return lead


# --------------------------------------------------------------------------- sending

async def deliver(session: AsyncSession, channel: str, recipient: str, text: str, lead_id: Any) -> dict:
    """The only path that talks to a customer. Called on approve or in auto mode."""
    if channel == "telegram":
        from src.services import telegram_sender

        return await telegram_sender.send_now(session, lead_id=lead_id, chat_id=recipient, text=text)
    if channel == "whatsapp":
        from src.services import whatsapp_sender

        return await whatsapp_sender.send_now(session, lead_id=lead_id, phone=recipient, text=text)
    if channel == "messenger":
        from src.services import messenger

        return await messenger.send_text(recipient, text)
    return {"ok": False, "error": f"unknown channel {channel}"}


async def _deliver_outside_window(session: AsyncSession, draft: ReplyDraft, text: str) -> dict | None:
    """A WhatsApp follow-up / payment link outside the 24h customer window goes
    through ``wa_templates`` (approved Meta template, else a manual fallback).
    Returns None when the normal path applies."""
    if draft.channel != "whatsapp" or draft.kind not in ("followup", "payment_link"):
        return None
    from src.services import wa_templates, whatsapp_sender

    if not whatsapp_sender.is_enabled() or await wa_templates.within_window(session, draft.recipient):
        return None
    return await wa_templates.send_business_initiated(
        session, phone=draft.recipient, purpose=draft.kind, text=text, lead_id=draft.lead_id,
        params=wa_templates.params_from_text(draft.kind, text))


def _sent_ok(result: dict) -> bool:
    return bool(result.get("ok") is True or result.get("status") == "sent")


async def _send_draft(session: AsyncSession, draft: ReplyDraft, *, base_url: str | None = None) -> ReplyDraft:
    from src.services import lead_pipeline

    text = draft.final_text or draft.draft_text
    if draft.kind == "payment_link":
        try:
            url = await lead_pipeline.ensure_payment_link(session, draft, base_url=base_url)
        except Exception as e:  # noqa: BLE001 - surfaced to the owner, nothing sent
            draft.status = "failed"
            draft.send_result = {"ok": False, "error": f"payment link: {str(e)[:200]}"}
            draft.decided_at = datetime.now(UTC)
            await session.flush()
            return draft
        text = text.replace("{payment_url}", url)
        draft.final_text = text
    result = await _deliver_outside_window(session, draft, text)
    if result is None:
        result = await deliver(session, draft.channel, draft.recipient, text, draft.lead_id)
    draft.send_result = {k: v for k, v in result.items() if k in ("ok", "error", "error_code", "message_id", "provider_message_id", "status", "id")}
    draft.status = "sent" if _sent_ok(result) else "failed"
    draft.decided_at = datetime.now(UTC)
    if draft.status == "sent":
        await lead_pipeline.on_draft_sent(session, draft)
    if draft.lead_id:
        session.add(LeadEvent(
            lead_id=draft.lead_id, event_type="auto_reply_sent" if draft.status == "sent" else "auto_reply_failed",
            channel=draft.channel, message=text[:2000], note=f"draft={draft.id} kind={draft.kind}",
        ))
    await session.flush()
    return draft


async def queue_or_send(session: AsyncSession, draft: ReplyDraft, *, base_url: str | None = None) -> ReplyDraft:
    qa = {"flagged": False}
    try:
        from src.services import draft_qa

        qa = await draft_qa.score_and_tag(session, draft)
    except Exception:  # noqa: BLE001 - QA must never block a reply
        log.warning("draft QA failed", exc_info=True)
    session.add(draft)
    await session.flush()
    if qa.get("flagged"):
        return draft  # low QA score: stays pending in the review queue even in auto mode
    if await get_mode(session, draft.channel) == "auto":
        await _send_draft(session, draft, base_url=base_url)
    return draft


# --------------------------------------------------------------------------- inbound

async def handle_inbound(
    session: AsyncSession,
    *,
    channel: str,
    recipient: Any,
    text: str,
    lead_id: Any = None,
    provider=None,
    base_url: str | None = None,
    override_text: str | None = None,
) -> ReplyDraft | None:
    """Draft (and in auto mode send) the CEO advisor's reply to one inbound message."""
    if channel not in CHANNELS or recipient is None:
        return None
    recipient = str(recipient)
    text = (text or "").strip()
    mode = await get_mode(session, channel)
    if mode == "off" or not text:
        return None

    from src.services import lead_pipeline

    lead = await _lead_for(session, channel, recipient, lead_id)
    pipe = await lead_pipeline.ensure(session, lead, channel=channel, recipient=recipient)
    lead_pipeline.on_inbound(pipe)
    if lead.opt_out:
        return None

    intent, _objection = classify_intent(text)
    meta: dict = {"intent": intent}
    kind, plan_key = "reply", pipe.plan_key

    if override_text:
        body = override_text
        meta["override"] = True
    elif intent == "OPT_OUT":
        lead.opt_out = True
        lead_pipeline.set_stage(pipe, "lost", "opt_out")
        return None
    if intent == "NOT_INTERESTED":
        lead_pipeline.set_stage(pipe, "lost", "not_interested")
        body = compose_closing()
    elif intent == "READY_TO_BUY" and pipe.plan_key:
        kind = "payment_link"
        plan_key = catalog.purchasable_plan_key(pipe.plan_key)
        pkg = catalog.PACKAGES.get(plan_key) or catalog.PACKAGES[catalog.RECOMMENDED_PACKAGE]
        body = (f"ممتاز 🎉 هذا رابط الاشتراك الآمن (ميسّر) لباقة «{pkg['name']}»:\n{{payment_url}}\n"
                "بعد الدفع نبدأ تجهيز فريقك مباشرة.")
    else:
        try:
            problem = ceo_advisor.validate_problem(text)
        except ValueError:
            problem = ""
        diag = ceo_advisor.diagnose_rules(problem) if problem else None
        if problem and diag and (diag.needs or diag.full_company):
            result = await ceo_advisor.diagnose(problem, provider=provider, locale="ar")
            plan_key = result["plan"]["key"]
            meta.update(agents=[a["slug"] for a in result["agents"]], source=result["source"],
                        addons=result["plan"].get("addons", 0))
            body = compose_offer(result)
            pipe.plan_key = plan_key
            lead.suggested_package = plan_key
            lead_pipeline.set_stage(pipe, "qualified", "diagnosed")
        else:
            kb_hits = await _kb_hits(session, text)
            if kb_hits:
                body = compose_kb_answer(kb_hits)
                meta["kb"] = [h["title"] for h in kb_hits]
                draft = ReplyDraft(
                    channel=channel, recipient=recipient, lead_id=lead.id, kind=kind,
                    inbound_text=text[:4000], draft_text=body, plan_key=plan_key, meta=meta, status="pending",
                )
                return await queue_or_send(session, draft, base_url=base_url)
            if await _greeted_recently(session, channel, recipient):
                return None  # do not repeat the greeting for every "ok" / "طيب"
            body = compose_greeting()
            meta["greeting"] = True

    draft = ReplyDraft(
        channel=channel, recipient=recipient, lead_id=lead.id, kind=kind,
        inbound_text=text[:4000], draft_text=body, plan_key=plan_key, meta=meta, status="pending",
    )
    return await queue_or_send(session, draft, base_url=base_url)


async def _kb_hits(session: AsyncSession, text: str) -> list[dict]:
    """Owner knowledge-base passages answering this message (empty on any error)."""
    try:
        from src.services.agent_tools import knowledge_base

        hits = await knowledge_base.search(session, text, project_id=None, k=2)
    except Exception:
        hits = []
    if hits:
        return hits
    # Owner-approved policies answer refund / support / trial / data questions
    # even before the owner FAQ has been seeded into the database.
    from src.services import policies
    from src.services.agent_tools import knowledge_base

    paras = [p for p in policies.OWNER_FAQ_AR.split("\n\n") if p.strip()]
    return knowledge_base.search_texts([(policies.OWNER_FAQ_TITLE, p) for p in paras], text, k=2)


def compose_kb_answer(hits: list[dict]) -> str:
    """Reply grounded only in the owner's FAQ. Still a draft: review mode applies."""
    top = hits[0]["text"].strip()
    if len(top) > 600:
        top = top[:600].rsplit(" ", 1)[0] + "…"
    return f"أهلًا بك 🌿\n{top}\n\nإذا عندك سؤال ثاني أنا حاضر."


async def _greeted_recently(session: AsyncSession, channel: str, recipient: str) -> bool:
    from datetime import timedelta

    since = datetime.now(UTC) - timedelta(hours=24)
    rows = (await session.execute(select(ReplyDraft).where(
        ReplyDraft.channel == channel, ReplyDraft.recipient == recipient, ReplyDraft.kind == "reply",
        ReplyDraft.status.in_(("pending", "sent")),
    ).order_by(ReplyDraft.created_at.desc()).limit(5))).scalars()
    for d in rows:
        created = d.created_at if d.created_at is None or d.created_at.tzinfo else d.created_at.replace(tzinfo=UTC)
        if created is None or created >= since:
            return True
    return False


async def has_contacted(session: AsyncSession, channel: str, recipient: str) -> bool:
    row = (await session.execute(select(ReplyDraft.id).where(
        ReplyDraft.channel == channel, ReplyDraft.recipient == str(recipient)).limit(1))).first()
    return row is not None


async def safe_handle_inbound(session_factory, **kwargs) -> None:
    """Webhook hook: own session, never raises (the webhook must still answer 200)."""
    try:
        async with session_factory() as session:
            await handle_inbound(session, **kwargs)
            await session.commit()
    except Exception:  # noqa: BLE001
        log.exception("smart reply failed for %s", kwargs.get("channel"))


# --------------------------------------------------------------------------- owner decisions

async def list_drafts(session: AsyncSession, status: str | None = "pending", limit: int = 100) -> list[ReplyDraft]:
    # Owner queue = Al-Narjis's own conversations only; tenant drafts live in each customer's portal.
    q = select(ReplyDraft).where(ReplyDraft.project_id.is_(None)).order_by(ReplyDraft.created_at.desc()).limit(limit)
    if status:
        q = q.where(ReplyDraft.status == status)
    return list((await session.execute(q)).scalars())


async def _pending(session: AsyncSession, draft_id: UUID) -> ReplyDraft:
    draft = await session.get(ReplyDraft, draft_id)
    if draft is None or draft.project_id is not None:
        raise LookupError("draft not found")
    if draft.status != "pending":
        raise ValueError(f"draft already {draft.status}")
    return draft


async def approve(session: AsyncSession, draft_id: UUID, *, text: str | None = None, base_url: str | None = None) -> ReplyDraft:
    draft = await _pending(session, draft_id)
    if text is not None and text.strip():
        draft.final_text = text.strip()[:4000]
    return await _send_draft(session, draft, base_url=base_url)


async def edit(session: AsyncSession, draft_id: UUID, text: str) -> ReplyDraft:
    draft = await _pending(session, draft_id)
    if not (text or "").strip():
        raise ValueError("empty text")
    draft.final_text = text.strip()[:4000]
    try:
        from src.services import draft_qa

        await draft_qa.score_and_tag(session, draft)
    except Exception:  # noqa: BLE001
        log.warning("draft QA failed", exc_info=True)
    await session.flush()
    return draft


async def reject(session: AsyncSession, draft_id: UUID, reason: str | None = None) -> ReplyDraft:
    draft = await _pending(session, draft_id)
    draft.status = "rejected"
    draft.decided_at = datetime.now(UTC)
    draft.meta = {**(draft.meta or {}), "reject_reason": (reason or "")[:200]}
    await session.flush()
    return draft


def draft_to_dict(d: ReplyDraft) -> dict:
    return {
        "id": str(d.id), "channel": d.channel, "recipient": d.recipient,
        "lead_id": str(d.lead_id) if d.lead_id else None, "kind": d.kind,
        "inbound_text": d.inbound_text, "draft_text": d.draft_text, "final_text": d.final_text,
        "status": d.status, "plan_key": d.plan_key, "meta": d.meta or {}, "send_result": d.send_result,
        "qa_score": ((d.meta or {}).get("qa") or {}).get("score"),
        "qa_flagged": bool(((d.meta or {}).get("qa") or {}).get("flagged")),
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "decided_at": d.decided_at.isoformat() if d.decided_at else None,
    }
