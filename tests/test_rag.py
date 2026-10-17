"""Real RAG for the tenant reply agent and the site assistant (mocked embeddings/LLM, no network)."""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models import ClientProject
from src.models.rag import KnowledgeChunk
from src.models.tenant import TenantContact
from src.services import rag, tenant_reply
from src.services.agent_tools import knowledge_base
from src.services.rag import arabic, embeddings, generate, store

# Fictional sample businesses (test data only).
CLINIC = ("ساعات العمل: من الأحد إلى الخميس من 9 صباحًا حتى 9 مساءً، والجمعة مغلق.\n\n"
          "تنظيف الأسنان: السعر 250 ريال ويشمل الفحص.\n\n"
          "الحجز: عبر الواتساب أو الاتصال، ويمكن إلغاء الموعد قبل 24 ساعة بدون رسوم.")
SALON = "قص الشعر: 80 ريال.\n\nصبغة الشعر: تبدأ من 300 ريال حسب الطول.\n\nالصالون للسيدات فقط."


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    async def _fake(*a, **k):
        return {"ok": True}

    from src.services import telegram_sender

    monkeypatch.setattr(telegram_sender, "send_owner_alert", _fake)


class LLM:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    async def __call__(self, system, prompt):
        self.calls.append((system, prompt))
        return self.reply(prompt) if callable(self.reply) else self.reply


async def _two(s):
    a = ClientProject(client_name="عيادة تجريبية", phone="0555000101", package="radd", status="active",
                      wa_phone_number_id="9001")
    b = ClientProject(client_name="صالون تجريبي", phone="0555000102", package="radd", status="active",
                      wa_phone_number_id="9002")
    s.add_all([a, b])
    await s.flush()
    await knowledge_base.add_doc(s, "الأسئلة الشائعة", CLINIC, project_id=a.id)
    await knowledge_base.add_doc(s, "الأسعار", SALON, project_id=b.id)
    await knowledge_base.add_doc(s, "Al-Narjis", "باقة ردّ بسعر 599 ريال شهريًا", project_id=None)
    return a, b


# --------------------------------------------------------------------------- normalization

@pytest.mark.parametrize("raw, want", [
    ("أحمد إبراهيم آمنة", "احمد ابراهيم امنه"),
    ("مستشفى", "مستشفي"),
    ("مَوْعِدٌ", "موعد"),
    ("مـــرحبا", "مرحبا"),
    ("٢٥٠ ريال", "250 ريال"),
    ("ههههههه", "هه"),
])
def test_normalize(raw, want):
    assert arabic.normalize(raw) == want


def test_dialect_variants_share_terms():
    assert arabic.terms("وش أوقات دوامكم؟") == ["دوام", "دوام"]
    assert "دوام" in arabic.terms("ما هي ساعات العمل")
    assert "سعر" in arabic.terms("بكم تنظيف الأسنان") and "سعر" in arabic.terms("كم سعر تنظيف الاسنان")
    assert arabic.terms("ابغى احجز") == arabic.terms("أريد الحجز") == ["حجز"]
    assert "موقع" in arabic.terms("وين مكانكم")


def test_chunks_keep_faq_entries_apart():
    parts = store.chunk_text(CLINIC)
    assert len(parts) == 3 and parts[1].startswith("تنظيف")


async def test_hash_embeddings_match_spelling_variants():
    e = embeddings.HashEmbedder()
    q, doc, other = await e.embed(["بكم تنظيف الاسنان؟", "تنظيف الأسنان: السعر 250 ريال", "الصالون للسيدات فقط"])
    assert embeddings.cosine(q, doc) > embeddings.cosine(q, other) + 0.2


# --------------------------------------------------------------------------- providers

def test_provider_selection_by_env(monkeypatch):
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("RAG_EMBED_MODEL", raising=False)
    monkeypatch.setattr(embeddings, "_has_local", lambda: False)
    monkeypatch.setattr(embeddings, "_key", lambda n: "k" if n == "GEMINI_API_KEY" else None)
    monkeypatch.setenv("RAG_EMBED_PROVIDER", "auto")
    assert embeddings.get_embedder().name == "gemini:gemini-embedding-001"
    # A present OpenAI key must not jump the queue. Production's key is invalid.
    monkeypatch.setattr(embeddings, "_key", lambda n: "k")
    assert embeddings.get_embedder().name == "gemini:gemini-embedding-001"
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    assert embeddings.get_embedder().name == "openai:text-embedding-3-small"
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    monkeypatch.setenv("RAG_EMBED_PROVIDER", "gemini")
    assert embeddings.get_embedder().name.startswith("gemini:")
    monkeypatch.setattr(embeddings, "_key", lambda n: "k" if n == "OPENAI_API_KEY" else None)
    monkeypatch.setenv("RAG_EMBED_PROVIDER", "auto")
    assert embeddings.get_embedder().name == "hash:ngram-v1"
    monkeypatch.setattr(embeddings, "_key", lambda n: None)
    monkeypatch.setenv("RAG_EMBED_PROVIDER", "openai")  # no key → hash, not a crash
    assert embeddings.get_embedder().name == "hash:ngram-v1"


def test_local_minilm_is_opt_in(monkeypatch):
    """Starter is 512 MB, so an installed sentence-transformers must not become the default."""
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("RAG_EMBED_MODEL", raising=False)
    monkeypatch.setattr(embeddings, "_has_local", lambda: True)
    monkeypatch.setattr(embeddings, "_key", lambda n: "k" if n == "GEMINI_API_KEY" else None)
    monkeypatch.setenv("RAG_EMBED_PROVIDER", "auto")
    assert embeddings.get_embedder().name == "gemini:gemini-embedding-001"
    assert all(not item.name.startswith("local:") for item in embeddings.candidate_embedders())
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    local = embeddings.get_embedder()
    assert local.name == "local:paraphrase-multilingual-MiniLM-L12-v2"
    assert local.dim == 384
    names = [item.name for item in embeddings.candidate_embedders()]
    assert names[0] == local.name and names[1].startswith("gemini:")
    monkeypatch.setattr(embeddings, "_has_local", lambda: False)
    embeddings._local_missing_logged = False
    assert embeddings.get_embedder().name.startswith("gemini:")


async def test_local_embed_uses_minilm_without_e5_prefixes(monkeypatch):
    seen = {}

    class Model:
        def get_sentence_embedding_dimension(self):
            return 384

        def encode(self, inputs, normalize_embeddings=False):
            seen["inputs"] = list(inputs)
            seen["normalized"] = normalize_embeddings
            return [[0.0] * 384]

    monkeypatch.setattr(embeddings, "_load_local_model", lambda name: seen.update(model=name) or Model())
    embeddings.LocalEmbedder._models.clear()
    embedder = embeddings.LocalEmbedder()
    vecs = await embedder.embed(["أهلاً"], kind="query")
    assert seen["model"] == embeddings.LOCAL_MODEL
    assert seen["inputs"] == ["اهلا"] and seen["normalized"] is True
    assert embedder.dim == 384 and len(vecs[0]) == 384


async def test_openai_and_gemini_payloads(monkeypatch):
    import httpx

    seen = []

    class R:
        def __init__(self, body):
            self.status_code, self._b = 200, body

        def json(self):
            return self._b

    async def post(self, url, headers=None, json=None):
        seen.append((url, json))
        if "openai" in url:
            return R({"data": [{"index": i, "embedding": [1.0, 0.0]} for i in range(len(json["input"]))]})
        return R({"embeddings": [{"values": [0.0, 2.0]} for _ in json["requests"]]})

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    v = await embeddings.OpenAIEmbedder("sk-test").embed(["أهلاً"])
    assert v == [[1.0, 0.0]] and seen[0][1]["input"] == ["اهلا"]  # normalized text is embedded
    v = await embeddings.GeminiEmbedder("g-test").embed(["سؤال"], kind="query")
    assert v == [[0.0, 1.0]] and seen[1][1]["requests"][0]["taskType"] == "RETRIEVAL_QUERY"


async def test_provider_failure_tries_the_next_real_provider(monkeypatch):
    class Boom:
        name, dim = "openai:text-embedding-3-small", 3

        async def embed(self, texts, kind="doc"):
            raise RuntimeError("invalid_api_key")

    class Ok(embeddings.GeminiEmbedder):
        def __init__(self):
            super().__init__("g", "gemini-embedding-001", 2)

        async def embed(self, texts, kind="doc"):
            return [[1.0, 0.0]]

    monkeypatch.setattr(embeddings, "candidate_embedders", lambda: [Ok()])
    used, vecs = await embeddings.embed_safe(Boom(), ["سلام"])
    assert used.name == "gemini:gemini-embedding-001" and vecs == [[1.0, 0.0]]


async def test_failed_providers_do_not_answer_with_hash(monkeypatch, caplog):
    class Boom:
        name, dim = "openai:text-embedding-3-small", 3

        async def embed(self, texts, kind="doc"):
            raise RuntimeError("invalid_api_key")

    monkeypatch.setattr(embeddings, "candidate_embedders", lambda: [])
    embeddings._hash_fallback_logged = False
    with caplog.at_level("ERROR", logger="src.services.rag.embeddings"):
        with pytest.raises(embeddings.EmbeddingUnavailable):
            await embeddings.embed_safe(Boom(), ["سلام"])
        with pytest.raises(embeddings.EmbeddingUnavailable):
            await embeddings.embed_safe(Boom(), ["سؤال سري"])
    errors = [rec.message for rec in caplog.records if rec.levelname == "ERROR"]
    assert len(errors) == 1
    assert "hash fallback will not be used to answer" in errors[0]
    assert "RuntimeError" in errors[0]
    assert "سؤال سري" not in caplog.text


# --------------------------------------------------------------------------- index + isolation

async def test_add_doc_indexes_and_delete_removes(maker):
    async with maker() as s:
        a, _ = await _two(s)
        assert await store.chunk_count(s, a.id) == 3
        doc = (await knowledge_base.list_docs(s, a.id))[0]
        assert await knowledge_base.delete_doc(s, doc.id, a.id)
        assert await store.chunk_count(s, a.id) == 0


async def test_edited_doc_is_reindexed(maker):
    async with maker() as s:
        a, _ = await _two(s)
        doc = (await knowledge_base.list_docs(s, a.id))[0]
        doc.content = "مواقف السيارات: متوفرة مجانًا أمام العيادة."
        await s.commit()
        hits = await rag.retrieve(s, "فيه مواقف سيارات؟", project_id=a.id)
        assert hits and "مواقف" in hits[0]["text"]
        texts = (await s.execute(select(KnowledgeChunk.text).where(KnowledgeChunk.project_id == a.id))).scalars().all()
        assert not any("تنظيف" in t for t in texts)


async def test_retrieval_is_strictly_per_tenant(maker):
    async with maker() as s:
        a, b = await _two(s)
        for q in ("كم سعر قص الشعر؟", "الصالون للسيدات؟", "بكم باقة رد؟"):
            for h in await rag.retrieve(s, q, project_id=a.id, k=10):
                assert "الشعر" not in h["text"] and "599" not in h["text"]
        for h in await rag.retrieve(s, "بكم تنظيف الاسنان", project_id=b.id, k=10):
            assert "الأسنان" not in h["text"]
        owner = await rag.retrieve(s, "بكم تنظيف الاسنان", project_id=None, k=10)
        assert all("الأسنان" not in h["text"] and "الشعر" not in h["text"] for h in owner)


async def test_dialect_question_retrieves_right_chunk(maker):
    async with maker() as s:
        a, _ = await _two(s)
        hits = await rag.retrieve(s, "وش أوقات دوامكم؟", project_id=a.id)
        assert "ساعات العمل" in hits[0]["text"] and hits[0]["score"] >= rag.min_confidence()
        hits = await rag.retrieve(s, "ابغى ألغي موعدي", project_id=a.id)
        assert "إلغاء" in hits[0]["text"]


# --------------------------------------------------------------------------- generation

HITS = [{"title": "FAQ", "text": "تنظيف الأسنان: السعر 250 ريال ويشمل الفحص.", "score": 0.8}]


async def test_llm_grounded_reply_is_used(monkeypatch):
    llm = LLM("هلا والله، تنظيف الأسنان سعره 250 ريال ويشمل الفحص.")
    monkeypatch.setattr(generate, "_llm_complete", llm)
    a = await generate.answer("بكم التنظيف؟", HITS, name="عيادة تجريبية")
    assert a.source == "llm" and "250" in a.text
    system, prompt = llm.calls[0]
    assert "اللهجة السعودية" in system and "[1]" in prompt and "250" in prompt


@pytest.mark.parametrize("bad", [
    "تنظيف الأسنان بـ 199 ريال بس!",               # invented number
    "احجز من https://evil.example.com",           # invented link
    "عندنا عرض خاص وخصم على تبييض الأسنان والتقويم",  # unsupported claims
])
async def test_ungrounded_llm_reply_falls_back_to_source(monkeypatch, bad):
    monkeypatch.setattr(generate, "_llm_complete", LLM(bad))
    a = await generate.answer("بكم التنظيف؟", HITS)
    assert a.source == "extractive" and "250" in a.text and bad not in a.text


async def test_no_answer_and_low_confidence_hand_off(monkeypatch):
    monkeypatch.setattr(generate, "_llm_complete", LLM("NO_ANSWER"))
    assert (await generate.answer("عندكم تقويم؟", HITS)).handoff == "no_answer"
    low = [{**HITS[0], "score": 0.1}]
    llm = LLM("x")
    monkeypatch.setattr(generate, "_llm_complete", llm)
    a = await generate.answer("سؤال بعيد", low)
    assert a.handoff == "low_confidence" and a.text is None and not llm.calls


# --------------------------------------------------------------------------- tenant agent end to end

async def test_tenant_unknown_question_goes_to_human_queue(maker, monkeypatch):
    llm = LLM("لازم ما يوصل")
    monkeypatch.setattr(generate, "_llm_complete", llm)
    async with maker() as s:
        a, _ = await _two(s)
        d = await tenant_reply.handle_inbound(s, project=a, contact="966500000001", text="هل تبيعون جوالات آيفون؟")
        assert d.kind == "handoff" and d.meta["handoff"] == "no_answer" and not llm.calls
        c = (await s.execute(select(TenantContact).where(TenantContact.project_id == a.id))).scalar_one()
        assert c.handoff_at is not None


async def test_tenant_answer_written_by_llm_from_own_kb(maker, monkeypatch):
    llm = LLM("أبشر، نفتح من الأحد إلى الخميس من 9 صباحًا حتى 9 مساءً، والجمعة مغلق.")
    monkeypatch.setattr(generate, "_llm_complete", llm)
    async with maker() as s:
        a, _ = await _two(s)
        d = await tenant_reply.handle_inbound(s, project=a, contact="966500000002", text="وش أوقات دوامكم؟")
        assert d.kind == "reply" and d.meta["answer_source"] == "llm" and d.draft_text == llm.reply
        assert "الشعر" not in llm.calls[0][1] and "599" not in llm.calls[0][1]  # only this tenant's sources


async def _over_limit(s, project):
    from src.services import usage

    row = await usage.current_usage(s, project)
    row.conversations = int(row.limit_conversations) + 5
    await s.flush()


async def test_over_usage_limit_skips_paid_ai_calls(maker, monkeypatch):
    llm = LLM("رد من النموذج")
    monkeypatch.setattr(generate, "_llm_complete", llm)
    called = []

    class Paid(embeddings.HashEmbedder):
        name = "openai:test"

        async def embed(self, texts, kind="doc"):
            called.append(texts)
            return await super().embed(texts, kind=kind)

    async with maker() as s:
        a, _ = await _two(s)
        embeddings.set_embedder(Paid())
        await _over_limit(s, a)
        called.clear()
        d = await tenant_reply.handle_inbound(s, project=a, contact="966500000003", text="بكم تنظيف الأسنان؟")
        assert d.kind == "reply" and d.meta["usage_limit"] and d.meta["answer_source"] == "extractive"
        assert "250" in d.draft_text and not llm.calls and not called


async def test_over_usage_limit_handoff_mode(maker, monkeypatch):
    monkeypatch.setenv("RAG_OVER_LIMIT", "handoff")
    async with maker() as s:
        a, _ = await _two(s)
        await _over_limit(s, a)
        d = await tenant_reply.handle_inbound(s, project=a, contact="966500000004", text="بكم تنظيف الأسنان؟")
        assert d.kind == "handoff" and d.meta["handoff"] == "usage_limit"


async def test_llm_pitch_is_blocked(maker, monkeypatch):
    monkeypatch.setattr(generate, "_llm_complete", LLM("قص الشعر 80 ريال، وجرب النرجس للذكاء الاصطناعي"))
    async with maker() as s:
        _, b = await _two(s)
        d = await tenant_reply.handle_inbound(s, project=b, contact="966500000005", text="بكم قص الشعر؟")
        assert "النرجس" not in d.draft_text and "80" in d.draft_text


async def test_query_embedding_is_masked(monkeypatch):
    """The string sent to the embedding provider has the phone replaced."""
    from src.services.rag import site_kb

    seen = []

    async def _embed(embedder, texts, *, kind="doc"):
        seen.append((kind, list(texts)))
        dim = getattr(embedder, "dim", 8)
        return embedder, [[0.0] * dim for _ in texts]

    monkeypatch.setattr(embeddings, "embed_safe", _embed)

    async def _noop(*_a, **_k):
        return None

    async def _not_pg(_session):
        return False

    monkeypatch.setattr(store, "ensure_indexed", _noop)
    monkeypatch.setattr(store, "pgvector_ready", _not_pg)

    class _Result:
        def all(self):
            return []

    class _Session:
        async def execute(self, *_a, **_k):
            return _Result()

    phone = "0551234567"
    hits = await store.retrieve(_Session(), f"جوالي {phone}", project_id=None, k=1)
    assert hits == []
    query_calls = [texts for kind, texts in seen if kind == "query"]
    assert query_calls and phone not in query_calls[0][0] and "[PHONE_1]" in query_calls[0][0]

    seen.clear()
    await site_kb.retrieve(f"اتصل {phone}")
    query_calls = [texts for kind, texts in seen if kind == "query"]
    assert query_calls
    assert all(phone not in text for texts in query_calls for text in texts)
    assert any("[PHONE_1]" in text for texts in query_calls for text in texts)


def test_vector_column_rebuild_only_when_the_width_is_fixed():
    assert store._vector_type_needs_rebuild("vector(1536)", 768) is True
    assert store._vector_type_needs_rebuild("vector(768)", 768) is False
    assert store._vector_type_needs_rebuild("vector", 768) is False


async def test_index_path_never_drops_the_vector_column(caplog):
    class Bind:
        class dialect:
            name = "postgresql"
        url = "postgresql://test"

    class Result:
        def scalar(self):
            return "vector(1536)"

    class Session:
        def __init__(self):
            self.sql: list[str] = []

        def get_bind(self):
            return Bind()

        async def execute(self, statement, params=None):
            self.sql.append(str(statement))
            return Result()

    session = Session()
    store._vector_dim_state.clear()
    store._vector_dim_warned.clear()
    with caplog.at_level("WARNING", logger="src.services.rag.store"):
        assert await store.ensure_vector_dim(session, 768) is False
        assert await store.ensure_vector_dim(session, 768) is False
    assert not any("DROP COLUMN" in sql or "ADD COLUMN" in sql for sql in session.sql)
    assert len(session.sql) == 1
    warnings = [rec.message for rec in caplog.records if rec.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "rebuild_embedding_vec.py" in warnings[0]
    assert "DROP COLUMN" in warnings[0]


async def test_vector_column_rebuild_is_an_explicit_admin_call():
    class Bind:
        class dialect:
            name = "postgresql"
        url = "postgresql://admin"

    class Session:
        def __init__(self):
            self.sql: list[str] = []

        def get_bind(self):
            return Bind()

        async def execute(self, statement, params=None):
            self.sql.append(str(statement))
            return None

    session = Session()
    store._vector_dim_state["postgresql://admin"] = "blocked:vector(1536)"
    await store.rebuild_embedding_vec_column(session)
    assert any("DROP COLUMN embedding_vec" in sql for sql in session.sql)
    assert any("ADD COLUMN embedding_vec vector" in sql for sql in session.sql)
    assert "postgresql://admin" not in store._vector_dim_state


async def test_dimension_change_reindexes_the_doc(maker):
    from src.models.agent_tools import KnowledgeDoc

    class Width:
        def __init__(self, dim):
            self.name = "gemini:gemini-embedding-001"
            self.dim = dim
            self.calls = 0

        async def embed(self, texts, kind="doc"):
            self.calls += 1
            return [[float(self.dim)] * self.dim for _ in texts]

    async with maker() as session:
        doc = KnowledgeDoc(
            project_id=None, title="kb:t", source="text",
            content="سعر باقة رد 599 ريال شهريا للرد على العملاء.",
        )
        session.add(doc)
        await session.flush()
        await store.index_doc(session, doc, Width(4))
        await session.commit()
        narrow = Width(8)
        await store.ensure_indexed(session, None, narrow)
        dims = (await session.execute(
            select(KnowledgeChunk.dim).where(KnowledgeChunk.doc_id == doc.id)
        )).scalars().all()
        assert set(dims) == {8} and narrow.calls >= 1


async def test_provider_change_reindexes_and_stores_the_new_model(maker):
    from src.models.agent_tools import KnowledgeDoc

    class Named:
        def __init__(self, name, dim):
            self.name = name
            self.dim = dim
            self.calls = 0

        async def embed(self, texts, kind="doc"):
            self.calls += 1
            return [[1.0] * self.dim for _ in texts]

    async with maker() as session:
        doc = KnowledgeDoc(
            project_id=None, title="kb:t", source="text",
            content="سعر باقة رد 599 ريال شهريا للرد على العملاء.",
        )
        session.add(doc)
        await session.flush()
        await store.index_doc(session, doc, Named("gemini:gemini-embedding-001", 4))
        await session.commit()
        local = Named("local:paraphrase-multilingual-MiniLM-L12-v2", 384)
        await store.ensure_indexed(session, None, local)
        rows = (await session.execute(
            select(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc.id)
        )).scalars().all()
        assert {row.model for row in rows} == {local.name}
        assert {row.dim for row in rows} == {384}
        assert local.calls >= 1


async def test_openai_tenant_docs_reindex_in_the_background(maker):
    """A customer retrieve must not rewrite OpenAI 1536 chunks. The background job does."""
    from src.models.agent_tools import KnowledgeDoc

    class Next:
        name = "gemini:gemini-embedding-001"
        dim = 8

        async def embed(self, texts, kind="doc"):
            return [[1.0] * self.dim for _ in texts]

    async with maker() as session:
        project, _other = await _two(session)
        rows = (await session.execute(
            select(KnowledgeChunk).where(KnowledgeChunk.project_id == project.id)
        )).scalars().all()
        assert rows
        for row in rows:
            row.model = "openai:text-embedding-3-small"
            row.dim = 1536
        owner = (await session.execute(
            select(KnowledgeChunk).where(KnowledgeChunk.project_id.is_(None))
        )).scalars().first()
        assert owner is not None
        owner.model = "openai:text-embedding-3-small"
        owner.dim = 1536
        await session.commit()

        await store.retrieve(
            session, "تنظيف الاسنان", project_id=project.id, k=3, embedder=Next(),
        )
        still = (await session.execute(
            select(KnowledgeChunk.model).where(KnowledgeChunk.project_id == project.id)
        )).scalars().all()
        assert set(still) == {"openai:text-embedding-3-small"}

        n = await store.reindex_openai_tenant_docs(session, Next())
        await session.commit()
        assert n >= 1
        fresh = (await session.execute(
            select(KnowledgeChunk.model, KnowledgeChunk.dim).where(KnowledgeChunk.doc_id.in_(
                select(KnowledgeDoc.id).where(KnowledgeDoc.project_id == project.id)
            ))
        )).all()
        assert fresh and {model for model, _dim in fresh} == {Next.name}
        assert {dim for _model, dim in fresh} == {8}
        owner_model = (await session.execute(
            select(KnowledgeChunk.model).where(KnowledgeChunk.project_id.is_(None))
        )).scalars().first()
        assert owner_model == "openai:text-embedding-3-small"


async def test_unindexed_tenant_doc_still_indexes_on_retrieve(maker):
    """A doc with no vectors is still filled on the question. OpenAI 1536 is the exception."""
    from src.models.agent_tools import KnowledgeDoc

    class Next:
        name = "hash:ngram-v1"
        dim = 8

        async def embed(self, texts, kind="doc"):
            return [[1.0] * self.dim for _ in texts]

    async with maker() as session:
        project = ClientProject(
            client_name="عيادة جديدة", phone="0555000199", package="radd", status="active",
        )
        session.add(project)
        await session.flush()
        session.add(KnowledgeDoc(
            project_id=project.id, title="دوام", source="text",
            content="الدوام من الأحد إلى الخميس ومن الساعة التاسعة صباحًا.",
        ))
        await session.commit()
        hits = await store.retrieve(session, "متى الدوام", project_id=project.id, k=3, embedder=Next())
        assert hits and "الأحد" in hits[0]["text"]
