"""PII masking for prompts sent to external LLM providers (PDPL data minimisation).

Before a prompt leaves the platform for an external model provider (Gemini,
Moonshot, OpenAI, Groq, Anthropic, OpenRouter), personal identifiers are
replaced with stable placeholders:

* email addresses                 -> [EMAIL_1]
* Saudi national / iqama IDs      -> [NATIONAL_ID_1]  (10 digits starting 1 or 2)
* Saudi IBANs                     -> [IBAN_1]
* phone numbers (Saudi + intl.)   -> [PHONE_1]

The model answers with the placeholders; ``unmask`` restores the original
values in the response locally, so the end-customer still sees correct data
while the provider never receives it. Arabic-Indic digits are handled.

Switch: env ``PII_MASKING`` (default ``on``; ``off``/``0``/``false`` disables).
A caller may opt out per request with ``metadata["pii_mask"] = False``.
Local providers (Ollama) are never masked: data does not leave the server.
"""

from __future__ import annotations

import os
import re

_AR = "٠١٢٣٤٥٦٧٨٩"
_D = "[0-9٠-٩]"

PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
    ("IBAN", re.compile(rf"\bSA{_D}{{2}}(?:\s?{_D}{{4}}){{5}}\b", re.IGNORECASE)),
    ("NATIONAL_ID", re.compile(rf"(?<![0-9٠-٩+])[12١٢]{_D}{{9}}(?![0-9٠-٩])")),
    ("PHONE", re.compile(
        rf"(?<![0-9٠-٩])(?:(?:\+|00)?[\s\-]?(?:966|٩٦٦)[\s\-]?|[0٠])?[5٥]{_D}(?:[\s\-]?{_D}){{7}}(?![0-9٠-٩])"
        rf"|(?:\+|00){_D}{{1,3}}(?:[\s\-]?{_D}){{7,12}}(?![0-9٠-٩])")),
]


def enabled() -> bool:
    return (os.getenv("PII_MASKING", "on") or "on").strip().lower() not in ("off", "0", "false", "no")


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
