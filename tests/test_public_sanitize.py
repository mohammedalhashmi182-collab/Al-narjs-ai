"""Public answers never show a repository path, on every customer-facing path.

Covers /api/consult, the extractive fallback, tenant_reply._rag_reply, chunking,
exact link matching, «المصدر:» lines that still have real words, the session-close
timeout, and bare «Source:» / markdown-link leftovers.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from src.ai import rag, router
from src.ai.sanitize import sanitize_public_text
from src.services.rag import generate


class FakeLLM:
    def __init__(self, name, replies):
        self.name = name
        self.replies = list(replies)
        self.calls = 0
        self.seen = ""

    async def chat(self, system, user, timeout=3.0):
        self.calls += 1
        self.system = system
        self.seen = user
        return self.replies.pop(0)


class FakeKB:
    def __init__(self, hits):
        self.hits = hits

    def retrieve(self, q, k=5):
        return self.hits[:k]


def test_source_line_keeps_words_and_the_full_url():
    leaked = (
        "المصدر: `src/services/catalog.py`، السعر 599 ريال، https://karmaai.online/docs/terms.pdf"
    )
    cleaned = sanitize_public_text(leaked)
    assert "src/" not in cleaned and "catalog.py" not in cleaned
    assert "599" in cleaned
    assert cleaned.count("https://karmaai.online/docs/terms.pdf") == 1
    assert "https://karmaai.online/." not in cleaned
    assert cleaned != ""
    assert sanitize_public_text(cleaned) == cleaned


def test_bare_source_label_and_internal_markdown_link_are_removed():
    cleaned = sanitize_public_text(
        "Answer. Source: src/services/catalog.py\n"
        "اقرأ [الملف](src/services/catalog.py) و [التسعير](https://karmaai.online/pricing)"
    )
    assert "Source" not in cleaned
    assert "[الملف]" not in cleaned and "src/" not in cleaned
    assert "[التسعير](https://karmaai.online/pricing)" in cleaned
    assert sanitize_public_text(cleaned) == cleaned


def test_non_path_citation_is_kept():
    cleaned = sanitize_public_text("يومياً. (المصدر: س1 – خدمات النرجس)")
    assert cleaned == "يومياً. (المصدر: س1 – خدمات النرجس)"


def test_public_kb_and_chunks_drop_repo_paths():
    raw = Path("data/kb/narjs_services.md").read_text(encoding="utf-8")
    assert "src/" not in raw and "docs/" not in raw
    chunks = rag.chunk_markdown(raw, "data/kb/narjs_services.md")
    blob = "\n".join(c["text"] for c in chunks)
    assert "src/" not in blob and "`docs/" not in blob
    assert "https://karmaai.online/pricing" in blob
    assert "https://karmaai.online/refund-policy" in blob
    assert "وصف الخدمة في الموقع" in blob
    assert "790" in blob and "1,490" in blob and "2,990" in blob
    injected = rag.chunk_markdown(
        "### س: سؤال؟\nج: السعر 599.\nالمصدر: `src/services/catalog.py`، https://karmaai.online/docs/terms.pdf\n",
        "kb.md",
    )
    text = injected[0]["text"]
    assert "src/" not in text
    assert "https://karmaai.online/docs/terms.pdf" in text
    assert "599" in text


def test_link_check_is_exact():
    hits = [{"text": "الشروط في https://karmaai.online/docs/terms.pdf", "title": "س"}]
    assert generate.grounded("راجع https://karmaai.online/docs/terms.pdf", hits)
    assert not generate.grounded("راجع https://karmaai.online", hits)
    assert not generate.grounded("راجع https://karmaai.online/docs", hits)
    assert not generate.grounded("راجع https://karmaai.online/docs/terms.pdf.evil", hits)


def test_extractive_fallback_strips_paths_and_keeps_the_url():
    hits = [{
        "text": "الدعم 24 ساعة.\nالمصدر: `src/services/policies.py`، https://karmaai.online/docs/terms.pdf",
        "title": "س",
        "score": 0.9,
    }]
    text = generate.extractive(hits)
    assert "src/" not in text and "policies.py" not in text
    assert "https://karmaai.online/docs/terms.pdf" in text
    assert "24 ساعة" in text


async def test_rag_reply_strips_paths_the_model_copied(monkeypatch):
    from src.models import ClientProject
    from src.services import tenant_reply

    class _Ans:
        text = "التفاصيل في src/services/catalog.py وشوف https://example.com/docs/terms.pdf"
        source = "llm"
        sources = ["t"]
        confidence = 0.8
        handoff = None

    async def _limit(*_a, **_k):
        return False

    async def _retrieve(*_a, **_k):
        return []

    async def _answer(*_a, **_k):
        return _Ans()

    monkeypatch.setattr(tenant_reply, "over_ai_limit", _limit)
    import src.services.rag as rag_mod

    monkeypatch.setattr(rag_mod, "retrieve", _retrieve)
    monkeypatch.setattr(rag_mod, "answer", _answer)
    project = ClientProject(client_name="تجريبي", phone="0550000000", package="radd", status="active")
    body, reason = await tenant_reply._rag_reply(None, project, "سؤال", {})
    assert reason is None
    assert body and "src/" not in body and "catalog.py" not in body
    assert "https://example.com/docs/terms.pdf" in body
    assert "التفاصيل" in body


async def test_path_on_a_source_line_does_not_handoff_empty():
    chunk = (
        "ج: السعر 599 ريال.\n"
        "المصدر: `src/services/catalog.py`، والتفاصيل https://karmaai.online/docs/terms.pdf"
    )
    leaked = "السعر 599 ريال. المصدر: `src/services/catalog.py`، والتفاصيل https://karmaai.online/docs/terms.pdf"
    fast = FakeLLM("groq", [leaked])
    result = await router.ask(
        "كم السعر",
        kb=FakeKB([{"text": chunk, "source": "data/kb/narjs_services.md", "score": 0.9}]),
        fast=fast,
        deep=FakeLLM("deep", []),
    )
    assert result.route == "fast"
    assert router.last_handoff_reason() != "stripped_empty"
    assert "599" in result.answer
    assert "والتفاصيل" in result.answer
    assert "https://karmaai.online/docs/terms.pdf" in result.answer
    assert "src/" not in result.answer and "catalog.py" not in result.answer
    assert "src/" not in fast.seen
    assert "https://karmaai.online/docs/terms.pdf" in fast.seen


async def test_prefix_of_a_public_url_is_not_grounded():
    chunk = "الشروط منشورة على https://karmaai.online/docs/terms.pdf"
    fast = FakeLLM("groq", ["راجع https://karmaai.online"])
    result = await router.ask(
        "وين الشروط",
        kb=FakeKB([{"text": chunk, "source": "data/kb/narjs_services.md", "score": 0.9}]),
        fast=fast,
        deep=FakeLLM("deep", []),
    )
    assert result.route == "handoff"
    assert router.last_handoff_reason() == "ungrounded"
    assert "https://" not in result.answer

    fast_ok = FakeLLM("groq", ["راجع https://karmaai.online/docs/terms.pdf"])
    ok = await router.ask(
        "وين الشروط",
        kb=FakeKB([{"text": chunk, "source": "data/kb/narjs_services.md", "score": 0.9}]),
        fast=fast_ok,
        deep=FakeLLM("deep", []),
    )
    assert ok.route == "fast"
    assert ok.answer == "راجع https://karmaai.online/docs/terms.pdf"


async def test_session_close_timeout_finishes_in_background(monkeypatch, caplog):
    from src.interfaces import ai_routes

    monkeypatch.setattr(ai_routes, "_SESSION_CLOSE_TIMEOUT_S", 0.05)
    before = ai_routes._session_close_timeouts
    state = {"cancelled": False, "finished": False, "invalidated": 0}

    class _CM:
        async def __aexit__(self, *_args):
            try:
                await asyncio.sleep(0.35)
            except asyncio.CancelledError:
                state["cancelled"] = True
                raise
            state["finished"] = True

    class _Session:
        async def invalidate(self):
            state["invalidated"] += 1

    caplog.set_level(logging.WARNING)
    await ai_routes._close_session(_CM(), _Session())
    assert state["cancelled"] is False
    assert state["finished"] is False
    assert ai_routes._session_close_timeouts == before + 1
    assert f"count={before + 1}" in caplog.text
    await asyncio.sleep(0)
    assert state["invalidated"] == 1
    await asyncio.sleep(0.45)
    assert state["finished"] is True
    assert state["cancelled"] is False


def test_consult_strips_paths_and_keeps_the_exact_url(monkeypatch):
    from fastapi.testclient import TestClient

    from src.main import app
    from src.utils import rate_limit

    for lim in vars(rate_limit).values():
        if hasattr(lim, "_hits"):
            lim._hits.clear()

    async def _hits(_history):
        return [{
            "title": "kb:data/kb/narjs_services.md",
            "text": "ج: الشروط على الرابط.\nالمصدر: `src/services/catalog.py`، https://karmaai.online/docs/terms.pdf",
            "score": 0.9,
        }]

    class _Resp:
        def __init__(self, content):
            self.content = content

    class _Model:
        def __init__(self):
            self.requests = []

        async def complete_with_fallback(self, _chain, request):
            self.requests.append(request)
            return _Resp(
                "راجع https://karmaai.online/docs/terms.pdf المصدر: `src/services/catalog.py`"
            )

    model = _Model()
    with TestClient(app) as client:
        monkeypatch.setattr(app.state, "model_provider", model)
        monkeypatch.setattr("src.main._consult_sources", _hits)
        response = client.post("/api/consult", json={"messages": [{"role": "user", "content": "وين الشروط؟"}]})
    body = response.json()
    assert response.status_code == 200
    assert body.get("handoff") is None
    assert "src/" not in body["reply"] and "catalog.py" not in body["reply"]
    assert "https://karmaai.online/docs/terms.pdf" in body["reply"]
    prompt = model.requests[0].system_prompt
    assert "src/" not in prompt and "data/kb/" not in prompt
    assert "https://karmaai.online/docs/terms.pdf" in prompt
