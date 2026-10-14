"""Tenant Reply Agent writes the reply with the LLM, grounded in the KB snippet,
with a safe fallback. The LLM is always mocked (no network)."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models import ClientProject
from src.services import tenant_reply
from src.services.agent_tools import knowledge_base

FAQ = "ساعات العمل: نفتح يوميًا من الساعة 9 صباحًا حتى 11 مساءً. التوصيل داخل الرياض مجاني للطلبات فوق 200 ريال."


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
def llm(monkeypatch):
    box = {"reply": None, "calls": []}

    async def fake(system, prompt):
        box["calls"].append((system, prompt))
        return box["reply"]

    monkeypatch.setattr(tenant_reply, "_llm_complete", fake)
    return box


async def _project(s):
    p = ClientProject(client_name="متجر الورد", phone="0555000001", package="radd", status="active",
                      wa_phone_number_id="111")
    s.add(p)
    await s.flush()
    await knowledge_base.add_doc(s, "FAQ", FAQ, project_id=p.id)
    await s.commit()
    return p


async def _ask(s, p, q="متى ساعات العمل؟"):
    return await tenant_reply.handle_inbound(s, project=p, contact="966511111111", text=q)


async def test_reply_is_generated_by_llm_not_copied(maker, llm):
    llm["reply"] = "أهلًا! نفتح يوميًا من 9 صباحًا إلى 11 مساءً 🌿"
    async with maker() as s:
        p = await _project(s)
        d = await _ask(s, p)
    assert d.draft_text == llm["reply"] and FAQ not in d.draft_text
    assert d.meta["answer_source"] == "llm" and d.kind == "reply"
    system, prompt = llm["calls"][0]
    assert FAQ in prompt and "متى ساعات العمل؟" in prompt and "متجر الورد" in system


@pytest.mark.parametrize("bad", [
    "نفتح من 8 صباحًا والتوصيل مجاني فوق 150 ريال",   # numbers not in the snippet
    "اطلب من https://evil.example/x",                  # link not in the snippet
    "جرّب باقة «رد» من النرجس للذكاء",                    # pitch
    "x" * 1200,                                        # too long
])
async def test_ungrounded_llm_reply_falls_back_to_snippet(maker, llm, bad):
    llm["reply"] = bad
    async with maker() as s:
        p = await _project(s)
        d = await _ask(s, p)
    assert d.meta["answer_source"] == "kb_fallback" and "9 صباحًا" in d.draft_text and bad not in d.draft_text


async def test_llm_unavailable_falls_back_to_snippet(maker, llm):
    llm["reply"] = None
    async with maker() as s:
        p = await _project(s)
        d = await _ask(s, p)
    assert d.meta["answer_source"] == "kb_fallback" and "9 صباحًا" in d.draft_text


async def test_llm_no_answer_hands_off(maker, llm):
    llm["reply"] = "NO_ANSWER"
    async with maker() as s:
        p = await _project(s)
        d = await _ask(s, p, "هل عندكم ورد أزرق؟ ساعات العمل")
    assert d.kind == "handoff" and d.meta["handoff"] == "no_answer"


def test_grounding_accepts_arabic_digits():
    assert tenant_reply.grounded("نفتح الساعة ٩ صباحًا", [{"text": FAQ}])
    assert not tenant_reply.grounded("نفتح الساعة ٧ صباحًا", [{"text": FAQ}])
