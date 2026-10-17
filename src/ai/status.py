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
    """Which answer providers exist, and whether the public KB index is queryable."""
    from src.ai.router import last_handoff_reason
    from src.services.rag import embeddings

    env = {name: bool((os.getenv(name) or "").strip()) for name in ENV_FLAGS}
    try:
        embedder_name = embeddings.get_embedder().name
    except Exception as exc:  # noqa: BLE001
        log.warning("ai status embedder check failed: %s", type(exc).__name__)
        embedder_name = "unavailable"
    out = {
        "env": env,
        "fast_configured": env["GROQ_API_KEY"],
        "deep_configured": env["DEEP_MODEL_KEY"],
        "embedder": embedder_name,
        "pgvector": False,
        "index_ready": False,
        "indexed_chunks": 0,
        "last_handoff_reason": last_handoff_reason(),
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
