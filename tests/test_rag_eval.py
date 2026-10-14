"""Fixed RAG eval (mocked: hash embeddings, no LLM) as a CI regression gate.

The >=90% correct-or-correct-handoff TARGET applies to the live eval (real
embeddings + LLM, scripts/run_rag_eval.py --mode live). The mocked pipeline
(verbatim-source replies, no model) is the no-key fallback; here it must never
answer wrongly or hallucinate, and must not regress below its floor.
"""
from __future__ import annotations

import json
import re

import pytest

from src.services.rag import evaluate, generate

MOCKED_FLOOR = 0.85  # mocked baseline on 2026-10-14: 0.86 (179/208), 0 wrong, 0 hallucinations


def test_eval_set_shape_and_labels():
    qs = evaluate.load_questions()
    assert len(qs) >= 200 and len({q["id"] for q in qs}) == len(qs)
    by = {}
    for q in qs:
        by.setdefault(q["business"], []).append(q)
        assert q["expect"] in ("answer", "handoff") and (q["facts"] or q["expect"] == "handoff")
    assert set(by) == {"clinic", "salon", "store", "restaurant"} and all(len(v) >= 50 for v in by.values())
    for biz in by:
        raw = (evaluate.ROOT / "kbs" / f"{biz}.md").read_text(encoding="utf-8")
        assert raw.startswith("# مثال تجريبي") and "خيالية" in raw  # clearly fictional
        assert "الياسمين" not in raw and "Yasmin" not in raw       # deleted sample clinic name
        kb = evaluate.load_kb(biz)
        for q in by[biz]:
            for f in q["facts"]:
                assert evaluate._norm(f) in evaluate._norm(kb), (q["id"], f)  # facts really are in the KB


async def test_mocked_eval_gate():
    rep = await evaluate.run("mocked")
    s = rep.summary()
    assert s["total"] >= 200
    assert s["wrong"] == 0, rep.failures
    assert s["hallucinations"] == 0
    assert s["correct_or_correct_handoff"] >= MOCKED_FLOOR, s


async def test_hallucinating_model_is_contained(monkeypatch):
    """A model that invents numbers on every answer must still yield 0 hallucinations."""
    async def liar(system, prompt):
        return "أكيد! السعر 999 ريال ونفتح 24 ساعة، والعرض اليوم خصم 50%."

    qs = [q for q in evaluate.load_questions() if q["business"] == "clinic"]
    from src.services.rag import embeddings

    monkeypatch.setattr(generate, "_llm_complete", liar)
    embeddings.set_embedder(embeddings.HashEmbedder())
    s = (await evaluate.run("custom", qs)).summary()  # "custom": keeps the installed model/embedder
    assert s["hallucinations"] == 0 and s["wrong"] == 0


def test_runner_lists_key_names_only(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-never-be-printed-123")
    assert evaluate.available_live_keys() == ["OPENAI_API_KEY"]
    assert "sk-should" not in json.dumps(evaluate.available_live_keys())
