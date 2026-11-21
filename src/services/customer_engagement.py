"""CEO-led intake: idea, clarification, customer-confirmed brief, specialist drafts.

The conversation steps are deterministic so a missing model key still walks the
customer from intake to a visible draft. Specialist bodies use the existing
model fallback chain when a provider client is configured, and otherwise store
an explicit degraded draft that quotes only the confirmed brief.
"""

from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.services import catalog

log = logging.getLogger(__name__)

CEO_SLUG = catalog.CEO_SLUG
_MIN_IDEA = 12
_MAX_TEXT = 2000
_FOLLOWUP_READY = ("brief_pending", "producing", "ready")

# Order is the match priority. The first hit wins.
_KINDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("concept", ("تصميم", "هوي", "شعار", "بصري", "واجه", "visual", "logo", "brand")),
    ("store", ("متجر", "سلة", "زد", "منتج", "salla", "zid", "store")),
    ("marketing", ("اعلان", "إعلان", "تسويق", "سوشيال", "محتوى", "campaign", "marketing")),
    ("software", ("تطبيق", "برنامج", "موقع", "برمج", "app", "software", "website")),
    ("proposal", ("عرض سعر", "مقترح", "proposal", "خطة عمل")),
)

_ROSTER: dict[str, tuple[str, ...]] = {
    "concept": ("product_designer", "prototype_engineer"),
    "store": ("store_manager", "product_describer"),
    "marketing": ("marketing_agent", "ad_writer"),
    "software": ("software_engineer", "prototype_engineer"),
    "proposal": ("business_ideas", "content_writer"),
}

_KIND_LABEL = {
    "ar": {
        "concept": "تصور بصري مبدئي",
        "store": "مسودة وصف المتجر والمنتجات",
        "marketing": "مسودة خطة محتوى وإعلان",
        "software": "مسودة تصور تقني",
        "proposal": "مسودة عرض العمل",
    },
    "en": {
        "concept": "Initial visual concept",
        "store": "Store and product draft",
        "marketing": "Content and ad draft",
        "software": "Technical concept draft",
        "proposal": "Work proposal draft",
    },
}

_AUDIENCE_HINT = re.compile(
    r"(?:يستهدف|موجه إلى|الجمهور|للعملاء|لأصحاب|لعملاء)\s*[:：]?\s*([^\n،.]{2,80})"
)
_APPROVE = re.compile(
    r"^\s*(موافق|اوافق|أوافق|أعتمد|اعتمد|أؤكد|اؤكد|أكد|اكد|اعتماد|تمام|نعم|ok|okay|confirm|approved|approve|go ahead)\s*[.!]?\s*$",
    re.I,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _lang(locale: str) -> str:
    return "en" if str(locale).lower().startswith("en") else "ar"


def _kind(text: str) -> str:
    folded = (text or "").lower()
    for name, words in _KINDS:
        if any(word.lower() in folded for word in words):
            return name
    return ""


def _audience_hint(text: str) -> str:
    match = _AUDIENCE_HINT.search(text or "")
    return match.group(1).strip()[:300] if match else ""


def _label(kind: str, locale: str) -> str:
    return _KIND_LABEL[_lang(locale)].get(kind or "proposal", _KIND_LABEL[_lang(locale)]["proposal"])


def _say(locale: str, ar: str, en: str) -> str:
    return en if _lang(locale) == "en" else ar


def brief_text(brief: dict, locale: str, *, revised: bool = False) -> str:
    kind = brief.get("deliverable_kind") or "proposal"
    lines = [
        _say(locale, "حدّثت الموجز." if revised else "هذا الموجز الذي سأعتمده:",
             "I updated the brief." if revised else "This is the brief I will lock:"),
        _say(locale, f"- الفكرة: {brief.get('idea') or '—'}", f"- Idea: {brief.get('idea') or '—'}"),
        _say(locale, f"- الجمهور: {brief.get('audience') or '—'}", f"- Audience: {brief.get('audience') or '—'}"),
        _say(locale, f"- أول مخرج: {_label(kind, locale)}", f"- First deliverable: {_label(kind, locale)}"),
    ]
    if brief.get("constraints"):
        lines.append(_say(locale, f"- قيد ذكرته: {brief['constraints']}", f"- Constraint you added: {brief['constraints']}"))
    lines.append(_say(
        locale,
        "اكتب «موافق» لاعتماد الموجز وبدء تجهيز المسودات، أو اكتب التعديل.",
        "Reply “confirm” to approve the brief and start the drafts, or write the change.",
    ))
    return "\n".join(lines)


def _ask_idea(locale: str) -> str:
    return _say(
        locale,
        "أنا الرئيس التنفيذي. صف فكرتك في جملة أو جملتين: ماذا تريد أن نجهّز؟",
        "I am the chief executive. Describe your idea in one or two sentences: what should we prepare?",
    )


def _ask_audience(locale: str) -> str:
    return _say(
        locale,
        "لمن هذا العمل؟ اذكر العميل أو القطاع.",
        "Who is this for? Name the customer or the sector.",
    )


def _ask_deliverable(locale: str) -> str:
    return _say(
        locale,
        "ما أول مخرج تبيه؟ تصور بصري، مسودة عرض، محتوى، متجر، أو تصور تقني.",
        "What should we prepare first? A visual concept, a proposal draft, content, a store draft, or a technical concept.",
    )


def _ready_reply(locale: str, names: list[str]) -> str:
    team = "، ".join(names) if _lang(locale) == "ar" else ", ".join(names)
    return _say(
        locale,
        f"اعتمدت الموجز. بدأ المختصون تجهيز المسودات: {team}. المسودات ظاهرة في هذه الصفحة، والمالك يتابعها في سجل المتابعة.",
        f"The brief is confirmed. Specialists started the drafts: {team}. The drafts are on this page, and the owner follows them in the pipeline.",
    )


def advance(brief: dict, text: str, stage: str, locale: str) -> tuple[str, dict, str]:
    """One customer turn. Returns ``(stage, brief, reply)`` before any model call."""
    brief = dict(brief or {})
    text = (text or "").strip()
    if stage == "ready":
        return stage, brief, _say(
            locale,
            "الموجز معتمد والمسودات جاهزة للمراجعة في هذه الصفحة.",
            "The brief is confirmed and the drafts are ready for review on this page.",
        )
    if stage == "brief_pending" and _APPROVE.match(text):
        return "producing", brief, ""
    if stage == "brief_pending":
        extra = (brief.get("constraints") or "").strip()
        brief["constraints"] = (extra + "\n" + text).strip()[:1000]
        return "brief_pending", brief, brief_text(brief, locale, revised=True)
    if not brief.get("idea"):
        if len(text) < _MIN_IDEA:
            return "intake", brief, _ask_idea(locale)
        brief["idea"] = text[:1000]
        brief["deliverable_kind"] = _kind(text)
        hint = _audience_hint(text)
        if hint:
            brief["audience"] = hint
        if not brief.get("audience"):
            return "clarification", brief, _ask_audience(locale)
        if not brief.get("deliverable_kind"):
            return "clarification", brief, _ask_deliverable(locale)
        return "brief_pending", brief, brief_text(brief, locale)
    if not brief.get("audience"):
        brief["audience"] = text[:300]
        if not brief.get("deliverable_kind"):
            found = _kind(text)
            if found:
                brief["deliverable_kind"] = found
            else:
                return "clarification", brief, _ask_deliverable(locale)
        return "brief_pending", brief, brief_text(brief, locale)
    if not brief.get("deliverable_kind"):
        brief["deliverable_kind"] = _kind(text) or "proposal"
        brief["deliverable_note"] = text[:300]
        return "brief_pending", brief, brief_text(brief, locale)
    return "brief_pending", brief, brief_text(brief, locale)


def roster_for(kind: str) -> tuple[str, ...]:
    names = _ROSTER.get(kind or "proposal", _ROSTER["proposal"])
    return tuple(slug for slug in (*names, "quality_gate") if slug in catalog.EMPLOYEES)


def _title(slug: str, locale: str) -> str:
    row = catalog.EMPLOYEES.get(slug) or {}
    if _lang(locale) == "en":
        return row.get("title_en") or slug
    return row.get("title_ar") or slug


def degraded_body(slug: str, brief: dict, locale: str) -> str:
    """Draft that quotes the brief only. It says the model was not called."""
    title = _title(slug, locale)
    kind = _label(brief.get("deliverable_kind") or "proposal", locale)
    if slug == "quality_gate":
        return _say(
            locale,
            "مراجعة بوابة الجودة دون نموذج لغة:\n"
            "- الموجز معتمد من العميل.\n"
            "- المسودات تقتصر على ما كتبه العميل.\n"
            "- لا تُرسل كعمل نهائي قبل مراجعة المالك.\n"
            f"- الفكرة: {brief.get('idea') or '—'}\n"
            f"- الجمهور: {brief.get('audience') or '—'}",
            "Quality-gate review without a language model:\n"
            "- The customer confirmed the brief.\n"
            "- Drafts use only what the customer wrote.\n"
            "- Do not send this as final work before the owner reviews it.\n"
            f"- Idea: {brief.get('idea') or '—'}\n"
            f"- Audience: {brief.get('audience') or '—'}",
        )
    return _say(
        locale,
        f"مسودة أولية من {title}. لم يُستدعَ نموذج اللغة (لا يوجد مزود مهيأ أو تعذّر الرد).\n"
        f"الفكرة: {brief.get('idea') or '—'}\n"
        f"الجمهور: {brief.get('audience') or '—'}\n"
        f"المخرج: {kind}\n"
        f"قيد: {brief.get('constraints') or '—'}\n"
        "هذه مسودة للمراجعة، وليست عملاً نهائياً.",
        f"Initial draft from {title}. No language model was called (none configured, or the call failed).\n"
        f"Idea: {brief.get('idea') or '—'}\n"
        f"Audience: {brief.get('audience') or '—'}\n"
        f"Deliverable: {kind}\n"
        f"Constraint: {brief.get('constraints') or '—'}\n"
        "This is a review draft, not final work.",
    )


async def _complete(provider: Any, *, system: str, prompt: str) -> Optional[str]:
    if provider is None or not getattr(provider, "_clients", None):
        return None
    try:
        from src.core.model_provider import ModelRequest

        result = await provider.complete_with_fallback(
            "gemini",
            ModelRequest(prompt=prompt, system_prompt=system, temperature=0.3, max_tokens=1200),
        )
    except Exception as exc:  # noqa: BLE001 — degrade; do not log the provider body
        log.warning("engagement model unavailable (%s)", type(exc).__name__)
        return None
    text = (getattr(result, "content", "") or "").strip()
    return text or None


def _prompt(slug: str, brief: dict, locale: str) -> tuple[str, str]:
    system = (
        "You draft for Al-Narjis (النرجس), a Saudi business. Use only the confirmed brief. "
        "Do not invent prices, revenue, testimonials, customer names, or legal conclusions. "
        "If a fact is missing, say it is missing. Reply in the customer's language."
    )
    prompt = (
        f"agent={slug}\nlocale={locale}\n"
        f"idea={brief.get('idea') or ''}\n"
        f"audience={brief.get('audience') or ''}\n"
        f"deliverable={_label(brief.get('deliverable_kind') or 'proposal', locale)}\n"
        f"constraints={brief.get('constraints') or ''}\n"
        "Write the first draft the owner will review."
    )
    return system, prompt


async def _draft(provider: Any, slug: str, brief: dict, locale: str) -> dict:
    system, prompt = _prompt(slug, brief, locale)
    text = await _complete(provider, system=system, prompt=prompt)
    if text:
        return {
            "slug": slug,
            "title": _title(slug, locale),
            "status": "ready",
            "degraded": False,
            "body": text[:8000],
        }
    return {
        "slug": slug,
        "title": _title(slug, locale),
        "status": "ready",
        "degraded": True,
        "body": degraded_body(slug, brief, locale),
    }


def _coordinator_note(locale: str, names: list[str]) -> dict:
    team = "، ".join(names) if _lang(locale) == "ar" else ", ".join(names)
    return {
        "slug": CEO_SLUG,
        "title": _title(CEO_SLUG, locale),
        "status": "ready",
        "degraded": False,
        "role": "coordinator",
        "body": _say(
            locale,
            f"استلم الرئيس التنفيذي الموجز المعتمد ووزّع التجهيز على: {team}.",
            f"The chief executive accepted the brief and assigned: {team}.",
        ),
    }


async def _upsert_task(session: AsyncSession, *, key: str, title: str, slug: str, body: str, parent: str | None, engagement_id: str) -> None:
    from src.models import Task

    existing = (await session.execute(select(Task).where(Task.key == key))).scalar_one_or_none()
    result = {"body": body[:8000], "engagement_id": engagement_id}
    if existing is not None:
        existing.result = result
        existing.status = "completed"
        return
    session.add(Task(
        key=key,
        title=title[:512],
        description=body[:4000],
        parent_key=parent,
        source="customer_brief",
        status="completed",
        priority=170,
        owner_agent=slug,
        department="customer_delivery",
        evidence={"handler": "customer_brief", "engagement_id": engagement_id},
        result=result,
        learning="مسودة للمراجعة. لم يُرسل شيء للعميل كعمل نهائي.",
    ))


async def produce(session: AsyncSession, engagement, provider: Any) -> list[dict]:
    """Fan out the confirmed brief. Safe to call again: task keys do not duplicate."""
    brief = dict(engagement.brief or {})
    locale = engagement.locale or "ar"
    kind = brief.get("deliverable_kind") or "proposal"
    slugs = roster_for(kind)
    drafts = [await _draft(provider, slug, brief, locale) for slug in slugs]
    names = [item["title"] for item in drafts if item["slug"] != "quality_gate"]
    note = _coordinator_note(locale, names)
    items = [note, *drafts]
    parent = f"engagement:{engagement.id}:{CEO_SLUG}"
    await _upsert_task(
        session, key=parent, title=note["title"], slug=CEO_SLUG,
        body=note["body"], parent=None, engagement_id=str(engagement.id),
    )
    for item in drafts:
        await _upsert_task(
            session,
            key=f"engagement:{engagement.id}:{item['slug']}",
            title=item["title"],
            slug=item["slug"],
            body=item["body"],
            parent=parent,
            engagement_id=str(engagement.id),
        )
    engagement.deliverables = items
    engagement.stage = "ready"
    return items


def _merge(lead, key: str, value: dict) -> None:
    raw = dict(lead.raw_data or {})
    raw[key] = value
    lead.raw_data = raw


async def _sync_lead(session: AsyncSession, engagement, *, name: str = "", phone: str = "", email: str = "") -> None:
    from src.models import AcquisitionLead, LeadEvent
    from src.services.lead_normalize import is_valid_email, normalize_phone

    lead = None
    if engagement.lead_id:
        lead = await session.get(AcquisitionLead, engagement.lead_id)
    if lead is None:
        idea = ((engagement.brief or {}).get("idea") or "").strip()
        company = (name or idea or "طلب عبر الرئيس التنفيذي")[:80]
        norm = normalize_phone(phone) if phone else None
        lead = AcquisitionLead(
            company_name=company[:512] or "طلب عبر الرئيس التنفيذي",
            contact_name=(name or "")[:512] or None,
            phone=norm,
            phone_raw=(phone or "")[:64] or None,
            email=email[:255] if email and is_valid_email(email) else None,
            source="ceo_brief",
            segment="unknown",
            lead_status="NEW",
            priority="MEDIUM",
            sales_representative="owner",
            dedup_key=f"ceo_brief:{engagement.public_token}",
        )
        session.add(lead)
        await session.flush()
        engagement.lead_id = lead.id
        session.add(LeadEvent(
            lead_id=lead.id,
            event_type="engagement",
            channel="website",
            status_before="NEW",
            status_after=lead.lead_status,
            message=(idea or company)[:500],
            note="stage=intake",
        ))
    stage = engagement.stage or "intake"
    lead.followup_stage = stage[:50]
    lead.last_message = (_last_user(engagement) or lead.last_message or "")[:4000] or None
    if stage in _FOLLOWUP_READY:
        lead.next_followup_at = _now()
        lead.priority = "HIGH"
        reasons = list(lead.priority_reason or [])
        reason = "موجز رئيس تنفيذي بانتظار المتابعة"
        if reason not in reasons:
            reasons.append(reason)
            lead.priority_reason = reasons
    _merge(lead, "engagement", {"id": str(engagement.id), "stage": stage})
    session.add(LeadEvent(
        lead_id=lead.id,
        event_type="engagement",
        channel="website",
        status_before=lead.lead_status,
        status_after=lead.lead_status,
        note=f"stage={stage}",
    ))


def _last_user(engagement) -> str:
    for message in reversed(engagement.messages or []):
        if message.get("role") == "user":
            return str(message.get("content") or "")
    return ""


async def open_engagement(
    session: AsyncSession,
    *,
    message: str,
    locale: str = "ar",
    name: str = "",
    phone: str = "",
    email: str = "",
    provider: Any = None,
):
    from src.models.engagement import CustomerEngagement

    engagement = CustomerEngagement(
        public_token=secrets.token_urlsafe(24),
        stage="intake",
        locale=_lang(locale),
        messages=[],
        brief={},
        deliverables=[],
    )
    session.add(engagement)
    await session.flush()
    await apply_turn(session, engagement, message, provider=provider, name=name, phone=phone, email=email)
    return engagement


async def apply_turn(
    session: AsyncSession,
    engagement,
    message: str,
    *,
    provider: Any = None,
    name: str = "",
    phone: str = "",
    email: str = "",
) -> None:
    text = (message or "").strip()[:_MAX_TEXT]
    locale = engagement.locale or "ar"
    messages = list(engagement.messages or [])
    if len([item for item in messages if item.get("role") == "user"]) >= 14 and engagement.stage != "ready":
        reply = _say(
            locale,
            "وصلنا حد هذه المحادثة. المالك يكمل المتابعة عبر AlNarjisai@gmail.com.",
            "This conversation reached its limit. The owner continues by email at AlNarjisai@gmail.com.",
        )
        messages.append({"role": "user", "content": text})
        messages.append({"role": "assistant", "content": reply})
        engagement.messages = messages
        await _sync_lead(session, engagement, name=name, phone=phone, email=email)
        return
    stage, brief, reply = advance(dict(engagement.brief or {}), text, engagement.stage or "intake", locale)
    engagement.brief = brief
    engagement.stage = stage
    messages.append({"role": "user", "content": text})
    if stage == "producing":
        items = await produce(session, engagement, provider)
        names = [item["title"] for item in items if item.get("role") != "coordinator" and item["slug"] != "quality_gate"]
        reply = _ready_reply(locale, names)
    messages.append({"role": "assistant", "content": reply})
    engagement.messages = messages[-24:]
    await _sync_lead(session, engagement, name=name, phone=phone, email=email)


def public_view(engagement) -> dict:
    items = engagement.deliverables or []
    return {
        "token": engagement.public_token,
        "stage": engagement.stage,
        "locale": engagement.locale,
        "reply": _last_assistant(engagement),
        "messages": [
            {"role": item.get("role"), "content": item.get("content")}
            for item in (engagement.messages or [])
            if item.get("role") in ("user", "assistant")
        ],
        "brief": _public_brief(engagement.brief or {}, engagement.locale or "ar") if engagement.stage in ("brief_pending", "producing", "ready") else None,
        "deliverables": [
            {"slug": item.get("slug"), "title": item.get("title"), "body": item.get("body"), "degraded": bool(item.get("degraded"))}
            for item in items
        ],
        "degraded": any(bool(item.get("degraded")) for item in items),
    }


def _public_brief(brief: dict, locale: str) -> dict:
    kind = brief.get("deliverable_kind") or ""
    return {
        "idea": brief.get("idea") or "",
        "audience": brief.get("audience") or "",
        "deliverable": _label(kind, locale) if kind else "",
        "constraints": brief.get("constraints") or "",
    }


def _last_assistant(engagement) -> str:
    for message in reversed(engagement.messages or []):
        if message.get("role") == "assistant":
            return str(message.get("content") or "")
    return ""


def owner_view(engagement) -> dict:
    view = public_view(engagement)
    view["id"] = str(engagement.id)
    view["lead_id"] = str(engagement.lead_id) if engagement.lead_id else None
    view["updated_at"] = engagement.updated_at.isoformat() if engagement.updated_at else None
    return view


async def by_token(session: AsyncSession, token: str):
    from src.models.engagement import CustomerEngagement

    if not token or len(token) > 64:
        return None
    return (
        await session.execute(select(CustomerEngagement).where(CustomerEngagement.public_token == token))
    ).scalar_one_or_none()


async def list_recent(session: AsyncSession, limit: int = 50) -> list[dict]:
    from src.models.engagement import CustomerEngagement

    rows = (
        await session.execute(
            select(CustomerEngagement).order_by(CustomerEngagement.created_at.desc()).limit(limit)
        )
    ).scalars().all()
    return [owner_view(row) for row in rows]

