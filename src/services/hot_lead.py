"""Mark a lead hot and tell the owner on the channel that already exists.

A lead is hot when they ask for the free 15-minute trial, reply, or tap the
consultation WhatsApp button. The flag is the existing ``priority`` /
``priority_score`` / ``priority_reason`` columns. ``lead_status`` is not changed.

The alert reuses Telegram (``TELEGRAM_TOKEN`` + ``TELEGRAM_OWNER_CHAT_ID``).
If that chat is not configured and SMTP already is, the same text goes to the
company inbox. No new WhatsApp provider and no new secret is added.

``HOT_LEAD_ALERTS=0`` keeps the flag and skips the message. Unset means on.
"""

from __future__ import annotations

import os
import re
import time
from collections import OrderedDict

from src.utils.logger import get_logger

log = get_logger(__name__)

HOT_SCORE = 90
REPEAT_SECONDS = 15 * 60
_REASON = {
    "trial": "ساخن: طلب تجربة ١٥ دقيقة",
    "reply": "ساخن: ردّ",
    "whatsapp_click": "ساخن: ضغط واتساب للاستشارة",
}
_TRIAL = re.compile(
    r"(تجرب|جرّ?ب|١٥\s*دقيق|15\s*دقيق|free\s*trial|\btrial\b)",
    re.IGNORECASE,
)
_recent: OrderedDict[str, float] = OrderedDict()
_RECENT_CAP = 500


def allow_public_signal(ip: str) -> bool:
    """Cap anonymous click alerts. A refused click still opens WhatsApp."""
    from src.utils.rate_limit import SlidingWindowLimiter

    global _public_signals
    if _public_signals is None:
        _public_signals = SlidingWindowLimiter(12, 3600)
    ok, _retry = _public_signals.check(ip or "unknown")
    return ok


_public_signals = None


def alerts_enabled() -> bool:
    raw = os.environ.get("HOT_LEAD_ALERTS")
    if raw is None or not str(raw).strip():
        return True
    return str(raw).strip().lower() not in {"0", "false", "off", "no"}


def trial_requested(text: str | None) -> bool:
    return bool(_TRIAL.search(text or ""))


def _reasons(lead) -> list:
    raw = getattr(lead, "priority_reason", None)
    return list(raw) if isinstance(raw, list) else []


def _due(key: str, *, newly: bool) -> bool:
    now = time.monotonic()
    last = _recent.get(key)
    if newly or last is None or now - last >= REPEAT_SECONDS:
        _recent[key] = now
        _recent.move_to_end(key)
        while len(_recent) > _RECENT_CAP:
            _recent.popitem(last=False)
        return True
    return False


def stamp_hot(lead, kind: str, *, excerpt: str = "") -> str | None:
    """Raise priority. Return the alert text when the owner should be told now.

    Does not change ``lead_status``. Opt-out leads are left alone.
    """
    if lead is None:
        return None
    if getattr(lead, "opt_out", False) or (getattr(lead, "lead_status", "") or "") == "DO_NOT_CONTACT":
        return None
    reason = _REASON.get(kind) or _REASON["reply"]
    reasons = _reasons(lead)
    newly = reason not in reasons
    if newly:
        reasons.append(reason)
    lead.priority_reason = reasons
    lead.priority = "HIGH"
    lead.priority_score = max(int(getattr(lead, "priority_score", 0) or 0), HOT_SCORE)
    if kind in {"trial", "whatsapp_click"}:
        lead.buying_signal = True
    key = f"{getattr(lead, 'id', None) or id(lead)}:{kind}"
    if not _due(key, newly=newly):
        return None
    return alert_text(lead, reason, excerpt=excerpt, source=getattr(lead, "source", "") or "")


def alert_text(lead, reason: str, *, excerpt: str = "", source: str = "", anonymous: bool = False) -> str:
    snippet = re.sub(r"[\x00-\x1f\x7f]", " ", excerpt or "").strip()
    if len(snippet) > 180:
        snippet = snippet[:180].rstrip() + "…"
    if anonymous or lead is None:
        lines = [
            "🔥 عميل ساخن — النرجس",
            f"السبب: {reason}",
            "لا يوجد اسم أو جوال في هذه النقرة، لذلك لم يُنشأ سجل عميل.",
        ]
    else:
        name = (getattr(lead, "contact_name", None) or getattr(lead, "company_name", None) or "—")
        lines = [
            "🔥 عميل ساخن — النرجس",
            f"السبب: {reason}",
            f"الاسم: {name}",
            f"الجوال: {getattr(lead, 'phone', None) or '—'}",
            f"البريد: {getattr(lead, 'email', None) or '—'}",
            f"المصدر: {source or getattr(lead, 'source', None) or '—'}",
        ]
    if snippet:
        lines.append(f"مقتطف: {snippet}")
    return "\n".join(lines)


def anonymous_click_alert(excerpt: str = "") -> str:
    return alert_text(None, _REASON["whatsapp_click"], excerpt=excerpt, anonymous=True)


def schedule_alert(text: str | None) -> None:
    """Fire the alert without holding the request that saved the lead."""
    if not text:
        return
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(deliver_alert(text))


async def deliver_alert(text: str | None) -> dict:
    """Best-effort. Never raises. Skipped entirely when HOT_LEAD_ALERTS is off."""
    if not text or not alerts_enabled():
        return {"ok": False, "skipped": True}
    telegram_ok = False
    try:
        from src.services import telegram_sender

        result = telegram_sender.send_owner_alert(text)
        if hasattr(result, "__await__"):
            result = await result
        telegram_ok = bool(isinstance(result, dict) and result.get("ok"))
    except Exception as exc:  # noqa: BLE001 - the lead save must not depend on Telegram
        log.warning("hot lead telegram alert failed: %s", type(exc).__name__)
    if telegram_ok:
        log.info("hot lead alert channel=telegram ok=true")
        return {"ok": True, "channel": "telegram"}
    try:
        from src.services import email_service
        from src.services.support import SUPPORT_EMAIL

        if email_service.is_configured():
            sent = await email_service.send_email(SUPPORT_EMAIL, "عميل ساخن — النرجس", text)
            log.info("hot lead alert channel=email ok=%s", bool(sent))
            return {"ok": bool(sent), "channel": "email"}
    except Exception as exc:  # noqa: BLE001
        log.warning("hot lead email alert failed: %s", type(exc).__name__)
    log.info("hot lead alert not delivered (telegram chat or SMTP is not configured)")
    return {"ok": False, "channel": None}
