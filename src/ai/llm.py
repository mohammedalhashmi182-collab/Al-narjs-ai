"""Minimal OpenAI-compatible chat clients for the router. Keys come from env only."""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

TIMEOUT_S = 3.0


class LLMError(Exception):
    """Provider failed (HTTP error, timeout, missing key). Message never carries the key."""


@dataclass
class Provider:
    name: str
    base_url: str
    model: str
    key_env: str

    @property
    def configured(self) -> bool:
        return bool(os.getenv(self.key_env))

    async def chat(self, system: str, user: str, *, timeout: float = TIMEOUT_S) -> str:
        key = os.getenv(self.key_env)
        if not key:
            raise LLMError(f"{self.name}: not configured")
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
                return r.json()["choices"][0]["message"]["content"].strip()
        except httpx.TimeoutException as exc:
            raise LLMError(f"{self.name}: timeout") from exc
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            # Type name only: the provider body can echo the prompt (PII).
            raise LLMError(f"{self.name}: {type(exc).__name__}") from exc


def fast_provider() -> Provider:
    return Provider(
        "groq",
        os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        os.getenv("GROQ_DEFAULT_MODEL", "llama-3.3-70b-versatile"),
        "GROQ_API_KEY",
    )


def deep_provider() -> Provider:
    return Provider(
        "deep",
        os.getenv("DEEP_MODEL_BASE_URL", "https://api.openai.com/v1"),
        os.getenv("DEEP_MODEL_NAME", "gpt-4o"),
        "DEEP_MODEL_KEY",
    )
