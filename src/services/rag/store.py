"""Index and retrieve knowledge-base chunks, strictly per tenant.

Retrieval = hybrid score of vector similarity (pgvector ``<=>`` on Postgres,
in-process cosine elsewhere) and normalized-term coverage of the question.
Every query is filtered by ``project_id`` first (``IS NULL`` for Al-Narjis's
own KB): a tenant can never retrieve another tenant's text (lesson 5).

Confidence (0..1) = ``VEC_W * cosine + LEX_W * coverage`` of the best chunk;
callers compare it with ``min_confidence()`` and hand off below it.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
from uuid import UUID

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.pii_mask import for_embedding
from src.models.agent_tools import KnowledgeDoc
from src.models.rag import KnowledgeChunk

from . import embeddings
from .arabic import light_stem, terms

log = logging.getLogger(__name__)

VEC_W = 0.5
LEX_W = 0.5
CHUNK_CHARS = int(os.getenv("RAG_CHUNK_CHARS", "450"))
CANDIDATES = 24


def min_confidence() -> float:
    try:
        return float(os.getenv("RAG_MIN_CONFIDENCE", "0.42"))
    except ValueError:
        return 0.42


def chunk_text(content: str) -> list[str]:
    """Paragraph chunks (one FAQ entry stays together); long paragraphs split on sentences."""
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n(?=[-•*]|\d+[.)]\s)", content or "") if p.strip()]
    out: list[str] = []
    for p in paras:
        if len(p) <= CHUNK_CHARS:
            out.append(p)
            continue
        cur = ""
        for s in re.split(r"(?<=[.!?؟。\n])\s+", p):
            if cur and len(cur) + len(s) > CHUNK_CHARS:
                out.append(cur)
                cur = ""
            cur = f"{cur} {s}".strip()
            while len(cur) > CHUNK_CHARS * 2:
                out.append(cur[:CHUNK_CHARS])
                cur = cur[CHUNK_CHARS:]
        if cur:
            out.append(cur)
    return out


def doc_hash(doc: KnowledgeDoc) -> str:
    return hashlib.sha256(f"{doc.title}\n{doc.content}".encode()).hexdigest()


def _tenant(col, project_id: UUID | None):
    return col.is_(None) if project_id is None else col == project_id


# --------------------------------------------------------------------------- pgvector

_PGV: dict[str, bool] = {}


async def pgvector_ready(session: AsyncSession) -> bool:
    """True when the DB is Postgres, the ``vector`` extension is installed and the column exists."""
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return False
    key = str(bind.url)
    if key not in _PGV:
        try:
            ok = (await session.execute(text(
                "SELECT 1 FROM information_schema.columns WHERE table_name='agent_knowledge_chunks' "
                "AND column_name='embedding_vec'"))).first() is not None
        except Exception:  # noqa: BLE001
            ok = False
        _PGV[key] = ok
    return _PGV[key]


def _vec_literal(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


# --------------------------------------------------------------------------- indexing

# Same key as ``src.ai.rag`` so the background indexer and this check agree.
# Indexing never takes a schema lock and never drops ``embedding_vec``.
_vector_dim_state: dict[str, str] = {}
_vector_dim_warned: set[str] = set()

# Hand-run only: ``python scripts/rebuild_embedding_vec.py``
VECTOR_REBUILD_SQL = (
    "ALTER TABLE agent_knowledge_chunks DROP COLUMN embedding_vec",
    "ALTER TABLE agent_knowledge_chunks ADD COLUMN embedding_vec vector",
)


def _vector_type_needs_rebuild(declared: str, dim: int) -> bool:
    """True when ``embedding_vec`` is ``vector(N)`` and N is not ``dim``.

    An unconstrained ``vector`` column already accepts the new width.
    """
    text_type = (declared or "").strip().lower()
    if not text_type.startswith("vector(") or not text_type.endswith(")"):
        return False
    try:
        declared_dim = int(text_type[len("vector("):-1])
    except ValueError:
        return False
    return declared_dim != dim


def _bind_key(bind) -> str:
    return str(getattr(bind, "url", id(bind)))


async def ensure_vector_dim(session: AsyncSession, dim: int) -> bool:
    """True when ``embedding_vec`` can store ``dim``.

    A fixed ``vector(N)`` that does not match is left untouched. Indexing must
    not ``DROP COLUMN`` on a live request. The admin command is
    ``python scripts/rebuild_embedding_vec.py``.
    """
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return False
    key = _bind_key(bind)
    state = _vector_dim_state.get(key)
    if state == f"ok:{dim}":
        return True
    if state is not None and state.startswith("blocked:"):
        return False
    declared = (await session.execute(text(
        "SELECT format_type(a.atttypid, a.atttypmod) "
        "FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid "
        "WHERE c.relname = 'agent_knowledge_chunks' AND a.attname = 'embedding_vec' "
        "AND NOT a.attisdropped"
    ))).scalar()
    declared_s = str(declared or "")
    if _vector_type_needs_rebuild(declared_s, dim):
        if key not in _vector_dim_warned:
            _vector_dim_warned.add(key)
            log.warning(
                "pgvector embedding_vec is %s; embeddings are dim %s. "
                "Refusing to DROP COLUMN at runtime. "
                "Run: python scripts/rebuild_embedding_vec.py",
                declared_s, dim,
            )
        _vector_dim_state[key] = f"blocked:{declared_s}"
        return False
    _vector_dim_state[key] = f"ok:{dim}"
    return True


async def rebuild_embedding_vec_column(session: AsyncSession) -> None:
    """Manual admin path: recreate ``embedding_vec`` as unconstrained ``vector``.

    Not called from ``index_doc`` or from a customer request. Run
    ``scripts/rebuild_embedding_vec.py``.
    """
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("embedding_vec rebuild is postgres only")
    for statement in VECTOR_REBUILD_SQL:
        await session.execute(text(statement))
    key = _bind_key(bind)
    _vector_dim_state.pop(key, None)
    _vector_dim_warned.discard(key)
    _PGV.pop(key, None)


async def index_doc(session: AsyncSession, doc: KnowledgeDoc, embedder: embeddings.Embedder | None = None) -> int:
    """(Re)build the chunk vectors of one document for the current embedder. Flushes, no commit."""
    embedder = embedder or embeddings.get_embedder()
    parts = chunk_text(doc.content)
    if not parts:
        return 0
    embedder, vecs = await embeddings.embed_safe(embedder, [f"{doc.title}\n{p}" for p in parts], kind="doc")
    # Drop every previous provider for this doc. Retrieval is filtered by
    # model and dim, and a provider switch must not leave the old vectors behind.
    await session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc.id))
    h = doc_hash(doc)
    rows = [KnowledgeChunk(doc_id=doc.id, project_id=doc.project_id, chunk_index=i, doc_hash=h, title=doc.title[:255], text=p,
                           model=embedder.name, dim=len(v), embedding=v) for i, (p, v) in enumerate(zip(parts, vecs, strict=True))]
    session.add_all(rows)
    await session.flush()
    if rows and await pgvector_ready(session) and await ensure_vector_dim(session, rows[0].dim):
        for r in rows:
            await session.execute(text("UPDATE agent_knowledge_chunks SET embedding_vec = CAST(:v AS vector) WHERE id = :id"),
                                  {"v": _vec_literal(r.embedding), "id": r.id})
    return len(rows)


async def delete_doc_chunks(session: AsyncSession, doc_id: UUID) -> None:
    await session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc_id))


async def reindex_openai_tenant_docs(session: AsyncSession, embedder: embeddings.Embedder | None = None) -> int:
    """Re-embed tenant docs still stored as OpenAI 1536-d vectors.

    The background indexer calls this under the Postgres advisory lock. A
    customer message must not: rewriting a tenant corpus on the first question
    blows the reply budget.
    """
    embedder = embedder or embeddings.get_embedder()
    doc_ids = list((await session.execute(
        select(KnowledgeChunk.doc_id).where(
            KnowledgeChunk.project_id.is_not(None),
            KnowledgeChunk.dim == 1536,
            KnowledgeChunk.model.like("openai:%"),
        ).distinct()
    )).scalars())
    n = 0
    for doc_id in doc_ids:
        doc = await session.get(KnowledgeDoc, doc_id)
        if doc is None or doc.project_id is None:
            continue
        await index_doc(session, doc, embedder)
        n += 1
    if n:
        log.info("tenant openai reindex docs=%s model=%s", n, embedder.name)
    return n


async def ensure_indexed(session: AsyncSession, project_id: UUID | None, embedder: embeddings.Embedder) -> None:
    """Lazy backfill: index this tenant's docs that have no chunks for ``embedder`` yet."""
    docs = list((await session.execute(select(KnowledgeDoc).where(_tenant(KnowledgeDoc.project_id, project_id)))).scalars())
    if not docs:
        return
    have = {(d, h, dim) for d, h, dim in (await session.execute(
        select(KnowledgeChunk.doc_id, KnowledgeChunk.doc_hash, KnowledgeChunk.dim).where(
            _tenant(KnowledgeChunk.project_id, project_id), KnowledgeChunk.model == embedder.name).distinct()
    )).all()}
    # Already-stored OpenAI 1536 vectors are rewritten by the background
    # indexer. Building them on the customer message misses the reply budget.
    openai_docs = set((await session.execute(
        select(KnowledgeChunk.doc_id).where(
            _tenant(KnowledgeChunk.project_id, project_id),
            KnowledgeChunk.dim == 1536,
            KnowledgeChunk.model.like("openai:%"),
        ).distinct()
    )).scalars())
    width = int(embedder.dim)
    for d in docs:
        if d.id in openai_docs:
            continue
        # A new provider name misses this set. A new vector width misses it too.
        if (d.id, doc_hash(d), width) not in have:
            await index_doc(session, d, embedder)


# --------------------------------------------------------------------------- retrieval

def coverage(q_terms: list[str], chunk: str) -> float:
    if not q_terms:
        return 0.0
    c = {light_stem(t) for t in terms(chunk)}
    qs = {light_stem(t) for t in q_terms}
    return len(qs & c) / len(qs)


async def retrieve(session: AsyncSession, query: str, *, project_id: UUID | None, k: int = 3,
                   embedder: embeddings.Embedder | None = None,
                   title_prefix: str | None = None,
                   ensure: bool = True) -> list[dict]:
    """Top-k chunks of ONE tenant with ``score`` (0..1), ``cosine`` and ``coverage``.

    ``title_prefix`` limits the search to one corpus (the public KB uses ``kb:``)
    so a company question never mixes in another document set.
    """
    embedder = embedder or embeddings.get_embedder()
    # The vector leaves for the embedding provider. The lexical terms below
    # stay on the original question so a masked token does not drop the match.
    # The wait is inside the 10s ask budget even if RAG_EMBED_TIMEOUT is larger.
    embedder, (qv,) = await asyncio.wait_for(
        embeddings.embed_safe(embedder, [for_embedding(query)], kind="query"),
        timeout=embeddings.query_embed_timeout(),
    )
    # The public ask path indexes in the background. Building vectors here
    # made the first customer request embed the whole KB.
    if ensure:
        await ensure_indexed(session, project_id, embedder)
    q_terms = terms(query)
    rows: list[tuple[str, str, list[float] | None, float | None]] = []
    if await pgvector_ready(session):
        prefix_sql = " AND title LIKE :pref" if title_prefix else ""
        res = await session.execute(text(
            "SELECT title, text, 1 - (embedding_vec <=> CAST(:q AS vector)) AS cos FROM agent_knowledge_chunks "
            "WHERE model = :m AND " + ("project_id IS NULL" if project_id is None else "project_id = :p") +
            " AND embedding_vec IS NOT NULL AND dim = :dim" + prefix_sql +
            " ORDER BY embedding_vec <=> CAST(:q AS vector) LIMIT :n"),
            {"q": _vec_literal(qv), "m": embedder.name, "p": project_id, "n": CANDIDATES * 4,
             "dim": int(embedder.dim), "pref": f"{title_prefix}%" if title_prefix else None})
        rows = [(t, x, None, float(c)) for t, x, c in res.all()]
    else:
        stmt = select(KnowledgeChunk.title, KnowledgeChunk.text, KnowledgeChunk.embedding).where(
            _tenant(KnowledgeChunk.project_id, project_id), KnowledgeChunk.model == embedder.name,
            KnowledgeChunk.dim == int(embedder.dim))
        if title_prefix:
            stmt = stmt.where(KnowledgeChunk.title.startswith(title_prefix))
        res = await session.execute(stmt)
        rows = [(t, x, v, None) for t, x, v in res.all()]
    scored = []
    for title, body, vec, cos in rows:
        cos = embeddings.cosine(qv, vec) if cos is None else cos
        cov = coverage(q_terms, f"{title} {body}")
        score = VEC_W * max(0.0, cos) + LEX_W * cov
        scored.append({"title": title, "text": body, "score": round(score, 4), "cosine": round(cos, 4),
                       "coverage": round(cov, 4)})
    scored.sort(key=lambda h: -h["score"])
    return scored[:k]


async def chunk_count(session: AsyncSession, project_id: UUID | None) -> int:
    return int((await session.execute(select(func.count()).select_from(KnowledgeChunk).where(
        _tenant(KnowledgeChunk.project_id, project_id)))).scalar() or 0)
