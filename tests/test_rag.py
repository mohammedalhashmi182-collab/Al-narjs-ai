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
    monkeypatch.setattr(embeddings, "_key", lambda n: "k" if n == "GEMINI_API_KEY" else None)
    monkeypatch.setenv("RAG_EMBED_PROVIDER", "auto")
    assert embeddings.get_embedder().name.startswith("gemini:")
    monkeypatch.setattr(embeddings, "_key", lambda n: "k")
    assert embeddings.get_embedder().name == "openai:text-embedding-3-small"
    monkeypatch.setenv("RAG_EMBED_PROVIDER", "gemini")
    assert embeddings.get_embedder().name.startswith("gemini:")
    monkeypatch.setattr(embeddings, "_key", lambda n: None)
    monkeypatch.setattr(embeddings, "_has_local", lambda: False)
    monkeypatch.setenv("RAG_EMBED_PROVIDER", "openai")  # no key → safe fallback
    assert embeddings.get_embedder().name == "hash:ngram-v1"


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


async def test_provider_failure_falls_back_to_hash():
    class Boom:
        name, dim = "openai:x", 3

        async def embed(self, texts, kind="doc"):
            raise RuntimeError("down")

    used, vecs = await embeddings.embed_safe(Boom(), ["سلام"])
    assert used.name == "hash:ngram-v1" and len(vecs[0]) == embeddings.HASH_DIM


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
