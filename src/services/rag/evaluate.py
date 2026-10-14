"""Fixed RAG eval: 4 fictional sample businesses (clinic, salon, store,
restaurant), 200+ questions with Saudi-dialect / phrasing variants.

Each question goes through the REAL tenant pipeline
(``tenant_reply.handle_inbound``) with all four tenants in one database, so
tenant isolation is exercised on every question.

Outcomes per question
  correct          expected an answer, got one containing every expected fact
  correct_handoff  expected a handoff (not in the KB / wants a human), got one
  missed           expected an answer, got a (safe) handoff
  wrong            answered when it should hand off, or answered without the facts
Hallucination = an answer containing a number that is not in THAT tenant's KB
(or any other tenant's text). Targets: (correct + correct_handoff) / total >= 0.90,
wrong == 0, hallucination == 0.

Modes
  mocked  hash embeddings, no LLM (verbatim-source replies). Deterministic, CI.
  live    configured embedding provider + the app's LLM chain. Needs a key.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "evals" / "rag"
TARGET = 0.90
LIVE_KEYS = ("OPENAI_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY",
             "MOONSHOT_API_KEY")
NAMES = {"clinic": "عيادة أسنان تجريبية", "salon": "صالون تجريبي", "store": "متجر عطور تجريبي",
         "restaurant": "مطعم تجريبي"}
_NUM = re.compile(r"\d+(?:\.\d+)?")


def available_live_keys() -> list[str]:
    """Names (never values) of model keys present in the environment."""
    return [k for k in LIVE_KEYS if (os.getenv(k) or "").strip()]


def load_kb(business: str) -> str:
    text = (ROOT / "kbs" / f"{business}.md").read_text(encoding="utf-8")
    return "\n".join(line for line in text.splitlines() if not line.startswith("#")).strip()


def load_questions() -> list[dict]:
    return json.loads((ROOT / "questions.json").read_text(encoding="utf-8"))


@dataclass
class Report:
    mode: str
    total: int = 0
    counts: dict = field(default_factory=lambda: {"correct": 0, "correct_handoff": 0, "missed": 0, "wrong": 0})
    hallucinations: int = 0
    latencies_ms: list = field(default_factory=list)
    by_business: dict = field(default_factory=dict)
    failures: list = field(default_factory=list)

    def summary(self) -> dict:
        t = max(self.total, 1)
        ok = self.counts["correct"] + self.counts["correct_handoff"]
        exp_h = sum(b["expected_handoff"] for b in self.by_business.values()) or 1
        lat = sorted(self.latencies_ms) or [0]
        return {
            "mode": self.mode, "total": self.total, **self.counts,
            "accuracy": round(self.counts["correct"] / max(t - exp_h, 1), 4),
            "correct_handoff_rate": round(self.counts["correct_handoff"] / exp_h, 4),
            "correct_or_correct_handoff": round(ok / t, 4),
            "wrong_rate": round(self.counts["wrong"] / t, 4),
            "hallucinations": self.hallucinations,
            "latency_ms_p50": int(statistics.median(lat)),
            "latency_ms_p95": int(lat[min(len(lat) - 1, int(len(lat) * 0.95))]),
            "target_met": ok / t >= TARGET and self.counts["wrong"] == 0 and self.hallucinations == 0,
            "by_business": self.by_business,
        }


def _norm(s: str) -> str:
    from .arabic import normalize

    return normalize(s)


async def run(mode: str = "mocked", questions: list[dict] | None = None) -> Report:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from src.db.session import Base
    from src.models import ClientProject
    from src.services import tenant_reply
    from src.services.agent_tools import knowledge_base

    from . import embeddings, generate

    questions = questions or load_questions()
    saved_llm, saved_emb = generate._llm_complete, embeddings._override
    if mode == "mocked":
        async def _none(system, prompt):
            return None

        generate._llm_complete = _none
        embeddings.set_embedder(embeddings.HashEmbedder())
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    rep = Report(mode=mode)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as s:
            projects, kb_nums = {}, {}
            for i, biz in enumerate(sorted({q["business"] for q in questions})):
                p = ClientProject(client_name=NAMES.get(biz, biz), phone=f"05550009{i:02d}", package="tashgheel",
                                  status="active", wa_phone_number_id=f"eval-{biz}", reply_mode="review")
                s.add(p)
                await s.flush()
                kb = load_kb(biz)
                await knowledge_base.add_doc(s, "الأسئلة الشائعة", kb, project_id=p.id)
                projects[biz], kb_nums[biz] = p, set(_NUM.findall(_norm(kb)))
            for n, q in enumerate(questions):
                biz = q["business"]
                b = rep.by_business.setdefault(biz, {"total": 0, "expected_handoff": 0, "correct": 0,
                                                     "correct_handoff": 0, "missed": 0, "wrong": 0})
                t0 = time.perf_counter()
                d = await tenant_reply.handle_inbound(s, project=projects[biz], contact=f"9665{n:08d}", text=q["question"])
                rep.latencies_ms.append((time.perf_counter() - t0) * 1000)
                answered = d is not None and d.kind == "reply"
                text = _norm(d.draft_text or "") if answered else ""
                if answered and any(x not in kb_nums[biz] for x in _NUM.findall(text)):
                    rep.hallucinations += 1
                if q["expect"] == "handoff":
                    b["expected_handoff"] += 1
                    out = "wrong" if answered else "correct_handoff"
                elif not answered:
                    out = "missed"
                else:
                    out = "correct" if all(_norm(f) in text for f in q["facts"]) else "wrong"
                rep.counts[out] += 1
                b[out] += 1
                b["total"] += 1
                rep.total += 1
                if out in ("wrong", "missed"):
                    rep.failures.append({"id": q["id"], "q": q["question"], "outcome": out,
                                         "reply": (d.draft_text if d else None), "meta": (d.meta if d else None)})
            await s.rollback()
    finally:
        generate._llm_complete, embeddings._override = saved_llm, saved_emb
        await engine.dispose()
    return rep
