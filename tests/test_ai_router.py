"""LLM router, pgvector RAG and review — all providers mocked, no network."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import src.models  # noqa: F401 — register tables before create_all
from src.ai import rag, router
from src.ai.llm import LLMError
from src.ai.review import parse_verdict
from src.db.session import Base
from src.models.rag import KnowledgeChunk


class FakeLLM:
    def __init__(self, name, replies):
        self.name = name
        self.replies = list(replies)
        self.calls = 0

    async def chat(self, system, user, timeout=3.0):
        self.calls += 1
        r = self.replies.pop(0) if self.replies else LLMError("empty")
        if isinstance(r, Exception):
            raise r
        return r


class FakeKB:
    def __init__(self, hits):
        self.hits = hits

    def retrieve(self, q, k=5):
        return self.hits[:k]


class Down:
    def retrieve(self, q, k=5):
        raise ConnectionError("down")


HITS = [{"text": "باقة ردّ 599 ر.س", "source": "data/kb/narjs_services.md"}]
OK = '{"ok": true, "reason": ""}'
BAD = '{"ok": false, "reason": "سعر غير مدعوم"}'


def test_classify():
    assert router.classify("كم سعر باقة رد") == "fast"
    assert router.classify("أبي أسترد المبلغ، وش سياسة الاسترداد") == "deep"
    assert router.classify("سؤال؟ وسؤال ثاني؟") == "deep"
    assert router.classify("x" * 300) == "deep"


async def test_fast_route_groq():
    fast, deep = FakeLLM("groq", ["باقة ردّ بـ599 ر.س"]), FakeLLM("deep", [])
    r = await router.ask("كم سعر باقة رد", kb=FakeKB(HITS), fast=fast, deep=deep)
    assert r.as_dict() == {
        "answer": "باقة ردّ بـ599 ر.س",
        "route": "fast",
        "sources": ["data/kb/narjs_services.md"],
        "reviewed": False,
    }
    assert deep.calls == 0


async def test_fast_falls_back_to_deep_on_timeout():
    fast, deep = FakeLLM("groq", [LLMError("groq: timeout")]), FakeLLM("deep", ["جواب"])
    r = await router.ask("كم سعر باقة رد", kb=FakeKB(HITS), fast=fast, deep=deep)
    assert r.route == "fast-fallback" and r.answer == "جواب"


async def test_both_fail_handoff():
    fast, deep = FakeLLM("groq", [LLMError("x")]), FakeLLM("deep", [LLMError("y")])
    r = await router.ask("كم سعر باقة رد", kb=FakeKB(HITS), fast=fast, deep=deep)
    assert r.route == "handoff" and r.answer == router.HANDOFF_AR


async def test_deep_reviewed_by_other_model():
    deep, fast = FakeLLM("deep", ["لا استرداد بعد التفعيل"]), FakeLLM("groq", [OK])
    r = await router.ask("وش سياسة الاسترداد", kb=FakeKB(HITS), fast=fast, deep=deep)
    assert r.route == "deep" and r.reviewed is True and fast.calls == 1


async def test_deep_regenerates_once_then_handoff():
    deep, fast = FakeLLM("deep", ["خصم 50%", "خصم 40%"]), FakeLLM("groq", [BAD, BAD])
    r = await router.ask("وش سياسة الاسترداد", kb=FakeKB(HITS), fast=fast, deep=deep)
    assert r.route == "handoff" and deep.calls == 2


async def test_deep_regeneration_passes():
    deep, fast = FakeLLM("deep", ["خصم 50%", "لا استرداد"]), FakeLLM("groq", [BAD, OK])
    r = await router.ask("وش سياسة الاسترداد", kb=FakeKB(HITS), fast=fast, deep=deep)
    assert r.answer == "لا استرداد" and r.reviewed


@pytest.mark.parametrize("ans", ["يحدده محمد", "السعر [X] ريال"])
async def test_placeholder_answers_never_sent(ans):
    r = await router.ask(
        "كم سعر الترجمة", kb=FakeKB(HITS), fast=FakeLLM("groq", [ans]), deep=FakeLLM("deep", []),
    )
    assert r.route == "handoff" and ans not in r.answer


@pytest.mark.parametrize("marker", ["يحدده محمد", "السعر [X] ريال"])
async def test_blocked_chunk_hands_off_before_the_model(marker):
    fast = FakeLLM("groq", ["لا يُستدعى"])
    hits = [{"text": f"سعر التصميم: {marker}", "source": "data/kb/narjs_services.md"}]
    r = await router.ask("كم سعر التصميم", kb=FakeKB(hits), fast=fast, deep=FakeLLM("deep", []))
    assert r.route == "handoff" and fast.calls == 0 and marker not in r.answer


async def test_no_hits_or_kb_down_handoff():
    r = await router.ask("سؤال", kb=Down(), fast=FakeLLM("groq", ["x"]), deep=FakeLLM("deep", []))
    assert r.route == "handoff"


def test_parse_verdict_fails_closed():
    assert parse_verdict("garbage") == (False, "unparseable review")
    assert parse_verdict(OK)[0] is True


def test_chunk_markdown_keeps_qa_together():
    md = "# عنوان\n\n### س1: سؤال؟\nج: جواب\nالمصدر: x\n\n### س2: ثاني؟\nج: يحدده محمد\n"
    chunks = rag.chunk_markdown(md, "kb.md")
    assert [c["title"] for c in chunks] == ["عنوان", "س1: سؤال؟", "س2: ثاني؟"]
    assert "ج: جواب" in chunks[1]["text"]


async def test_kb_ingest_and_retrieve_via_pgvector_store(tmp_path):
    """Same store the tenant RAG uses (pgvector on Postgres, cosine on SQLite)."""
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        (tmp_path / "a.md").write_text("### س: كم سعر رد؟\nج: 599", encoding="utf-8")
        async with maker() as session:
            kb = rag.KB(session)
            assert await kb.ingest(tmp_path) == 1
            hits = await kb.retrieve("سعر رد")
            assert hits and hits[0]["source"].endswith("a.md")
            row = (await session.execute(select(KnowledgeChunk))).scalars().first()
            assert row is not None and row.embedding and row.title.startswith(rag.COLLECTION_PREFIX)
    finally:
        await engine.dispose()


def test_endpoint(monkeypatch):
    from contextlib import asynccontextmanager

    from fastapi.testclient import TestClient

    from src.main import app

    @asynccontextmanager
    async def _session():
        yield None

    async def fake_ask(q, **_kwargs):
        return router.Result("جواب", "fast", ["s.md"], False)

    monkeypatch.setattr(router, "ask", fake_ask)
    # The route opens a DB session before the (patched) answer. Lifespan does
    # not run on a one-shot TestClient, so the test supplies the factory.
    monkeypatch.setattr(app.state, "session_factory", _session, raising=False)
    r = TestClient(app).post("/api/ai/ask", json={"question": "كم سعر رد"})
    assert r.status_code == 200
    assert r.json() == {"answer": "جواب", "route": "fast", "sources": ["s.md"], "reviewed": False}


def test_endpoint_rejects_oversized_question():
    from fastapi.testclient import TestClient

    from src.main import app

    r = TestClient(app).post("/api/ai/ask", json={"question": "س" * 2001})
    assert r.status_code == 422
