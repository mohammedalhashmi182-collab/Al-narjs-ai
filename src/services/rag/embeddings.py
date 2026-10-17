"""Arabic-capable text embeddings with a configurable provider.

``RAG_EMBED_PROVIDER`` (env):
  auto    (default) openai if OPENAI_API_KEY, else gemini if GEMINI_API_KEY,
          else local if sentence-transformers is installed, else hash
  openai  OpenAI ``text-embedding-3-small`` (``RAG_EMBED_MODEL`` to override,
          e.g. text-embedding-3-large)
  gemini  Google ``gemini-embedding-001`` (``RAG_EMBED_MODEL`` to override)
  local   sentence-transformers ``intfloat/multilingual-e5-small`` (optional
          dependency, CPU, no network after the model download)
  hash    deterministic character n-gram hashing (no network, no dependency).
          Works for Arabic spelling variants; used in tests and as the last
          resort so retrieval never goes down with a provider.

Every provider embeds the *normalized* text (``arabic.canonical_text``) so
dialect/spelling variants land close together. Vectors are L2-normalized.
Keys are read from settings/env and never logged.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
from dataclasses import dataclass
from typing import Protocol

from .arabic import canonical_text, light_stem, normalize, terms

log = logging.getLogger(__name__)

HASH_DIM = 768
# A customer question must embed inside the 10s ask budget. Document indexing
# uses the same default; ``RAG_EMBED_TIMEOUT`` can raise it, but a query never
# waits longer than ``QUERY_EMBED_S``.
QUERY_EMBED_S = 4.0
TIMEOUT = float(os.getenv("RAG_EMBED_TIMEOUT", str(QUERY_EMBED_S)))


def query_embed_timeout() -> float:
    """Seconds a query embedding may take. Never above ``QUERY_EMBED_S``."""
    try:
        configured = float(os.getenv("RAG_EMBED_TIMEOUT", str(QUERY_EMBED_S)))
    except ValueError:
        configured = QUERY_EMBED_S
    if configured <= 0:
        configured = QUERY_EMBED_S
    return min(configured, QUERY_EMBED_S)


class Embedder(Protocol):
    name: str  # provider:model, stored with every vector (vectors of different models never mix)
    dim: int

    async def embed(self, texts: list[str], *, kind: str = "doc") -> list[list[float]]: ...


def _l2(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=False))


@dataclass
class HashEmbedder:
    dim: int = HASH_DIM
    name: str = "hash:ngram-v1"

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        feats: list[tuple[str, float]] = []
        for t in terms(text):
            st = light_stem(t)
            feats.append(("w:" + st, 2.0))
            padded = f"#{st}#"
            for i in range(len(padded) - 2):
                feats.append(("c:" + padded[i:i + 3], 0.5))
        if not feats:
            for t in normalize(text).split():
                feats.append(("w:" + t, 1.0))
        for f, w in feats:
            h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "big")
            v[h % self.dim] += w if (h >> 63) & 1 else -w
        return _l2(v)

    async def embed(self, texts: list[str], *, kind: str = "doc") -> list[list[float]]:
        return [self._vec(t) for t in texts]


@dataclass
class OpenAIEmbedder:
    api_key: str
    model: str = "text-embedding-3-small"
    dim: int = 1536

    @property
    def name(self) -> str:
        return f"openai:{self.model}"

    async def embed(self, texts: list[str], *, kind: str = "doc") -> list[list[float]]:
        import httpx

        base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.post(f"{base}/embeddings", headers={"Authorization": f"Bearer {self.api_key}"},
                             json={"model": self.model, "input": [canonical_text(t) for t in texts]})
        if r.status_code != 200:
            raise RuntimeError(f"openai embeddings http {r.status_code}")
        data = sorted(r.json()["data"], key=lambda d: d["index"])
        return [_l2(d["embedding"]) for d in data]


@dataclass
class GeminiEmbedder:
    api_key: str
    model: str = "gemini-embedding-001"
    dim: int = 768

    @property
    def name(self) -> str:
        return f"gemini:{self.model}"

    async def embed(self, texts: list[str], *, kind: str = "doc") -> list[list[float]]:
        import httpx

        task = "RETRIEVAL_QUERY" if kind == "query" else "RETRIEVAL_DOCUMENT"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:batchEmbedContents"
        reqs = [{"model": f"models/{self.model}", "content": {"parts": [{"text": canonical_text(t)}]},
                 "taskType": task, "outputDimensionality": self.dim} for t in texts]
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.post(url, headers={"x-goog-api-key": self.api_key}, json={"requests": reqs})
        if r.status_code != 200:
            raise RuntimeError(f"gemini embeddings http {r.status_code}")
        return [_l2(e["values"]) for e in r.json()["embeddings"]]


class LocalE5Embedder:
    """multilingual-e5 via sentence-transformers (optional dependency)."""

    _models: dict = {}

    def __init__(self, model: str = "intfloat/multilingual-e5-small"):
        self.model = model
        self.dim = 384 if "small" in model else 768

    @property
    def name(self) -> str:
        return f"local:{self.model}"

    async def embed(self, texts: list[str], *, kind: str = "doc") -> list[list[float]]:
        import asyncio

        from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

        m = self._models.get(self.model)
        if m is None:
            m = self._models[self.model] = SentenceTransformer(self.model)
        prefix = "query: " if kind == "query" else "passage: "
        inputs = [prefix + normalize(t) for t in texts]
        vecs = await asyncio.to_thread(m.encode, inputs, normalize_embeddings=True)
        return [list(map(float, v)) for v in vecs]


def _has_local() -> bool:
    import importlib.util

    return importlib.util.find_spec("sentence_transformers") is not None


def _key(name: str) -> str | None:
    try:
        from src.config.settings import get_settings

        v = getattr(get_settings(), name.lower(), None)
    except Exception:  # noqa: BLE001
        v = None
    return v or os.getenv(name) or None


_override: Embedder | None = None


def set_embedder(e: Embedder | None) -> None:
    """Test seam / runtime override."""
    global _override
    _override = e


def get_embedder() -> Embedder:
    if _override is not None:
        return _override
    choice = (os.getenv("RAG_EMBED_PROVIDER") or "auto").strip().lower()
    model = (os.getenv("RAG_EMBED_MODEL") or "").strip()
    if choice in ("openai", "auto") and _key("OPENAI_API_KEY"):
        return OpenAIEmbedder(_key("OPENAI_API_KEY") or "", model or "text-embedding-3-small",
                              3072 if "large" in (model or "") else 1536)
    if choice in ("gemini", "auto") and _key("GEMINI_API_KEY"):
        return GeminiEmbedder(_key("GEMINI_API_KEY") or "", model or "gemini-embedding-001")
    if choice in ("local", "auto") and _has_local():
        return LocalE5Embedder(model or "intfloat/multilingual-e5-small")
    if choice not in ("auto", "hash"):
        log.warning("RAG_EMBED_PROVIDER=%s unavailable (missing key or package); using hash embeddings", choice)
    return HashEmbedder()


async def embed_safe(embedder: Embedder, texts: list[str], *, kind: str = "doc") -> tuple[Embedder, list[list[float]]]:
    """Embed with the configured provider; on provider failure fall back to hash (logged, never raises)."""
    try:
        return embedder, await embedder.embed(texts, kind=kind)
    except Exception as exc:  # noqa: BLE001
        if isinstance(embedder, HashEmbedder):
            raise
        log.warning("embedding provider %s failed (%s); falling back to hash", embedder.name, type(exc).__name__)
        h = HashEmbedder()
        return h, await h.embed(texts, kind=kind)
