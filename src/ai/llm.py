"""Minimal OpenAI-compatible chat clients for the router. Keys come from env only."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import httpx

from src.core import pii_mask

log = logging.getLogger(__name__)

TIMEOUT_S = 3.0
# Truncation and safety filters are not a complete answer.
BAD_FINISH = frozenset({"length", "content_filter"})
# Groq shut llama-3.3-70b-versatile and llama-3.1-8b-instant down on 2026-08-16
# for free and developer tiers (404 model_not_found). gpt-oss-120b is the
# replacement Groq documents for the 70B model.
GROQ_MODEL = "openai/gpt-oss-120b"
_RETIRED_GROQ = {
    "llama-3.3-70b-versatile": GROQ_MODEL,
    "llama-3.1-70b-versatile": GROQ_MODEL,
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
}
_retired_groq_logged = False


class LLMError(Exception):
    """Provider failed (HTTP error, timeout, missing key). Message never carries the key."""


@dataclass
class ChatResult:
    text: str
    finish_reason: str | None = "stop"


def as_chat_result(raw) -> ChatResult:
    """Accept a ChatResult or a plain string from tests and older callers."""
    if isinstance(raw, ChatResult):
        return raw
    return ChatResult(str(raw or ""), "stop")


@dataclass
class Provider:
    name: str
    base_url: str
    model: str
    key_env: str

    @property
    def configured(self) -> bool:
        return bool(os.getenv(self.key_env))

    def _log_failure(self, exc: BaseException) -> None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        # Class and status only. The body can echo the customer question.
        log.warning(
            "llm provider=%s error=%s status=%s",
            self.name,
            type(exc).__name__,
            status if status is not None else "-",
        )

    async def chat(self, system: str, user: str, *, timeout: float = TIMEOUT_S) -> ChatResult:
        key = os.getenv(self.key_env)
        if not key:
            raise LLMError(f"{self.name}: not configured")
        mapping: dict[str, str] = {}
        if pii_mask.enabled():
            system, mapping = pii_mask.mask(system, mapping)
            user, mapping = pii_mask.mask(user, mapping)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if uses_native_gemini(self.base_url):
                    return await self._gemini_native(client, key, system, user, mapping)
                return await self._openai_chat(client, key, system, user, mapping)
        except httpx.TimeoutException as exc:
            self._log_failure(exc)
            raise LLMError(f"{self.name}: timeout") from exc
        except (httpx.HTTPError, KeyError, IndexError, ValueError, AttributeError) as exc:
            self._log_failure(exc)
            raise LLMError(f"{self.name}: {type(exc).__name__}") from exc

    async def _openai_chat(self, client: httpx.AsyncClient, key: str, system: str, user: str,
                           mapping: dict[str, str]) -> ChatResult:
        body: dict = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        # gpt-oss reasons by default and can blow the 3s budget or return an
        # empty content field. Low effort keeps the answer in message.content.
        if self.model.startswith("openai/gpt-oss"):
            body["reasoning_effort"] = "low"
        r = await client.post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json=body,
        )
        r.raise_for_status()
        choice = r.json()["choices"][0]
        text = pii_mask.unmask((choice.get("message") or {}).get("content") or "", mapping).strip()
        reason = choice.get("finish_reason") or "stop"
        return ChatResult(text, str(reason))

    async def _gemini_native(self, client: httpx.AsyncClient, key: str, system: str, user: str,
                             mapping: dict[str, str]) -> ChatResult:
        """Native generateContent. The OpenAI-compat /openai/chat/completions path 404s."""
        model = self.model.split("/")[-1] or GEMINI_DEEP_MODEL
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        generation: dict = {"temperature": 0.2}
        if model.startswith("gemini-2.5"):
            generation["thinkingConfig"] = {"thinkingBudget": 0}
        r = await client.post(
            url,
            headers={"x-goog-api-key": key},
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": generation,
            },
        )
        r.raise_for_status()
        data = r.json()
        if (data.get("promptFeedback") or {}).get("blockReason"):
            return ChatResult("", "content_filter")
        candidates = data.get("candidates") or []
        if not candidates:
            raise LLMError(f"{self.name}: empty")
        candidate = candidates[0]
        parts = ((candidate.get("content") or {}).get("parts")) or []
        raw = "".join(part.get("text") or "" for part in parts if not part.get("thought"))
        text = pii_mask.unmask(raw, mapping).strip()
        finish = str(candidate.get("finishReason") or "STOP")
        mapped = {
            "STOP": "stop",
            "MAX_TOKENS": "length",
            "SAFETY": "content_filter",
            "RECITATION": "content_filter",
            "BLOCKLIST": "content_filter",
            "PROHIBITED_CONTENT": "content_filter",
            "SPII": "content_filter",
        }.get(finish, "stop")
        return ChatResult(text, mapped)


def uses_native_gemini(base_url: str) -> bool:
    """Gemini's OpenAI-compatible chat URL returns 404. Native generateContent works."""
    return "generativelanguage.googleapis.com" in (base_url or "").lower()


def groq_model() -> str:
    """Live Groq model. Retired ids are replaced so a stale env var still answers."""
    global _retired_groq_logged
    raw = _env("GROQ_DEFAULT_MODEL") or GROQ_MODEL
    replacement = _RETIRED_GROQ.get(raw)
    if not replacement:
        return raw
    if not _retired_groq_logged:
        log.warning("groq model %s is retired; using %s", raw, replacement)
        _retired_groq_logged = True
    return replacement


def fast_provider() -> Provider:
    return Provider(
        "groq",
        os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        groq_model(),
        "GROQ_API_KEY",
    )


# Kept so an existing Gemini OpenAI-compat base URL still selects Gemini.
# Chat does not POST there: that path returns 404. Native generateContent is used.
GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_DEEP_MODEL = "gemini-2.5-flash"


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def deep_provider() -> Provider:
    """Deep chat. OpenAI stays on ``/chat/completions``.

    Gemini does not. ``POST .../v1beta/openai/chat/completions`` returns 404,
    so a Gemini base URL (including ``GEMINI_OPENAI_BASE``) calls native
    ``models/{model}:generateContent`` with the same key. Default model is
    ``gemini-2.5-flash``.

    When ``DEEP_MODEL_KEY`` is empty and ``GEMINI_API_KEY`` is set, that
    Gemini path is used. A non-empty ``DEEP_MODEL_NAME`` still overrides.
    """
    base = _env("DEEP_MODEL_BASE_URL")
    model = _env("DEEP_MODEL_NAME")
    if _env("DEEP_MODEL_KEY"):
        return Provider(
            "deep",
            base or "https://api.openai.com/v1",
            model or "gpt-4o",
            "DEEP_MODEL_KEY",
        )
    if _env("GEMINI_API_KEY"):
        return Provider(
            "deep",
            base or GEMINI_OPENAI_BASE,
            model or GEMINI_DEEP_MODEL,
            "GEMINI_API_KEY",
        )
    return Provider(
        "deep",
        base or "https://api.openai.com/v1",
        model or "gpt-4o",
        "DEEP_MODEL_KEY",
    )
