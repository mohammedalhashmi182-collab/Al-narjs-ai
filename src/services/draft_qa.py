"""Conversation QA: score an agent draft against the catalog and the knowledge base.

Deterministic checks (no model call):

* **Invented prices** - every money amount in the draft (a number next to
  ريال / ر.س / SAR / ﷼) must be a price the catalog can produce (plans,
  annual, founding, VAT totals, add-ons, setup fees, Meta caps) or appear in
  the project's knowledge base. Anything else costs 40 points.
* **Unbuilt features promised as live** - voice agent/calls, Salla/Zid store
  connection, abandoned carts, Instagram DMs - without a "قريباً"/"coming soon"
  qualifier costs 25 points.
* **Store write access** - the Salla/Zid connection (coming soon) will be
  read-only; a draft that says it edits/manages store products, orders
  or prices, or installs itself automatically, costs 25 points.
* **Guarantees / invented results** - "نضمن لك" / "guaranteed" / "% زيادة"
  style claims cost 20 points (the setup guarantee from the catalog is allowed).
* Empty or unfinished placeholders ("{...}" other than {payment_url}) cost 30.

Score is 0..100; below ``FLAG_THRESHOLD`` the draft is flagged for review and
is never auto-sent.
"""

from __future__ import annotations

import re
from typing import Iterable

from src.services import catalog

FLAG_THRESHOLD = 70

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_CURRENCY = r"(?:ريال|ر\.?\s?س|SAR|﷼|riyals?)"
_NUM = r"(\d[\d,٬\.]*)"
_MONEY_RE = re.compile(rf"{_NUM}\s*{_CURRENCY}|{_CURRENCY}\s*{_NUM}", re.IGNORECASE)

UNBUILT = {
    "voice": (r"وكيل\s*صوت|خط\s*صوت|مكالمات|المكالمات|voice agent|voice line|phone calls",),
    "store_link": (r"ربط\s*(?:متجرك?\s*(?:على\s*)?)?سلة|ربط\s*زد|Salla (?:store )?(?:integration|connection)|Zid (?:store )?(?:integration|connection)",),
    "abandoned_cart": (r"السلات?\s*المتروكة|سلة\s*متروكة|abandoned[- ]cart",),
    "instagram_dm": (r"رسائل\s*(?:ال)?(?:إنستغرام|انستقرام|انستغرام)|خاص\s*(?:ال)?(?:إنستغرام|انستقرام)|Instagram DMs?",),
}
_STORE_WRITE = re.compile(
    r"(?:يعدّ?ل|يضيف|يحذف|يدير|تعديل|إدارة)\s*(?:\S+\s+){0,2}(?:منتجات|المنتجات|طلبات|الطلبات|أسعار|الأسعار)\s*(?:\S+\s+){0,3}(?:سلة|زد)"
    r"|(?:سلة|زد)\s*(?:\S+\s+){0,4}(?:يعدّ?ل|يضيف|يحذف|يدير|تعديل|إدارة)\s*(?:\S+\s+){0,1}(?:منتجات|المنتجات|طلبات|الطلبات|أسعار|الأسعار)"
    r"|(?:Salla|Zid)\b[^.\n]{0,60}\b(?:edit|update|create|delete|manage)s?\b[^.\n]{0,20}\b(?:products|orders|prices)"
    r"|(?:edit|update|create|delete|manage)s?\s+(?:your\s+)?(?:products|orders|prices)\s+(?:on|in)\s+(?:your\s+)?(?:Salla|Zid)"
    r"|(?:Salla|Zid)\b[^.\n]{0,40}\b(?:self-serve|installs? (?:itself|automatically)|one-click)",
    re.IGNORECASE,
)
_SOON = re.compile(r"قريباً|قريبا|coming soon", re.IGNORECASE)
_GUARANTEE = re.compile(r"نضمن\s*لك|مضمون(?:ة)?\s*100|guarantee[sd]?\s+(?:you|results|sales)|\d+\s*[%٪]\s*(?:زيادة|أكثر|more|increase)",
                        re.IGNORECASE)
_PLACEHOLDER = re.compile(r"\{(?!payment_url\})[^{}\s]{1,40}\}")


def _norm_number(raw: str) -> int | None:
    s = raw.translate(_AR_DIGITS).replace(",", "").replace("٬", "")
    if s.count(".") == 1:
        s = s.split(".")[0]
    s = s.replace(".", "")
    return int(s) if s.isdigit() else None


def money_amounts(text: str) -> list[int]:
    out = []
    for m in _MONEY_RE.finditer(text or ""):
        n = _norm_number(m.group(1) or m.group(2) or "")
        if n is not None:
            out.append(n)
    return out


def allowed_amounts() -> set[int]:
    """Every whole-riyal amount the catalog can legitimately quote."""
    from src.services import payments

    hal: set[int] = set()
    keys = list(catalog.PACKAGES) + list(catalog.LEGACY_TIERS)
    for key in keys:
        for period in catalog.BILLING_PERIODS:
            for addons in range(0, catalog.MAX_ADDON_AGENTS + 1):
                for amt in (catalog.plan_amount(key, period, addons),):
                    hal.update({amt, payments.total_with_vat(amt)})
                if key in catalog.PACKAGES and catalog.founding_enabled():
                    f = catalog.founding_amount(key, period, addons)
                    hal.update({f, payments.total_with_vat(f)})
    for pkg in catalog.PACKAGES.values():
        hal.update({int(pkg.get("setup_fee") or 0), int(pkg["limits"]["meta_cap"])})
        if pkg.get("setup_fee"):
            hal.add(payments.total_with_vat(int(pkg["setup_fee"])))
    hal.add(catalog.ADDON_AGENT["amount"])
    hal.add(catalog.LEGACY_ADDON_AMOUNT)
    for a in catalog.USAGE_ADDONS.values():
        if a.get("amount"):
            hal.add(int(a["amount"]))
    hal.add(int(catalog.ENTERPRISE["amount_from"]))
    riyals = {h // 100 for h in hal if h}
    # a quoted riyal amount may be rounded either way
    riyals |= {(h + 99) // 100 for h in hal if h}
    return riyals


def score_draft(text: str, kb_texts: Iterable[str] = ()) -> dict:
    text = text or ""
    issues: list[dict] = []
    score = 100

    kb_numbers: set[int] = set()
    for t in kb_texts:
        for m in re.finditer(_NUM, (t or "").translate(_AR_DIGITS)):
            n = _norm_number(m.group(1))
            if n is not None:
                kb_numbers.add(n)
    allowed = allowed_amounts() | kb_numbers
    invented = sorted({n for n in money_amounts(text) if n not in allowed})
    if invented:
        score -= 40
        issues.append({"code": "invented_price", "detail": invented})

    soon = bool(_SOON.search(text))
    promised = [k for k, pats in UNBUILT.items() if any(re.search(p, text, re.IGNORECASE) for p in pats)]
    if promised and not soon:
        score -= 25
        issues.append({"code": "unbuilt_feature", "detail": promised})

    w = _STORE_WRITE.search(text)
    if w:
        score -= 25
        issues.append({"code": "store_write_claim", "detail": w.group(0)})

    g = _GUARANTEE.search(text)
    if g and catalog.SETUP_GUARANTEE["text"][:20] not in text:
        score -= 20
        issues.append({"code": "unsupported_claim", "detail": g.group(0)})

    if not text.strip() or _PLACEHOLDER.search(text):
        score -= 30
        issues.append({"code": "placeholder_or_empty"})

    score = max(0, score)
    return {"score": score, "flagged": score < FLAG_THRESHOLD, "issues": issues}


async def kb_texts_for(session, project_id=None) -> list[str]:
    try:
        from src.services.agent_tools import knowledge_base

        docs = await knowledge_base.list_docs(session, project_id)
        return [d.content for d in docs]
    except Exception:  # noqa: BLE001
        return []


async def score_and_tag(session, draft, project_id=None) -> dict:
    """Attach ``meta["qa"]`` to a ReplyDraft and return the result."""
    from src.services import policies

    kb = await kb_texts_for(session, project_id)
    kb.append(policies.OWNER_FAQ_AR)
    result = score_draft(draft.final_text or draft.draft_text, kb)
    draft.meta = {**(draft.meta or {}), "qa": result}
    return result
