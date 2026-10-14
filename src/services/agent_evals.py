"""Offline eval harness for the specialist agents.

Metric: *grounding coverage* — for each realistic Saudi-context task in
``evals/agent_evals.json`` we assemble exactly what the model would receive
(agent prompt + Saudi context [+ knowledge pack]) and check which grading
criteria (any-of keyword groups) are present. With the mocked model the
"answer" is the grounding itself, so this measures whether the agent has the
knowledge available, NOT the final answer quality of a live model.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

EVAL_PATH = Path(__file__).resolve().parents[2] / "evals" / "agent_evals.json"
AGENTS_DIR = Path(__file__).resolve().parents[2] / "agents" / "base"


def load_evals() -> dict:
    return json.loads(EVAL_PATH.read_text(encoding="utf-8"))


def _norm(s: str) -> str:
    s = (s or "").lower().replace("\u0640", "")
    return re.sub(r"[\u064B-\u0652]", "", s)


def base_prompt(slug: str) -> str:
    import yaml

    try:
        data = yaml.safe_load((AGENTS_DIR / f"{slug}.yaml").read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return ""
    prompts = data.get("prompts") or {}
    tmpl = prompts.get("default") if isinstance(prompts, dict) else None
    if isinstance(tmpl, dict):
        tmpl = tmpl.get("template")
    return str(tmpl or data.get("prompt") or "")


def assemble(slug: str, question: str, with_pack: bool) -> str:
    from src.services import agent_brief, agent_knowledge

    ctx = base_prompt(slug) + "\n\n" + agent_brief.SAUDI_CONTEXT + "\n\nUser: " + question
    if with_pack:
        ctx += agent_knowledge.expert_block(slug, question)
    return ctx


def mock_model(context: str) -> str:
    """Deterministic stand-in for the LLM: it can only use what it was given."""
    return context


def score_item(answer: str, criteria: list[list[str]]) -> float:
    a = _norm(answer)
    hit = sum(1 for group in criteria if any(_norm(w) in a for w in group))
    return hit / len(criteria) if criteria else 0.0


def run(with_pack: bool, model=mock_model) -> dict[str, float]:
    out = {}
    for slug, items in load_evals()["agents"].items():
        scores = [score_item(model(assemble(slug, it["q"], with_pack)), it["criteria"]) for it in items]
        out[slug] = round(100 * sum(scores) / len(scores), 1)
    return out
