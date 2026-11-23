"""Offline comparison harness for an open Arabic voice chain (ASR -> LLM -> TTS).

This module never serves visitors. The public ``/voice`` page keeps using the
owner's xAI Voice Agent (see ``voice_live.py``). The harness runs a recorded
Arabic test set through self-hosted open models so latency and transcription
accuracy can be compared before any change to ``/voice`` is proposed.

Nothing here invents results. Every number in a report comes from a call that
actually ran. A stage that fails is recorded as failed; it is never filled in.

Endpoint contract (any self-hosted server that matches it):

* ASR: ``POST`` multipart field ``file`` (WAV) plus form field ``language``
  -> JSON ``{"text": "..."}``
* TTS: ``POST`` JSON ``{"text": "...", "language": "ar"}`` -> audio bytes

Configuration comes from environment variables read here, not from
``src/config/settings.py``:

* ``VOICE_COMPARE_ASR_URL`` (required)
* ``VOICE_COMPARE_TTS_URL`` (required)
* ``VOICE_COMPARE_TOKEN`` (optional bearer token, sent only to these URLs)

Plain ``http://`` is accepted only for localhost, so a token is never sent in
clear text to a remote host.
"""

from __future__ import annotations

import math
import os
import re
import statistics
import time
import unicodedata
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import httpx

from src.core.model_provider import ModelRequest

ENV_ASR_URL = "VOICE_COMPARE_ASR_URL"
ENV_TTS_URL = "VOICE_COMPARE_TTS_URL"
ENV_TOKEN = "VOICE_COMPARE_TOKEN"
TIMEOUT_SECONDS = 60.0
LLM_CHAIN = "gemini"
LLM_MAX_TOKENS = 300
LLM_SYSTEM_PROMPT = (
    "أجب بالعربية الفصحى المبسطة في جملتين أو ثلاث. "
    "لا تذكر أسعاراً أو أرقاماً أو وعوداً لم ترد في السؤال."
)
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
_ALEF_VARIANTS = re.compile("[آأإٱ]")
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)

AsrFn = Callable[[bytes, str], Awaitable[str]]
LlmFn = Callable[[str], Awaitable[str]]
TtsFn = Callable[[str, str], Awaitable[bytes]]


class NotConfigured(RuntimeError):
    """Raised when a required endpoint variable is missing. The run must not start."""

    def __init__(self, missing: list[str]) -> None:
        super().__init__("missing " + ", ".join(missing))
        self.missing = missing


def normalize_arabic(text: str) -> str:
    """Normalise Arabic text for word-level comparison.

    Removes diacritics and tatweel, unifies alef variants, maps alef maqsura to
    yeh, strips punctuation (including Arabic comma and question mark), lowercases
    Latin letters and collapses whitespace.
    """
    text = unicodedata.normalize("NFKC", text or "")
    text = _DIACRITICS.sub("", text).replace("ـ", "")
    text = _ALEF_VARIANTS.sub("ا", text).replace("ى", "ي")
    text = _PUNCTUATION.sub(" ", text.lower())
    return " ".join(text.split())


def word_error_rate(reference: str, hypothesis: str) -> float | None:
    """Word-level edit distance divided by the reference length.

    Returns ``None`` when the reference is empty, because the rate is undefined.
    """
    ref = normalize_arabic(reference).split()
    if not ref:
        return None
    hyp = normalize_arabic(hypothesis).split()
    previous = list(range(len(hyp) + 1))
    for i, ref_word in enumerate(ref, start=1):
        current = [i]
        for j, hyp_word in enumerate(hyp, start=1):
            cost = 0 if ref_word == hyp_word else 1
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost))
        previous = current
    return previous[-1] / len(ref)


@dataclass
class StageResult:
    name: str
    ok: bool
    latency_ms: float
    error: str = ""


@dataclass
class CaseResult:
    case_id: str
    transcript: str = ""
    reply: str = ""
    audio_bytes: int = 0
    wer: float | None = None
    stages: list[StageResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return [s.name for s in self.stages if s.ok] == ["asr", "llm", "tts"]


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


async def _stage(result: CaseResult, name: str, call: Callable[[], Awaitable[Any]]) -> Any | None:
    started = time.perf_counter()
    try:
        value = await call()
    except Exception as exc:  # recorded, never raised: one bad clip must not stop the suite
        elapsed = (time.perf_counter() - started) * 1000
        result.stages.append(StageResult(name, False, round(elapsed, 1), _describe(exc)))
        return None
    elapsed = (time.perf_counter() - started) * 1000
    result.stages.append(StageResult(name, True, round(elapsed, 1)))
    return value


async def run_case(
    case_id: str,
    audio: bytes,
    *,
    asr: AsrFn,
    llm: LlmFn,
    tts: TtsFn,
    reference_text: str | None = None,
    language: str = "ar",
) -> CaseResult:
    """Run one clip through ASR, the LLM and TTS, stopping at the first failed stage."""
    result = CaseResult(case_id=case_id)

    async def _transcribe() -> str:
        text = await asr(audio, language)
        if not text or not text.strip():
            raise ValueError("ASR returned empty text")
        return text

    transcript = await _stage(result, "asr", _transcribe)
    if transcript is None:
        return result
    result.transcript = transcript
    if reference_text:
        result.wer = word_error_rate(reference_text, transcript)

    async def _reply() -> str:
        text = await llm(transcript)
        if not text or not text.strip():
            raise ValueError("LLM returned empty text")
        return text

    reply = await _stage(result, "llm", _reply)
    if reply is None:
        return result
    result.reply = reply

    async def _speak() -> bytes:
        speech = await tts(reply, language)
        if not speech:
            raise ValueError("TTS returned no audio")
        return speech

    speech = await _stage(result, "tts", _speak)
    if speech is None:
        return result
    result.audio_bytes = len(speech)
    return result


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    """Aggregate per-stage latency (median and p95, successful calls only) and WER."""
    latencies: dict[str, list[float]] = {}
    failures: dict[str, int] = {}
    for case in results:
        for stage in case.stages:
            if stage.ok:
                latencies.setdefault(stage.name, []).append(stage.latency_ms)
            else:
                failures[stage.name] = failures.get(stage.name, 0) + 1
    wers = [case.wer for case in results if case.wer is not None]
    return {
        "cases": len(results),
        "complete": sum(1 for case in results if case.ok),
        "latency_ms": {
            name: {
                "median": round(statistics.median(values), 1),
                "p95": round(_percentile(values, 95), 1),
                "n": len(values),
            }
            for name, values in latencies.items()
        },
        "failures": failures,
        "wer_mean": round(statistics.fmean(wers), 4) if wers else None,
        "wer_cases": len(wers),
    }


@dataclass(frozen=True)
class Endpoints:
    asr_url: str
    tts_url: str
    token: str = ""


def _checked_url(name: str, raw: str) -> str:
    parts = urlsplit(raw)
    if parts.scheme == "https" and parts.netloc:
        return raw
    if parts.scheme == "http" and parts.hostname in _LOCAL_HOSTS:
        return raw
    raise ValueError(f"{name} must be https:// (http:// is allowed for localhost only)")


def endpoints_from_env(env: Mapping[str, str] | None = None) -> Endpoints:
    """Read the endpoint variables. Raises ``NotConfigured`` if a required one is empty."""
    source = os.environ if env is None else env
    asr = (source.get(ENV_ASR_URL) or "").strip()
    tts = (source.get(ENV_TTS_URL) or "").strip()
    missing = [name for name, value in ((ENV_ASR_URL, asr), (ENV_TTS_URL, tts)) if not value]
    if missing:
        raise NotConfigured(missing)
    return Endpoints(
        asr_url=_checked_url(ENV_ASR_URL, asr),
        tts_url=_checked_url(ENV_TTS_URL, tts),
        token=(source.get(ENV_TOKEN) or "").strip(),
    )


class HttpVoiceStages:
    """ASR and TTS calls to self-hosted endpoints, following the contract above."""

    def __init__(
        self, endpoints: Endpoints, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._endpoints = endpoints
        self._client = httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=transport)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._endpoints.token}"} if self._endpoints.token else {}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def asr(self, audio: bytes, language: str) -> str:
        response = await self._client.post(
            self._endpoints.asr_url,
            headers=self._headers(),
            files={"file": ("clip.wav", audio, "audio/wav")},
            data={"language": language},
        )
        response.raise_for_status()
        body = response.json()
        text = body.get("text") if isinstance(body, dict) else None
        if not isinstance(text, str):
            raise ValueError("ASR response has no 'text' field")
        return text

    async def tts(self, text: str, language: str) -> bytes:
        response = await self._client.post(
            self._endpoints.tts_url,
            headers=self._headers(),
            json={"text": text, "language": language},
        )
        response.raise_for_status()
        return response.content


def make_llm_stage(provider: Any) -> LlmFn:
    """Wrap the app's model provider (Gemini chain, with its fallbacks) as the LLM stage."""

    async def llm(user_text: str) -> str:
        request = ModelRequest(
            prompt=user_text,
            system_prompt=LLM_SYSTEM_PROMPT,
            max_tokens=LLM_MAX_TOKENS,
            temperature=0.4,
        )
        response = await provider.complete_with_fallback(LLM_CHAIN, request)
        return str(getattr(response, "content", "") or "").strip()

    return llm
