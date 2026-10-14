"""Site-assistant support tickets: validate, store, notify the owner, list.

Visitor gives name, email and question (with PDPL consent). The ticket is
stored, the owner is notified via the existing paths (Telegram War Room alert,
and email to the support inbox when SMTP is configured), and the visitor gets
a reference like NRJ-000123 with the expected response time.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.support import SupportTicket

log = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,24}$")
RESPONSE_TIME_AR = "خلال يوم عمل"
RESPONSE_TIME_EN = "within one business day"
MAX_NAME, MAX_EMAIL, MAX_Q = 120, 254, 2000


class TicketError(ValueError):
    def __init__(self, field: str):
        super().__init__(field)
        self.field = field


def _clean(v: Any, n: int) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(v or "")).strip()[:n]


def validate(name: Any, email: Any, question: Any, consent: Any) -> tuple[str, str, str]:
    n, e, q = _clean(name, MAX_NAME), _clean(email, MAX_EMAIL).lower(), _clean(question, MAX_Q)
    if len(n) < 2:
        raise TicketError("name")
    if not EMAIL_RE.match(e) or ".." in e:
        raise TicketError("email")
    if len(q) < 3:
        raise TicketError("question")
    if consent is not True:
        raise TicketError("consent")
    return n, e, q


async def _notify(t: SupportTicket) -> dict:
    text = (f"🎫 تذكرة دعم جديدة {t.reference}\n"
            f"الاسم: {t.name}\nالبريد: {t.email}\nاللغة: {t.lang}\nالصفحة: {t.page or '-'}\n\n{t.question[:1500]}")
    out: dict = {}
    try:
        from src.services import telegram_sender
        r = await telegram_sender.send_owner_alert(text)
        out["telegram"] = bool(r.get("ok"))
    except Exception as exc:  # best-effort
        out["telegram"] = False
        log.warning("ticket telegram notify failed: %s", type(exc).__name__)
    try:
        from src.services import email_service
        from src.services.support import SUPPORT_EMAIL
        out["email"] = await email_service.send_email(SUPPORT_EMAIL, f"[{t.reference}] تذكرة دعم من {t.name}", text)
    except Exception as exc:
        out["email"] = False
        log.warning("ticket email notify failed: %s", type(exc).__name__)
    return out


async def create(session: AsyncSession, *, name: Any, email: Any, question: Any, consent: Any,
                 lang: str = "ar", page: str | None = None) -> SupportTicket:
    n, e, q = validate(name, email, question, consent)
    t = SupportTicket(name=n, email=e, question=q, consent=True,
                      lang="en" if lang == "en" else "ar", page=_clean(page, 300) or None)
    session.add(t)
    await session.flush()
    t.notify_result = await _notify(t)
    await session.commit()
    return t


def to_dict(t: SupportTicket) -> dict:
    return {"id": t.id, "reference": t.reference, "name": t.name, "email": t.email, "question": t.question,
            "lang": t.lang, "page": t.page, "status": t.status, "notify": t.notify_result or {},
            "created_at": t.created_at.isoformat() if t.created_at else None}


async def list_recent(session: AsyncSession, limit: int = 50) -> list[dict]:
    rows = (await session.execute(select(SupportTicket).order_by(SupportTicket.id.desc()).limit(limit))).scalars()
    return [to_dict(t) for t in rows]
