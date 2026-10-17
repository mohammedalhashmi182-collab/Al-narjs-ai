"""Arabic-capable text embeddings with a configurable provider.

``EMBEDDING_PROVIDER`` overrides ``RAG_EMBED_PROVIDER`` when set.
  auto    (default) Gemini native embeddings when ``GEMINI_API_KEY`` is set,
          else hash. OpenAI is not used unless the provider is explicitly
          ``openai``. Local MiniLM is not in this path.
  openai  OpenAI ``text-embedding-3-small``. On failure, Gemini.
  gemini  ``gemini-embedding-001`` via native ``batchEmbedContents``.
          ``text-embedding-004`` was shut down and is not requested.
  local   opt-in ``paraphrase-multilingual-MiniLM-L12-v2`` (384-d). The
          Render web service is the starter plan (512 MB). The weights are
          about 470 MB and torch needs more on top, so this is never the
          default and never a silent fallback.
  hash    explicit character n-gram hashing. A hash vector that exists only
          because a real provider failed is not used to answer.

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

    async def _post(self, texts: list[str], *, kind: str, model: str) -> list[list[float]]:
        import httpx

        task = "RETRIEVAL_QUERY" if kind == "query" else "RETRIEVAL_DOCUMENT"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
        reqs = [{"model": f"models/{model}", "content": {"parts": [{"text": canonical_text(t)}]},
                 "taskType": task, "outputDimensionality": self.dim} for t in texts]
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            r = await c.post(url, headers={"x-goog-api-key": self.api_key}, json={"requests": reqs})
        if r.status_code != 200:
            raise RuntimeError(f"gemini embeddings http {r.status_code}")
        vecs = [_l2(e["values"]) for e in r.json()["embeddings"]]
        if vecs:
            self.dim = len(vecs[0])
        return vecs

    async def embed(self, texts: list[str], *, kind: str = "doc") -> list[list[float]]:
        try:
            return await self._post(texts, kind=kind, model=self.model)
        except RuntimeError as exc:
            # A retired id such as text-embedding-004 is a 404. The supported
            # native model is gemini-embedding-001.
            if self.model != GEMINI_EMBED_MODEL and "404" in str(exc):
                log.warning("gemini embedding model %s unavailable; using %s", self.model, GEMINI_EMBED_MODEL)
                self.model = GEMINI_EMBED_MODEL
                return await self._post(texts, kind=kind, model=self.model)
            raise


# paraphrase-multilingual-MiniLM-L12-v2. 384 dimensions, weights about 470 MB.
# Not loaded unless the provider is explicitly local.
LOCAL_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
LOCAL_DIM = 384


class LocalEmbedder:
    """Opt-in multilingual MiniLM via sentence-transformers.

    Production stays on Gemini. ``render.yaml`` pins the web service to the
    starter plan, which Render documents as 512 MB RAM. The model file is
    about 470 MB and a CPU torch runtime needs more than the instance has
    left, so this class is constructed only for ``EMBEDDING_PROVIDER=local``
    (or ``RAG_EMBED_PROVIDER=local``). The package is not part of the image.
    """

    _models: dict = {}

    def __init__(self, model: str = LOCAL_MODEL):
        self.model = model
        self.dim = LOCAL_DIM

    @property
    def name(self) -> str:
        return f"local:{self.model}"

    async def embed(self, texts: list[str], *, kind: str = "doc") -> list[list[float]]:
        import asyncio

        m = self._models.get(self.model)
        if m is None:
            m = self._models[self.model] = _load_local_model(self.model)
            width = getattr(m, "get_sentence_embedding_dimension", lambda: self.dim)()
            if width:
                self.dim = int(width)
        # Same normalized text as the API embedders. MiniLM has no query/passage prefix.
        inputs = [canonical_text(t) for t in texts]
        vecs = await asyncio.to_thread(m.encode, inputs, normalize_embeddings=True)
        out = [list(map(float, v)) for v in vecs]
        if out:
            self.dim = len(out[0])
        return out


def _load_local_model(model: str):
    from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

    return SentenceTransformer(model)


def _has_local() -> bool:
    import importlib.util

    return importlib.util.find_spec("sentence_transformers") is not None


class EmbeddingUnavailable(Exception):
    """Every real embedding provider failed. Hash is not an answer."""


_hash_fallback_logged = False

GEMINI_EMBED_MODEL = "gemini-embedding-001"


def _provider_choice() -> str:
    """``EMBEDDING_PROVIDER`` is the explicit selector. ``RAG_EMBED_PROVIDER`` remains."""
    explicit = (os.getenv("EMBEDDING_PROVIDER") or "").strip().lower()
    if explicit:
        return explicit
    return (os.getenv("RAG_EMBED_PROVIDER") or "auto").strip().lower() or "auto"


def _configured_model() -> str:
    return (os.getenv("RAG_EMBED_MODEL") or "").strip()


def _gemini_model(configured: str) -> str:
    if not configured or configured.startswith("text-embedding") or configured in {"embedding-001"}:
        return GEMINI_EMBED_MODEL
    return configured


def _openai_model(configured: str) -> str:
    if not configured or "gemini" in configured or configured.startswith("embedding"):
        return "text-embedding-3-small"
    return configured


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


def _gemini_embedder(configured: str) -> GeminiEmbedder | None:
    key = _key("GEMINI_API_KEY")
    if not key:
        return None
    return GeminiEmbedder(key, _gemini_model(configured))


def _openai_embedder(configured: str) -> OpenAIEmbedder | None:
    key = _key("OPENAI_API_KEY")
    if not key:
        return None
    model = _openai_model(configured)
    dim = 3072 if "large" in model else 1536
    return OpenAIEmbedder(key, model, dim)


def _looks_like_local_model(configured: str) -> bool:
    name = configured.lower()
    return "minilm" in name or name.startswith("paraphrase-") or name.startswith("sentence-transformers/")


def _local_embedder(configured: str) -> LocalEmbedder | None:
    if not _has_local():
        return None
    model = configured if _looks_like_local_model(configured) else ""
    return LocalEmbedder(model or LOCAL_MODEL)


_local_missing_logged = False


def _warn_local_unavailable() -> None:
    """One line. The package is absent, so MiniLM is not loaded."""
    global _local_missing_logged
    if _local_missing_logged:
        return
    _local_missing_logged = True
    log.warning(
        "EMBEDDING_PROVIDER=local but sentence-transformers is not installed; "
        "MiniLM was not loaded. Gemini is next when GEMINI_API_KEY is set"
    )


def candidate_embedders() -> list[Embedder]:
    """Real providers in try-order.

    OpenAI is included only when explicitly selected. MiniLM is included only
    when the provider is ``local``: loading torch on the 512 MB starter
    instance is not a fallback.
    """
    choice = _provider_choice()
    configured = _configured_model()
    if choice == "hash":
        return [HashEmbedder()]
    ordered: list[Embedder | None]
    if choice == "openai":
        ordered = [_openai_embedder(configured), _gemini_embedder(configured)]
    elif choice == "local":
        local = _local_embedder(configured)
        if local is None:
            _warn_local_unavailable()
        ordered = [local, _gemini_embedder(configured)]
    else:
        # auto and gemini: native Gemini. An invalid OpenAI key is ignored.
        ordered = [_gemini_embedder(configured)]
    return [item for item in ordered if item is not None]


def get_embedder() -> Embedder:
    if _override is not None:
        return _override
    chain = candidate_embedders()
    if chain:
        return chain[0]
    choice = _provider_choice()
    if choice not in ("auto", "hash"):
        log.warning("embedding provider %s unavailable (missing key or package); using hash embeddings", choice)
    return HashEmbedder()


def _log_hash_fallback_once(provider_name: str, exc: BaseException) -> None:
    """One loud line per process. The question and the key are not included."""
    global _hash_fallback_logged
    if _hash_fallback_logged:
        return
    _hash_fallback_logged = True
    log.error(
        "embedding provider %s failed (%s); hash fallback will not be used to answer",
        provider_name,
        type(exc).__name__,
    )


async def embed_safe(embedder: Embedder, texts: list[str], *, kind: str = "doc") -> tuple[Embedder, list[list[float]]]:
    """Embed with ``embedder``, then the next real provider.

    Explicit hash embeddings are returned as-is. When every real provider
    fails, this raises :class:`EmbeddingUnavailable` instead of answering
    with a hash vector.
    """
    if isinstance(embedder, HashEmbedder):
        return embedder, await embedder.embed(texts, kind=kind)
    chain: list[Embedder] = []
    seen: set[str] = set()
    for item in (embedder, *candidate_embedders()):
        if isinstance(item, HashEmbedder):
            continue
        if item.name in seen:
            continue
        seen.add(item.name)
        chain.append(item)
    last: BaseException | None = None
    last_name = embedder.name
    for item in chain:
        try:
            return item, await item.embed(texts, kind=kind)
        except Exception as exc:  # noqa: BLE001
            last = exc
            last_name = item.name
            log.warning("embedding provider %s failed (%s)", item.name, type(exc).__name__)
    if last is not None:
        _log_hash_fallback_once(last_name, last)
    raise EmbeddingUnavailable(last_name)
