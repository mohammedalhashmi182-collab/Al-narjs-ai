"""Channel-neutral inbound intent classification and lead promotion.

Telegram is the only messaging channel, but the classification rules describe
*what a customer said*, not how they said it. Keeping them here means the
classifier has one home and can be unit-tested without any provider.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from src.models.crm import AcquisitionLead

INTENTS = (
    "INTERESTED",
    "QUESTION",
    "PRICE",
    "DEMO",
    "PROPOSAL",
    "READY_TO_BUY",
    "NOT_INTERESTED",
    "FOLLOW_UP_LATER",
    "OPT_OUT",
    "UNKNOWN",
)

# Intent keywords (Arabic + English). Matching is case-insensitive; Arabic
# letters are compared loosely (roughly normalized in ``_norm``).
_KEYWORDS: dict[str, list[str]] = {
    "OPT_OUT": [
        "لا ترسل", "لا تبعت", "ما تبعت", "تركوني", "اشيلوني", "أيقفوا", "ايقفوا",
        "بطلوا", "كفاية رسائل", "لا تزعجوني", "لست مهتم بالرسائل", "unsubscribe",
        "opt out", "opt-out", "stop messaging", "don't message", "لا اريد رسائل",
        "ابلغوا عن", "ارفعوني من القائمة", "ما ابي رسايل", "منعني",
    ],
    "READY_TO_BUY": [
        "ابغى", "ابغا", "ابي", "أبي", "اريد", "أريد", "عايز", "بدنا",
        "خلنا نبدأ", "نبدأ", "ابدأ", "ابدا", "أبدأ", "اتفقنا", "موافق",
        "سجلنا", "اشترك", "أشترى", "اشتري", "اشتركوا", "سووا لنا الاشتراك",
        "buy", "purchase", "subscribe", "start now", "we agree", "I want it",
        "نحتاج نبدأ", "جهزو لنا", "فعّلوا",
    ],
    "PRICE": [
        "كم السعر", "كم سعره", "بكم", "السعر", "سعر", "التكلفة", "كم تكلفة",
        "كم الثمن", "بكم تبدأ", "تسعير", "سعر الاشتراك", "price", "cost",
        "how much", "pricing", "كم الرسوم", "الأقساط",
    ],
    "DEMO": [
        "ارسلوا العرض", "ابعتوا العرض", "ارسل العرض", "ابعت العرض", "شوفوا العرض",
        "جرّب", "جرب", "نجرب", "ديمو", "demo", "عرض تجريبي", "التجربة",
        "أرسل لنا العرض", "جهزوا العرض", "ابعتوه", "نتعرف عليه",
    ],
    "PROPOSAL": [
        "عرض سعر", "عرض رسمي", "proposal", "كشف حساب", "عقد", "فقرة", "فاتورة",
        "ارسلوا مقترح", "مقترح", "نحتاج عرض", "بالعرض",
    ],
    "FOLLOW_UP_LATER": [
        "بعدين", "لاحقا", "لاحقاً", "وقت لاحق", "مشغول", "انشغل", "سأرجع لكم",
        "نشاور", "نرجع لك", "خلنا نفكر", "بدنا نفكر", "اررجع لكم", "after",
        "later", "busy", "come back", "we'll get back", "check later",
        "بعد شوية", "بعد فترة",
    ],
    "NOT_INTERESTED": [
        "لست مهتم", "مش مهتم", "مش فايدنا", "لا شكرا", "لا شكراً", "ما نحتاج",
        "ما نحتاجه", "مو محتاجين", "not interested", "no thanks", "لا نشكر",
        "شكرا، لا", "معندناش", "ليش ندفع", "مش حابين",
    ],
    "QUESTION": [
        "سؤال", "كيف", "شلون", "وش", "ممكن", "هل في", "هل عندكم", "كم مدة",
        "question", "how", "what do you", "وين", "فيه", "عندكم", "يعني",
    ],
    "INTERESTED": [
        "مهتم", "ممتاز", "رائع", "تمام", "حلو", "يعجبني", "عاجبني", "يناسب",
        "مناسب", "نفسنا", "بسعر مناسب", "ok", "great", "nice", "interested",
        "good", "يعطيك العافية", "تابعوا", "كملوا", "استمروا", "بس عندي سؤال",
    ],
}

# Intent matching priority — OPT_OUT wins over everything else.
_INTENT_ORDER = (
    "OPT_OUT",
    "READY_TO_BUY",
    "PRICE",
    "PROPOSAL",
    "DEMO",
    "NOT_INTERESTED",
    "FOLLOW_UP_LATER",
    "INTERESTED",
    "QUESTION",
    "UNKNOWN",
)

BUYING_INTENTS = {"INTERESTED", "PRICE", "DEMO", "PROPOSAL", "READY_TO_BUY"}

_OBJECTIONS = {
    "price": ["غالي", "مكلف", "expensive", "كثير", "تكلفة عالية", "الميزانية", "ميزانيتنا", "باهظ"],
    "competitor": ["عندنا مزود", "مع المزود", "عندنا احد", "شريكنا", "competitor", "another vendor"],
    "timing": ["الوقت الحالي", "الحين مش مناسب", "not the right time", "هالسنة"],
    "decision": ["المدير مسافر", "بناخد رأي", "نشاور الشركاء", "decision maker"],
    "trust": ["وثوق", "التجربة الفعلية", "بدنا نتأكد", "trust", "proof"],
}

_NORM_RE = re.compile(r"[^\w\s]", re.UNICODE)


def _norm(text: str) -> str:
    """Light normalization for keyword matching (not a display form)."""
    out: list[str] = []
    for ch in text.lower():
        if ch in "أإآٱ":
            out.append("ا")
        elif ch in "ىئ":
            out.append("ي")
        elif ch == "ؤ":
            out.append("و")
        elif ch == "ة":
            out.append("ه")
        else:
            out.append(ch)
    return _NORM_RE.sub(" ", "".join(out)).strip()


def classify_intent(text: str) -> tuple[str, Optional[str]]:
    """Return ``(intent, objection_or_None)`` from free text."""
    text = _norm(str(text or "") or "")
    if not text:
        return "UNKNOWN", None

    for intent in _INTENT_ORDER:
        if intent == "UNKNOWN":
            return "UNKNOWN", detect_objection(text)
        for kw in _KEYWORDS.get(intent, []):
            if kw in text:
                return intent, detect_objection(text)
    return "UNKNOWN", detect_objection(text)


def detect_objection(text: str) -> Optional[str]:
    for obj, kws in _OBJECTIONS.items():
        if any(kw in text for kw in kws):
            return obj
    return None


# --- Lead mapping -------------------------------------------------------------


def promote_lead(lead: AcquisitionLead, intent: str, buying: bool, objection: Optional[str], *, status_promote: bool = True) -> tuple[str, str]:
    """Return ``(status_before, status_after)``. Opt-out is unconditional."""
    before = lead.lead_status or "NEW"
    now_utc = datetime.now(timezone.utc)

    if intent == "OPT_OUT" or objection == "opted_out":
        lead.opt_out = True
        lead.buying_signal = False
        lead.last_reply_at = now_utc
        lead.intent = intent
        if before != "DO_NOT_CONTACT":
            lead.lead_status = "DO_NOT_CONTACT"
            return before, "DO_NOT_CONTACT"
        return before, before

    lead.last_reply_at = now_utc
    lead.intent = intent

    if buying:
        lead.buying_signal = True
        lead.priority_score = min(100, (lead.priority_score or 0) + 40)
        lead.priority = "HIGH"

    if not status_promote:
        return before, before

    mapping = {
        "READY_TO_BUY": "INTERESTED",
        "PRICE": "INTERESTED",
        "INTERESTED": "INTERESTED",
        "DEMO": "DEMO",
        "PROPOSAL": "PROPOSAL",
    }
    desired = mapping.get(intent)
    if desired:
        rank = {"NEW": 0, "READY": 1, "CONTACTED": 2, "REPLIED": 3, "INTERESTED": 4, "DEMO": 5, "PROPOSAL": 6}
        if rank.get(before, 0) < rank[desired]:
            lead.lead_status = desired
            return before, desired
        action_to = {"REPLIED": "REPLIED"}
        if intent not in BUYING_INTENTS and before in ("NEW", "READY", "CONTACTED"):
            lead.lead_status = "REPLIED"
            return before, "REPLIED"
        return before, before
    if before in ("NEW", "READY", "CONTACTED"):
        lead.lead_status = "REPLIED"
        return before, "REPLIED"
    return before, before


