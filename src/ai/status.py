"""Owner-safe readiness for /api/ai/ask. Booleans and counts only — never a key."""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

# Names only. Values are reported as present/absent.
ENV_FLAGS = (
    "GROQ_API_KEY",
    "DEEP_MODEL_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
)


async def snapshot(session_factory=None) -> dict:
    """Which answer providers exist, and whether the public KB index is queryable.

    Owner-only. The embedder name and the last handoff reason are logs, not
    fields on this payload.
    """
    from src.ai.llm import deep_provider, fast_provider

    env = {name: bool((os.getenv(name) or "").strip()) for name in ENV_FLAGS}
    out = {
        "env": env,
        "fast_configured": fast_provider().configured,
        "deep_configured": deep_provider().configured,
        "pgvector": False,
        "index_ready": False,
        "indexed_chunks": 0,
    }
    if session_factory is None:
        return out
    try:
        from sqlalchemy import func, select

        from src.models.rag import KnowledgeChunk
        from src.services.rag import store

        async with session_factory() as session:
            out["pgvector"] = bool(await store.pgvector_ready(session))
            count = (await session.execute(
                select(func.count()).select_from(KnowledgeChunk).where(
                    KnowledgeChunk.project_id.is_(None),
                    KnowledgeChunk.title.startswith("kb:"),
                )
            )).scalar()
            out["indexed_chunks"] = int(count or 0)
            out["index_ready"] = out["indexed_chunks"] > 0
    except Exception as exc:  # noqa: BLE001
        log.warning("ai status index check failed: %s", type(exc).__name__)
    return out
