"""Reusable quality gate: score a deliverable and revise up to three rounds.

Scores are logged (structured log, in-process ring, and the database when a
session is passed). The default reviser only removes placeholder debris. A
model reviser is used when the caller passes one, which the HTTP route does
only if ``CAPABILITY_EVAL_USE_MODEL`` is on.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

from src.services.capabilities.config import eval_max_rounds, eval_min_score
from src.utils.logger import get_logger

logger = get_logger(__name__)

_AR = re.compile(r"[\u0600-\u06FF]")
_LATIN_WORD = re.compile(r"[A-Za-z]{3,}")
_PLACEHOLDER = re.compile(
    r"\{\{|\}\}|TODO|TBD|FIXME|lorem ipsum|\[insert|\[your |غير محدد\s*—\s*افترض|placeholder|\bXXX\b|___",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"\d[\d,\.]*\s*%|\b\d{3,}\b")
_SOURCE = re.compile(r"مصدر|تقدير|افتراض|according|estimate|source|https?://", re.IGNORECASE)
_DIALECT = ("وش", "أبغى", "ابغى", "الحين", "ياليت")
_LOGS: deque[dict] = deque(maxlen=200)


@dataclass
class ScoreCard:
    accuracy_sources: float
    arabic_quality: float
    rtl_formatting: float
    brand_compliance: float
    completeness: float
    no_placeholders: float
    issues: list[str] = field(default_factory=list)

    @property
    def overall(self) -> float:
        values = [
            self.accuracy_sources,
            self.arabic_quality,
            self.rtl_formatting,
            self.brand_compliance,
            self.completeness,
            self.no_placeholders,
        ]
        return round(sum(values) / len(values), 4)

    def as_dict(self) -> dict:
        return {
            "accuracy_sources": self.accuracy_sources,
            "arabic_quality": self.arabic_quality,
            "rtl_formatting": self.rtl_formatting,
            "brand_compliance": self.brand_compliance,
            "completeness": self.completeness,
            "no_placeholders": self.no_placeholders,
            "overall": self.overall,
            "issues": list(self.issues),
        }


def _clip(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def score_output(
    text: str,
    *,
    locale: str = "ar",
    register: str = "",
    brand_ar: str = "",
    brand_en: str = "",
    banned_words: list[str] | None = None,
) -> ScoreCard:
    raw = text or ""
    issues: list[str] = []
    locale = (locale or "ar").lower()
    arabic = len(_AR.findall(raw))
    latin = len(_LATIN_WORD.findall(raw))

    if _NUMBER.search(raw) and not _SOURCE.search(raw):
        accuracy = 0.45
        issues.append("numbers or percentages are not tied to a source or marked as an estimate")
    else:
        accuracy = 1.0 if _SOURCE.search(raw) or not _NUMBER.search(raw) else 0.7

    if locale.startswith("ar"):
        if arabic < 20:
            arabic_quality = 0.35
            issues.append("Arabic output is too short to judge language quality")
        else:
            arabic_quality = _clip(arabic / (arabic + latin * 4))
            if register == "saudi" and not any(marker in raw for marker in _DIALECT):
                arabic_quality = _clip(arabic_quality - 0.15)
                issues.append("Saudi dialect was requested and no dialect marker is present")
            if register == "msa" and any(marker in raw for marker in _DIALECT):
                arabic_quality = _clip(arabic_quality - 0.2)
                issues.append("MSA was requested but the text uses dialect markers")
    else:
        arabic_quality = 1.0 if latin >= arabic else 0.4
        if arabic_quality < 1:
            issues.append("English was requested and the text is mostly Arabic")

    if locale.startswith("ar") and arabic == 0:
        rtl = 0.2
        issues.append("Arabic locale has no Arabic text to format RTL")
    elif re.search(r'dir\s*=\s*["\']ltr["\']', raw, re.I) and arabic:
        rtl = 0.3
        issues.append("Arabic text is wrapped in an LTR direction")
    else:
        rtl = 1.0

    banned = [word for word in (banned_words or []) if word and word in raw]
    brand_score = 1.0
    if banned:
        brand_score = 0.0
        issues.append("banned words present: " + ", ".join(banned[:5]))
    if locale.startswith("ar") and brand_ar and brand_ar not in raw:
        brand_score = min(brand_score, 0.45)
        issues.append("Arabic brand spelling is missing")
    if locale.startswith("en") and brand_en and brand_en not in raw:
        brand_score = min(brand_score, 0.45)
        issues.append("English brand spelling is missing")

    completeness = 1.0
    if len(raw.strip()) < 40:
        completeness = 0.35
        issues.append("answer looks incomplete")
    elif len(raw.strip()) < 80 or "\n" not in raw:
        completeness = 0.7
        issues.append("answer has little structure")

    if _PLACEHOLDER.search(raw):
        placeholders = 0.0
        issues.append("placeholder or unfinished marker")
    else:
        placeholders = 1.0

    return ScoreCard(
        accuracy_sources=_clip(accuracy),
        arabic_quality=_clip(arabic_quality),
        rtl_formatting=_clip(rtl),
        brand_compliance=_clip(brand_score),
        completeness=_clip(completeness),
        no_placeholders=placeholders,
        issues=issues,
    )


def placeholder_revise(text: str, issues: list[str]) -> str:
    """Remove unfinished markers. Does not invent facts or translate."""
    del issues
    cleaned = _PLACEHOLDER.sub("", text or "")
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def recent_logs() -> list[dict]:
    return list(_LOGS)


def _remember(entry: dict) -> None:
    _LOGS.append(entry)
    logger.info(
        "eval_score",
        agent=entry.get("agent_slug") or "",
        overall=entry.get("overall"),
        rounds=entry.get("rounds"),
        passed=entry.get("passed"),
        source=entry.get("source") or "",
    )


@dataclass
class EvalOutcome:
    text: str
    passed: bool
    rounds: int
    revisions: int
    scores: list[dict]

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "passed": self.passed,
            "rounds": self.rounds,
            "revisions": self.revisions,
            "scores": self.scores,
            "final": self.scores[-1] if self.scores else {},
        }


def run_eval_loop(
    text: str,
    *,
    locale: str = "ar",
    register: str = "",
    brand_ar: str = "",
    brand_en: str = "",
    banned_words: list[str] | None = None,
    revise: Callable[[str, list[str]], str] | None = None,
    max_rounds: int | None = None,
    min_score: float | None = None,
    agent_slug: str = "",
    client_key: str = "",
    source: str = "api",
) -> EvalOutcome:
    limit = max_rounds if max_rounds is not None else eval_max_rounds()
    limit = max(1, min(3, int(limit)))
    threshold = eval_min_score() if min_score is None else float(min_score)
    current = text or ""
    history: list[dict] = []
    revisions = 0
    reviser = revise or placeholder_revise
    while True:
        card = score_output(
            current,
            locale=locale,
            register=register,
            brand_ar=brand_ar,
            brand_en=brand_en,
            banned_words=banned_words,
        )
        snapshot = card.as_dict()
        snapshot["round"] = len(history) + 1
        history.append(snapshot)
        passed = card.overall >= threshold and card.no_placeholders == 1.0 and card.brand_compliance > 0
        _remember(
            {
                "agent_slug": agent_slug,
                "client_key": client_key,
                "overall": card.overall,
                "rounds": len(history),
                "passed": passed,
                "source": source,
                "scores": snapshot,
            }
        )
        if passed or revisions >= limit:
            return EvalOutcome(current, passed, len(history), revisions, history)
        revised = reviser(current, list(card.issues))
        revisions += 1
        if not revised or revised.strip() == current.strip():
            return EvalOutcome(current, False, len(history), revisions, history)
        current = revised


async def persist_log(session, entry: dict) -> None:
    from src.models.capabilities import CapabilityEvalLog

    row = CapabilityEvalLog(
        agent_slug=(entry.get("agent_slug") or "")[:80],
        client_key=(entry.get("client_key") or "")[:64],
        scores=entry.get("scores") or {},
        overall=float(entry.get("overall") or 0),
        rounds=int(entry.get("rounds") or 0),
        passed=bool(entry.get("passed")),
        source=(entry.get("source") or "api")[:20],
    )
    session.add(row)
    await session.commit()
