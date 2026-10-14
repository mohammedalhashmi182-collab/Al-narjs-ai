"""pgvector path against a real Postgres (opt-in: set RAG_PG_TEST_URL to an
empty throwaway database, e.g. postgresql+asyncpg://postgres@/ragtest?host=/tmp/pg).
Never point this at production."""
from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

URL = os.getenv("RAG_PG_TEST_URL")
pytestmark = pytest.mark.skipif(not URL, reason="RAG_PG_TEST_URL not set (needs a throwaway Postgres with pgvector)")


async def test_pgvector_retrieval_is_tenant_scoped():
    from src.db.session import Base
    from src.models import ClientProject
    from src.services import rag
    from src.services.agent_tools import knowledge_base
    from src.services.rag import store

    engine = create_async_engine(URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("ALTER TABLE agent_knowledge_chunks ADD COLUMN IF NOT EXISTS embedding_vec vector"))
    store._PGV.clear()
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as s:
            a = ClientProject(client_name="أ", phone="0555000201", package="radd", status="active")
            b = ClientProject(client_name="ب", phone="0555000202", package="radd", status="active")
            s.add_all([a, b])
            await s.flush()
            await knowledge_base.add_doc(s, "FAQ", "تنظيف الأسنان: السعر 250 ريال.\n\nالجمعة مغلق.", project_id=a.id)
            await knowledge_base.add_doc(s, "FAQ", "قص الشعر: 80 ريال.", project_id=b.id)
            assert await store.pgvector_ready(s)
            n = (await s.execute(text("SELECT count(*) FROM agent_knowledge_chunks WHERE embedding_vec IS NOT NULL"))).scalar()
            assert n == 3
            hits = await rag.retrieve(s, "بكم تنظيف الاسنان؟", project_id=a.id, k=5)
            assert "250" in hits[0]["text"] and all("الشعر" not in h["text"] for h in hits)
            assert all("الأسنان" not in h["text"] for h in await rag.retrieve(s, "تنظيف الأسنان", project_id=b.id, k=5))
            assert await rag.retrieve(s, "تنظيف الأسنان", project_id=None, k=5) == []
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
        store._PGV.clear()
