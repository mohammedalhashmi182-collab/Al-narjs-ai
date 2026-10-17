"""Remove internal repository paths from text a customer can see.

Public ``https`` URLs are masked before any path match, so a link such as
``https://karmaai.online/docs/terms.pdf`` is never shortened. A line that
starts with «المصدر:» keeps its remaining words; only the path token goes.
A label left with nothing after it («المصدر:», «Source:») is removed, and a
markdown link whose target is an internal path is removed entirely.
"""

from __future__ import annotations

import re

# Trailing sentence punctuation stays outside the masked URL.
_URL = re.compile(r"(?:https?://|www\.)[^\s<>\"'`)\]]+", re.I)
_URL_TAIL = ".,);:!?،"

_INTERNAL_PATH = re.compile(
    r"`(?:src|docs|data|agents|tests|scripts|alembic)/[A-Za-z0-9_./\-]*\.[A-Za-z0-9]{1,8}`"
    r"|(?<![A-Za-z0-9_.\-])(?:src|docs|data|agents|tests|scripts|alembic)/"
    r"[A-Za-z0-9_./\-]*\.[A-Za-z0-9]{1,8}"
)
# [label](src/…) — drop the whole link, not only the target.
_MD_INTERNAL_LINK = re.compile(
    r"\[[^\]\n]{0,200}\]\(\s*`?(?:src|docs|data|agents|tests|scripts|alembic)/[^)\n]*?`?\s*\)"
)
# Applied after paths are gone. Real words after the colon keep the label.
_BARE_LABEL = re.compile(
    r"(?m)(?:المصدر|[Ss]ource)\s*[:：]\s*(?:[،,.\-–—]+\s*)*(?=\s*(?:[)\]）]|$))"
)

_PLACE_L = "\ue000"
_PLACE_R = "\ue001"


def sanitize_public_text(text: str) -> str:
    """Drop repo paths. Keep public URLs and any non-path words on the line."""
    if not text:
        return ""
    cleaned = _MD_INTERNAL_LINK.sub("", text)
    urls: list[str] = []

    def _mask(match: re.Match) -> str:
        raw = match.group(0)
        trimmed = raw.rstrip(_URL_TAIL)
        if len(trimmed) < len("http://a"):
            trimmed = raw
        urls.append(trimmed)
        return f"{_PLACE_L}{len(urls) - 1}{_PLACE_R}{raw[len(trimmed):]}"

    cleaned = _URL.sub(_mask, cleaned)
    cleaned = _INTERNAL_PATH.sub("", cleaned)
    cleaned = _BARE_LABEL.sub("", cleaned)
    cleaned = re.sub(
        rf"{re.escape(_PLACE_L)}(\d+){re.escape(_PLACE_R)}",
        lambda m: urls[int(m.group(1))],
        cleaned,
    )
    cleaned = re.sub(r"((?:المصدر|[Ss]ource)\s*[:：])(?:\s*[،,]+\s*)+", r"\1 ", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\.\s+\.", ".", cleaned)
    cleaned = re.sub(r"(?:،\s*){2,}", "، ", cleaned)
    cleaned = re.sub(r"\(\s*\)", "", cleaned)
    cleaned = re.sub(r"\[\s*\]", "", cleaned)
    cleaned = re.sub(r"(?m)[ \t]*[،,][ \t]*$", "", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


# Name used by the ask router and the tests written with the first strip.
strip_internal_sources = sanitize_public_text
