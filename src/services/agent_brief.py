"""Bridge the portal interview to the agent prompt templates.

Audit finding: for ~20 of 35 agents the interview question keys (catalog
``questions``) did not match the ``{{variables}}`` in ``agents/base/*.yaml``,
so the client's answers were silently dropped and the model got an empty
template. This module maps answers onto template variables, fills sensible
defaults, and always appends the full client brief so nothing is lost.
"""
from __future__ import annotations

import re
from typing import Any

# interview key -> template variable(s) it should also fill
ALIASES: dict[str, tuple[str, ...]] = {
    "text": ("source_text",),
    "type": ("content_type",),
    "target": ("target_locale",),
    "keywords": ("target_keywords",),
    "url": ("site_url",),
    "doc": ("document",),
    "data": ("data_flows",),
    "jurisdiction": ("jurisdictions",),
    "costs": ("cost_ledger",),
    "currency": ("currencies",),
    "catalog": ("product_catalog",),
    "discount": ("discount_ceiling",),
    "message": ("customer_message",),
    "users": ("target_users",),
    "assets": ("brand_assets",),
    "style": ("color_direction",),
    "directive": ("owner_directive",),
    "goal": ("objective",),
    "action": ("objective",),
    "amount": ("amount_sar",),
    "deliverable": ("source_text",),
    "niche": ("industry",),
    "offer": ("package_name_ar",),
    "company": ("context",),
}

# Defaults for a Saudi SMB when the interview does not ask.
DEFAULTS: dict[str, str] = {
    "locale": "ar-SA",
    "source_locale": "ar-SA",
    "target_locale": "en",
    "geography": "المملكة العربية السعودية",
    "location": "المملكة العربية السعودية",
    "jurisdictions": "المملكة العربية السعودية (نظام حماية البيانات الشخصية PDPL)",
    "currencies": "SAR",
    "brand_voice": "ودود ومهني بلهجة سعودية بيضاء",
    "tone": "مهني وودود",
    "audience": "العملاء في السعودية",
    "mode": "reply",
}

SAUDI_CONTEXT = (
    "You work for a Saudi small/medium business served by Al-Narjis (النرجس). "
    "Assume the Saudi market unless told otherwise: prices in SAR, "
    "Saudi platforms and habits (Snapchat, TikTok, Instagram, X, WhatsApp Business, Salla, Zid, "
    "Google Maps), Saudi regulations (PDPL, ZATCA e-invoicing, Maroof/SBC), Hijri/Gregorian dates, "
    "Ramadan/Eid/National Day (23 Sept)/Founding Day (22 Feb) seasons and prayer-time aware scheduling. "
    "Be concrete and ready to use: numbers, examples and next steps. Never invent facts about the "
    "client; if information is missing, state the assumption you made."
)

MIN_MAX_TOKENS = 2000  # Arabic needs ~2x the tokens of English for the same content


def template_vars(template_text: str) -> set[str]:
    return set(re.findall(r"\{\{\s*(\w+)", template_text or ""))


def build_variables(template_text: str, answers: dict[str, Any], client_name: str = "") -> dict[str, Any]:
    answers = {k: v for k, v in (answers or {}).items() if v not in (None, "")}
    out: dict[str, Any] = dict(answers)
    for key, value in answers.items():
        for target in ALIASES.get(key, ()):
            out.setdefault(target, value)
    if client_name:
        out.setdefault("company", client_name)
        out.setdefault("business_name", client_name)
    for var in template_vars(template_text):
        if var not in out:
            out[var] = DEFAULTS.get(var, "غير محدد — افترض الأنسب لنشاط سعودي صغير ووضّح افتراضك")
    return out


def brief_block(answers: dict[str, Any], questions: list[dict] | None = None, client_name: str = "") -> str:
    labels = {q.get("key"): q.get("q_en") or q.get("q_ar") or q.get("key") for q in (questions or [])}
    lines = [f"- {labels.get(k, k)}: {v}" for k, v in (answers or {}).items() if v not in (None, "")]
    head = f"Client: {client_name}\n" if client_name else ""
    if not lines:
        return ""
    return "\n\n--- Client brief (all interview answers) ---\n" + head + "\n".join(lines)
