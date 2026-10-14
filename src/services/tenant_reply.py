"""Tenant Reply Agent: the live WhatsApp agent of one *customer* project.

Inbound traffic on a subscriber's own linked number
(``ClientProject.wa_phone_number_id``) is routed here instead of Al-Narjis's
sales pipeline. Rules:

* Answers come only from that project's own knowledge base (``KnowledgeDoc``
  rows with ``project_id``). No answer → polite human handoff, never a guess.
* The reply is written by the LLM (``compose_llm_answer``) grounded ONLY in the
  retrieved snippets. It is rejected and the safe verbatim-snippet reply is used
  instead when the LLM is unavailable/errors, the reply is empty or too long,
  pitches Al-Narjis, or contains a number or link that is not in the snippets.
  If the LLM says the snippets do not answer the question → human handoff.
* Never pitches Al-Narjis plans or payment links (``contains_pitch`` guard).
* Never creates ``AcquisitionLead`` / ``LeadPipeline`` rows. The end-customer
  is a ``TenantContact`` of the project.
* Drafts are ``ReplyDraft`` rows tagged ``project_id`` and wait in the
  customer's portal review queue (``reply_mode`` default ``review``). Only
  ``auto`` sends without a human, and only from the customer's own number
  with the customer's own token; without a token, replies stay queued.
* Usage metering is untouched (``whatsapp_webhook`` meters before routing).
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
from datetime import UTC, datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.models import ClientProject
from src.models.automation import ReplyDraft
from src.models.tenant import TenantContact

from .intent_classify import classify_intent

log = logging.getLogger(__name__)

CHANNEL = "whatsapp"
MODES = ("off", "review", "auto")
DEFAULT_MODE = "review"

HANDOFF_WORDS = (
    "موظف", "انسان", "إنسان", "بشري", "شخص حقيقي", "خدمة العملاء", "المدير", "مسؤول", "شكوى", "اشتكي", "أشتكي",
    "human", "agent", "representative", "manager", "complaint",
)


# --------------------------------------------------------------------------- no-pitch guard

def _pitch_markers() -> list[str]:
    from src.services import catalog

    # Specific markers only: a customer's own KB may legitimately use common words.
    marks = ["النرجس للذكاء", "نرجس للذكاء", "narjis ai", "al-narjis", "al-narjs", "alnarjs", "karmaai",
             "moyasar", "{payment_url}", "t.me/alnarjs"]
    for p in catalog.PACKAGES.values():
        for k in ("name", "name_en"):
            v = str(p.get(k) or "").strip()
            if len(v) >= 3:
                marks.append(f"باقة «{v}»" if k == "name" else f"{v} plan")
    return [m.lower() for m in marks]


def contains_pitch(text: str) -> bool:
    t = (text or "").lower()
    return any(m in t for m in _pitch_markers())


# --------------------------------------------------------------------------- composing

def wants_human(text: str) -> bool:
    t = (text or "").lower()
    return any(w in t for w in HANDOFF_WORDS)


def compose_answer(hits: list[dict]) -> str:
    top = hits[0]["text"].strip()
    if len(top) > 700:
        top = top[:700].rsplit(" ", 1)[0] + "…"
    return f"أهلًا بك 🌿\n{top}\n\nإذا عندك سؤال ثاني أنا حاضر."


LLM_NO_ANSWER = "NO_ANSWER"
LLM_MAX_CHARS = 900
LLM_TIMEOUT = 12.0

_SYSTEM = (
    "أنت موظف خدمة عملاء لدى {name} وترد على عملائه في واتساب باللغة العربية بأسلوب ودود ومختصر. "
    "أجب فقط من المقتطفات المرفقة من قاعدة معرفة {name}. لا تضف أي معلومة أو سعر أو رقم أو رابط غير موجود فيها. "
    "لا تذكر أنك ذكاء اصطناعي ولا تذكر أي شركة أخرى. "
    "إذا كانت المقتطفات لا تجيب عن السؤال فاكتب فقط: " + LLM_NO_ANSWER
)


async def _llm_complete(system: str, prompt: str) -> Optional[str]:
    """One LLM call through the app's fallback chain (seam for tests). Never raises."""
    import asyncio

    from src.config.settings import get_settings

    st = get_settings()
    if not (st.gemini_api_key or st.moonshot_api_key or getattr(st, "openrouter_api_key", None)):
        return None
    try:
        from src.core.model_provider import ModelProvider, ModelRequest

        req = ModelRequest(prompt=prompt, system_prompt=system, temperature=0.2, max_tokens=400)
        res = await asyncio.wait_for(ModelProvider(st).complete_with_fallback("gemini", req), LLM_TIMEOUT)
        return (res.content or "").strip() or None
    except Exception as exc:  # noqa: BLE001 - fall back to the verbatim snippet
        log.warning("tenant LLM reply failed: %s", type(exc).__name__)
        return None


_NUM = re.compile(r"\d+(?:[.,]\d+)?")
_URL = re.compile(r"https?://\S+|www\.\S+", re.I)
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def grounded(reply: str, hits: list[dict]) -> bool:
    """Every number and link in the reply must appear in the snippets."""
    source = " ".join(str(h.get("text") or "") for h in hits).translate(_AR_DIGITS)
    out = (reply or "").translate(_AR_DIGITS)
    src_nums = set(_NUM.findall(source))
    if any(n not in src_nums for n in _NUM.findall(out)):
        return False
    return all(u.rstrip(".,)") in source for u in _URL.findall(out))


async def compose_llm_answer(project: ClientProject, question: str, hits: list[dict]) -> tuple[Optional[str], str]:
    """(body, source). source: ``llm`` | ``kb_fallback`` | ``no_answer`` (body None)."""
    name = (project.client_name or "").strip() or "المتجر"
    snippets = "\n\n".join(f"[{i + 1}] {h.get('title') or ''}\n{str(h.get('text') or '')[:1500]}"
                            for i, h in enumerate(hits))
    prompt = f"المقتطفات:\n{snippets}\n\nسؤال العميل:\n{question[:1000]}\n\nالرد:"
    reply = await _llm_complete(_SYSTEM.format(name=name), prompt)
    if reply is None:
        return compose_answer(hits), "kb_fallback"
    if LLM_NO_ANSWER in reply.upper():
        return None, "no_answer"
    if len(reply) > LLM_MAX_CHARS or contains_pitch(reply) or not grounded(reply, hits):
        return compose_answer(hits), "kb_fallback"
    return reply, "llm"


def compose_handoff(project: ClientProject, reason: str) -> str:
    name = (project.client_name or "").strip()
    team = f"فريق {name}" if name else "فريقنا"
    if reason == "requested":
        return f"أبشر 🙏 حوّلت محادثتك إلى {team} وبيتواصلون معك في أقرب وقت."
    return f"شكرًا لسؤالك 🙏 حوّلته إلى {team} للتأكد من الإجابة الصحيحة، وبيردّون عليك قريبًا."


# --------------------------------------------------------------------------- per-project token

def _fernet():
    from cryptography.fernet import Fernet

    key = hashlib.sha256(f"tenant-wa-token:{settings.secret_key}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_token(token: str) -> str:
    return _fernet().encrypt(token.encode()).decode()


def decrypt_token(blob: Optional[str]) -> Optional[str]:
    if not blob:
        return None
    try:
        return _fernet().decrypt(blob.encode()).decode()
    except Exception:
        log.warning("tenant token could not be decrypted (SECRET_KEY rotated?)")
        return None


def can_send(project: ClientProject) -> bool:
    return bool(project.wa_phone_number_id and project.wa_access_token_enc)


def mode_of(project: ClientProject) -> str:
    m = (getattr(project, "reply_mode", None) or DEFAULT_MODE)
    return m if m in MODES else DEFAULT_MODE


# --------------------------------------------------------------------------- routing

def is_tenant_number(project: Optional[ClientProject]) -> bool:
    """A linked number that is not Al-Narjis's own sender number."""
    if project is None or not project.wa_phone_number_id:
        return False
    own = str(settings.whatsapp_phone_number_id or "").strip()
    return not (own and own == str(project.wa_phone_number_id).strip())


def _norm(contact: Any) -> str:
    raw = str(contact or "")
    return (re.sub(r"\D", "", raw) or raw)[:64]


async def touch_contact(session: AsyncSession, project: ClientProject, contact: Any, *, text: str | None = None,
                        name: str | None = None, now: datetime | None = None) -> TenantContact:
    contact = _norm(contact)
    row = (await session.execute(select(TenantContact).where(
        TenantContact.project_id == project.id, TenantContact.channel == CHANNEL, TenantContact.contact == contact,
    ))).scalar_one_or_none()
    if row is None:
        row = TenantContact(project_id=project.id, channel=CHANNEL, contact=contact, message_count=0)
        session.add(row)
    row.message_count = int(row.message_count or 0) + 1
    row.last_inbound_at = now or datetime.now(UTC)
    if text:
        row.last_text = text[:2000]
    if name:
        row.display_name = name[:255]
    await session.flush()
    return row


async def _contact(session: AsyncSession, project_id: UUID, contact: str) -> Optional[TenantContact]:
    return (await session.execute(select(TenantContact).where(
        TenantContact.project_id == project_id, TenantContact.channel == CHANNEL,
        TenantContact.contact == _norm(contact),
    ))).scalar_one_or_none()


async def handle_inbound(session: AsyncSession, *, project: ClientProject, contact: Any, text: str) -> ReplyDraft | None:
    """Draft (and in auto mode send) this project's reply to one inbound text."""
    text = (text or "").strip()
    if not text or project is None or project.status not in ("active", "demo"):
        return None
    mode = mode_of(project)
    if mode == "off":
        return None
    recipient = _norm(contact)
    c = await _contact(session, project.id, recipient) or await touch_contact(session, project, recipient, text=text)

    intent, _ = classify_intent(text)
    if intent == "OPT_OUT":
        c.opt_out = True
        await session.flush()
        return None
    if c.opt_out or c.handoff_at is not None:
        return None  # opted out, or a human of the customer's team owns this chat

    meta: dict = {"intent": intent, "tenant": True}
    kind = "reply"
    if wants_human(text):
        reason = "requested"
    else:
        from src.services.agent_tools import knowledge_base

        try:
            hits = await knowledge_base.search(session, text, project_id=project.id, k=2)
        except Exception:
            log.warning("tenant KB search failed", exc_info=True)
            hits = []
        reason = None if hits else "no_answer"
        if hits:
            body, source = await compose_llm_answer(project, text, hits)
            meta["kb"] = [h["title"] for h in hits]
            meta["answer_source"] = source
            if body is None:
                reason = "no_answer"
            elif contains_pitch(body):
                reason = "guard"
    if reason:
        kind = "handoff"
        body = compose_handoff(project, reason)
        c.handoff_at = datetime.now(UTC)
        c.handoff_reason = reason
        meta["handoff"] = reason

    draft = ReplyDraft(project_id=project.id, channel=CHANNEL, recipient=recipient[:64], lead_id=None, kind=kind,
                       inbound_text=text[:4000], draft_text=body, meta=meta, status="pending")
    session.add(draft)
    await session.flush()
    if mode == "auto":
        await send_draft(session, draft, project)
    return draft


async def safe_handle_inbound(session_factory, *, project_id: UUID, contact: Any, text: str) -> None:
    """Webhook hook: own session, never raises."""
    try:
        async with session_factory() as session:
            project = await session.get(ClientProject, project_id)
            await handle_inbound(session, project=project, contact=contact, text=text)
            await session.commit()
    except Exception:  # noqa: BLE001
        log.exception("tenant reply failed for project %s", project_id)


# --------------------------------------------------------------------------- sending

async def _post_tenant(phone_number_id: str, token: str, body: dict) -> dict:
    """POST to Meta from the customer's own number (seam for tests). Never logs the token."""
    import httpx

    from .whatsapp_sender import API_URL

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            resp = await client.post(f"{API_URL}/{phone_number_id}/messages", json=body,
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        if resp.status_code != 200:
            code = None
            try:
                code = ((resp.json() or {}).get("error") or {}).get("code")
            except Exception:
                pass
            return {"ok": False, "error": f"http {resp.status_code}", "error_code": str(code) if code else None}
        mid = ((resp.json() or {}).get("messages") or [{}])[0].get("id")
        return {"ok": True, "provider_message_id": str(mid)[:255] if mid else None}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": type(e).__name__}


async def send_draft(session: AsyncSession, draft: ReplyDraft, project: ClientProject) -> ReplyDraft:
    if draft.project_id != project.id:
        raise PermissionError("draft belongs to another project")
    text = (draft.final_text or draft.draft_text or "").strip()
    if contains_pitch(text):
        draft.send_result = {"ok": False, "error": "blocked: Al-Narjis sales content in a tenant reply"}
        await session.flush()
        return draft
    token = decrypt_token(project.wa_access_token_enc) if project.wa_phone_number_id else None
    if not token:
        # No per-project credential: keep it in the queue, visible to the customer.
        draft.send_result = {"ok": False, "error": "queued: no WhatsApp token for this project"}
        draft.meta = {**(draft.meta or {}), "queued": "no_project_token"}
        await session.flush()
        return draft
    result = await _post_tenant(str(project.wa_phone_number_id), token,
                                {"messaging_product": "whatsapp", "to": draft.recipient, "type": "text",
                                 "text": {"body": text[:4096]}})
    draft.send_result = {k: v for k, v in result.items() if k in ("ok", "error", "error_code", "provider_message_id")}
    draft.status = "sent" if result.get("ok") else "failed"
    draft.decided_at = datetime.now(UTC)
    await session.flush()
    return draft


# --------------------------------------------------------------------------- portal queue

async def list_drafts(session: AsyncSession, project_id: UUID, status: str | None = "pending", limit: int = 100):
    q = select(ReplyDraft).where(ReplyDraft.project_id == project_id).order_by(ReplyDraft.created_at.desc()).limit(limit)
    if status:
        q = q.where(ReplyDraft.status == status)
    return list((await session.execute(q)).scalars())


async def get_draft(session: AsyncSession, project_id: UUID, draft_id: UUID) -> ReplyDraft:
    d = await session.get(ReplyDraft, draft_id)
    if d is None or d.project_id != project_id:
        raise LookupError("draft not found")
    return d


async def list_contacts(session: AsyncSession, project_id: UUID, limit: int = 200):
    return list((await session.execute(select(TenantContact).where(TenantContact.project_id == project_id)
                                       .order_by(TenantContact.last_inbound_at.desc()).limit(limit))).scalars())


async def manual_reply(session: AsyncSession, project: ClientProject, contact: str, text: str) -> ReplyDraft:
    """The customer's staff replies to a contact from the portal (human handoff)."""
    text = (text or "").strip()[:4000]
    if not text:
        raise ValueError("empty text")
    c = await _contact(session, project.id, contact)
    if c is None:
        raise LookupError("contact not found")
    draft = ReplyDraft(project_id=project.id, channel=CHANNEL, recipient=c.contact, kind="human", draft_text=text,
                       final_text=text, meta={"tenant": True, "human": True}, status="pending")
    session.add(draft)
    await session.flush()
    return await send_draft(session, draft, project)


def contact_to_dict(c: TenantContact) -> dict:
    return {"contact": c.contact, "name": c.display_name, "messages": c.message_count, "last_text": c.last_text,
            "last_inbound_at": c.last_inbound_at.isoformat() if c.last_inbound_at else None,
            "handoff": c.handoff_at is not None, "handoff_reason": c.handoff_reason, "opt_out": bool(c.opt_out)}
