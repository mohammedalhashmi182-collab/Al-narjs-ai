"""Minimal OpenAI-compatible chat clients for the router. Keys come from env only."""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

from src.core import pii_mask

TIMEOUT_S = 3.0
# Truncation and safety filters are not a complete answer.
BAD_FINISH = frozenset({"length", "content_filter"})


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
                r = await client.post(
                    f"{self.base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={
                        "model": self.model,
                        "temperature": 0.2,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                    },
                )
                r.raise_for_status()
                choice = r.json()["choices"][0]
                text = pii_mask.unmask((choice.get("message") or {}).get("content") or "", mapping).strip()
                reason = choice.get("finish_reason") or "stop"
                return ChatResult(text, str(reason))
        except httpx.TimeoutException as exc:
            raise LLMError(f"{self.name}: timeout") from exc
        except (httpx.HTTPError, KeyError, IndexError, ValueError, AttributeError) as exc:
            # Type name only: the provider body can echo the prompt (PII).
            raise LLMError(f"{self.name}: {type(exc).__name__}") from exc


def fast_provider() -> Provider:
    return Provider(
        "groq",
        os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        os.getenv("GROQ_DEFAULT_MODEL", "llama-3.3-70b-versatile"),
        "GROQ_API_KEY",
    )


# Gemini's OpenAI-compatible chat endpoint. A Gemini key in DEEP_MODEL_KEY with
# this base URL and DEEP_MODEL_NAME=gemini-2.5-flash is a valid deep model.
GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_DEEP_MODEL = "gemini-2.5-flash"


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def deep_provider() -> Provider:
    """OpenAI-compatible deep chat.

    An explicit ``DEEP_MODEL_KEY`` uses ``DEEP_MODEL_BASE_URL`` (OpenAI when
    empty) and ``DEEP_MODEL_NAME`` (``gpt-4o`` when empty). Gemini is that
    same client: set the base URL to ``GEMINI_OPENAI_BASE``, the key to a
    Gemini key, and the name to ``gemini-2.5-flash``.

    When ``DEEP_MODEL_KEY`` is empty and ``GEMINI_API_KEY`` is set, those
    Gemini defaults are used. A non-empty ``DEEP_MODEL_BASE_URL`` or
    ``DEEP_MODEL_NAME`` still overrides the default.
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
