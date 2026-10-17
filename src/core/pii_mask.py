"""PII masking for prompts sent to external LLM providers (PDPL data minimisation).

Before a prompt leaves the platform for an external model provider (Gemini,
Moonshot, OpenAI, Groq, Anthropic, OpenRouter), personal identifiers are
replaced with stable placeholders:

* email addresses                  -> [EMAIL_1]
* Saudi national / iqama IDs       -> [NATIONAL_ID_1]  (10 digits starting 1 or 2)
* Saudi IBANs (spaces or dashes)   -> [IBAN_1]
* phone numbers (mobile, landline, intl.) -> [PHONE_1]
* card-like numbers (13–19 digits) -> [CARD_1]
* a name after «اسمي» / «أنا اسمي» / "my name is" / «معك» -> [NAME_1]

The model answers with the placeholders; ``unmask`` restores the original
values in the response locally, so the end-customer still sees correct data
while the provider never receives it. Arabic-Indic digits are handled.
«يحدده محمد» is not a name and is left as-is (it is the handoff marker).

Switch: env ``PII_MASKING`` (default ``on``; ``off``/``0``/``false`` disables
outside production). In production the switch is ignored and a warning is
logged: personal data still leaves masked. A caller may opt out per request
with ``metadata["pii_mask"] = False``. Local providers (Ollama) are never
masked: data does not leave the server.
"""

from __future__ import annotations

import logging
import os
import re

log = logging.getLogger(__name__)

_AR = "٠١٢٣٤٥٦٧٨٩"
_D = "[0-9٠-٩]"
_SEP = r"[\s\-]*"
# Trunk 0 / +966, then 5, then exactly 8 digits. Separators may sit between digits.
_SA_MOBILE = rf"(?:(?:\+|00)?{_SEP}(?:966|٩٦٦){_SEP}|[0٠])?[5٥](?:{_SEP}{_D}){{8}}"
# Landline: trunk 0 or +966, then 1, then an area digit 1–7 (011 Riyadh …), then 7 digits.
_SA_LAND = rf"(?:(?:\+|00)?{_SEP}(?:966|٩٦٦){_SEP}|[0٠])[1١][1-7١-٧](?:{_SEP}{_D}){{7}}"
_INTL = rf"(?:\+|00){_D}{{1,3}}(?:{_SEP}{_D}){{7,12}}"
_AR_WORD = r"[\u0621-\u064A]{2,}"
# The word after a name cue is not a person. Bare «أنا مهتم» has no cue at all.
_NOT_A_NAME = (
    "مهتم|مهتمة|أبغى|ابغى|أبي|ابي|أبى|ابى|أريد|اريد|أحتاج|احتاج|عندي|"
    "أسأل|اسأل|أقدر|اقدر|باغي|بسأل|أستفسر|استفسر|عميل|عميلة|صاحب|صاحبة|"
    "زبون|متجر|باقة|سعر|خدمة|دعم|دفع|فاتورة|اشتراك|حق|تمام|مشكلة|سؤال|"
    "جديد|جديدة|الآن|الان|كيف|وش|متى|ليش|لماذا"
)
_NAME_TOKEN = rf"(?!(?:{_NOT_A_NAME})(?:\s|$)){_AR_WORD}"
_EN_NOT_A_NAME = "Interested|Looking|Customer|Client|Owner"

_production_off_warned = False

PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
    # Before phones: a dashed IBAN otherwise loses its middle groups to PHONE.
    ("IBAN", re.compile(rf"\bSA(?:{_SEP}{_D}){{22}}\b", re.IGNORECASE)),
    ("NATIONAL_ID", re.compile(rf"(?<![0-9٠-٩+])[12١٢]{_D}{{9}}(?![0-9٠-٩])")),
    ("PHONE", re.compile(
        rf"(?<![0-9٠-٩])(?:{_SA_MOBILE}|{_SA_LAND}|{_INTL})(?![0-9٠-٩])")),
    # After phones and national IDs, so a 10-digit ID or a mobile is not a card.
    ("CARD", re.compile(
        rf"(?<![0-9٠-٩])(?:{_D}{{4}}(?:[ \-]{_D}{{4}}){{2,3}}|{_D}{{13,19}})(?![0-9٠-٩])"
    )),
    # Explicit cues only. «أنا مهتم» and «I am …» are sentences, not introductions.
    ("NAME", re.compile(
        rf"(?:(?:أنا|انا)\s+)?(?:اسمي|إسمي|اسمى)\s+(?:هو\s+)?{_NAME_TOKEN}(?:\s+{_NAME_TOKEN}){{0,2}}"
        rf"|(?<![\u0621-\u064A])و?معك\s+{_NAME_TOKEN}(?:\s+{_NAME_TOKEN}){{0,2}}"
        rf"|(?i:\bmy name is\s+)(?!(?:{_EN_NOT_A_NAME})\b)[A-Z][A-Za-z'.-]{{1,30}}"
        rf"(?:\s+(?!(?:{_EN_NOT_A_NAME})\b)[A-Z][A-Za-z'.-]{{1,30}}){{0,2}}"
    )),
]


def _requested_off() -> bool:
    return (os.getenv("PII_MASKING", "on") or "on").strip().lower() in ("off", "0", "false", "no")


def _is_production() -> bool:
    return (os.getenv("ENVIRONMENT", "development") or "").strip().lower() == "production"


def enabled() -> bool:
    """True unless masking was explicitly switched off outside production."""
    global _production_off_warned
    if not _requested_off():
        return True
    if _is_production():
        if not _production_off_warned:
            log.warning("PII_MASKING=off is ignored in production; personal data stays masked")
            _production_off_warned = True
        return True
    return False


def for_embedding(text: str) -> str:
    """Mask personal data before a string is sent to an embedding provider.

    Lexical retrieval should keep using the original question. Only the text
    that leaves for a vector API goes through here.
    """
    if not text or not enabled():
        return text
    masked, _mapping = mask(text)
    return masked


def mask(text: str, mapping: dict[str, str] | None = None) -> tuple[str, dict[str, str]]:
    """Return (masked_text, placeholder->original). Reuses ``mapping`` across fields."""
    mapping = {} if mapping is None else mapping
    if not text:
        return text, mapping
    reverse = {v: k for k, v in mapping.items()}
    counters: dict[str, int] = {}
    for k in mapping:
        kind = k[1:].rsplit("_", 1)[0]
        counters[kind] = max(counters.get(kind, 0), int(k.rsplit("_", 1)[1][:-1]))

    for kind, pat in PATTERNS:
        def _sub(m: re.Match) -> str:
            value = m.group(0)
            if value in reverse:
                return reverse[value]
            counters[kind] = counters.get(kind, 0) + 1
            ph = f"[{kind}_{counters[kind]}]"
            mapping[ph] = value
            reverse[value] = ph
            return ph
        text = pat.sub(_sub, text)
    return text, mapping


def unmask(text: str, mapping: dict[str, str]) -> str:
    if not text or not mapping:
        return text
    for ph in sorted(mapping, key=len, reverse=True):
        text = text.replace(ph, mapping[ph])
    return text


def should_mask(provider_value: str, metadata: dict | None) -> bool:
    if not enabled():
        return False
    if (metadata or {}).get("pii_mask") is False:
        return False
    return provider_value != "ollama"


def mask_request(request) -> dict[str, str]:
    """Mask ``prompt`` and ``system_prompt`` of a ModelRequest in place; return the mapping."""
    mapping: dict[str, str] = {}
    request.prompt, mapping = mask(request.prompt, mapping)
    request.system_prompt, mapping = mask(request.system_prompt, mapping)
    if mapping:
        request.metadata["pii_masked"] = sorted({k[1:].rsplit("_", 1)[0] for k in mapping})
    return mapping
