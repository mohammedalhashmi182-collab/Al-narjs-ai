"""Agent knowledge packs: every agent has a valid pack, packs are wired into
the prompts, and the offline evals run with the mocked model."""

import json
import re
from pathlib import Path

import yaml

from src.services import agent_evals, agent_knowledge, catalog

ROOT = Path(__file__).resolve().parents[1]


def test_every_agent_has_a_valid_pack():
    yaml_slugs = {p.stem for p in (ROOT / "agents" / "base").glob("*.yaml")}
    assert set(catalog.EMPLOYEES) <= set(agent_knowledge.pack_slugs())
    assert yaml_slugs <= set(agent_knowledge.pack_slugs())
    reg = agent_knowledge.shared()["sources"]
    for slug in catalog.EMPLOYEES:
        pack = agent_knowledge.load_pack(slug)
        assert pack and pack["slug"] == slug
        assert pack["system_prompt"] and pack["guardrails"] and pack["playbooks"] and pack["few_shot"]
        assert len(pack["facts"]) >= 5, slug
        assert pack["sources"], slug
        for f in pack["facts"]:
            assert all(k in reg for k in f["sources"]), f["id"]


def test_sources_are_public_https_or_internal():
    for key, s in agent_knowledge.shared()["sources"].items():
        assert s["title"]
        assert s["url"] == "" or s["url"].startswith("https://"), key


def test_packs_hold_no_secrets_or_unapproved_offers():
    text = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "knowledge" / "agents").glob("*.json"))
    assert not re.search(r"(sk-|AIza|EAA[A-Za-z0-9]{10}|ghp_)[A-Za-z0-9]", text)
    assert "عرض التأسيس" not in text.replace("عرض التأسيس أُلغي", "")
    assert not re.search(r"(?<![\d,])499", text)  # old price (lesson 3)
    for price in ("599", "1,499", "3,499", "990", "1,990"):
        assert price in (ROOT / "knowledge" / "agents" / "orchestrator.json").read_text(encoding="utf-8")


def test_expert_block_references_pack_and_retrieves_relevant_facts():
    block = agent_knowledge.expert_block("finance_pricing", "متى لازم أسجل في ضريبة القيمة المضافة")
    assert agent_knowledge.MARKER in block and "finance_pricing" in block
    assert "375,000" in block
    assert agent_knowledge.expert_block("no_such_agent", "x") == ""
    assert agent_knowledge.load_pack("../etc") is None


def test_ceo_prompt_uses_orchestrator_pack():
    from types import SimpleNamespace

    from src.services import ceo_advisor

    system, _ = ceo_advisor._llm_prompt("كيف أرتب أولويات مشاريعي", SimpleNamespace(agents=["customer_service"]), "ar")
    assert agent_knowledge.MARKER in system
    assert "Refunds: none after activation" in system


async def test_run_context_injects_pack_for_every_agent(monkeypatch):
    from types import SimpleNamespace

    from src.services import agent_tools

    async def _no_search(*a, **k):
        return []

    monkeypatch.setattr(agent_tools.web_search, "search", _no_search)
    monkeypatch.setattr(agent_tools.store_connectors, "snapshots", _no_search)

    class _S:  # session stub: tool queries return nothing
        async def execute(self, *a, **k):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

    async def _empty(*a, **k):
        return []

    monkeypatch.setattr(agent_tools.knowledge_base, "search", _empty)
    monkeypatch.setattr(agent_tools.knowledge_base, "list_docs", _empty)
    project = SimpleNamespace(id=None, client_name="متجر")
    for slug in catalog.EMPLOYEES:
        ctx = await agent_tools.run_context(_S(), slug, project, {"q": "خطة"})
        assert f"{agent_knowledge.MARKER}: {slug}" in ctx, slug


def test_evals_cover_every_agent_and_run_mocked():
    data = agent_evals.load_evals()
    assert set(data["agents"]) == set(catalog.EMPLOYEES)
    for slug, items in data["agents"].items():
        assert len(items) >= 10, slug
        assert all(it["q"] and it["criteria"] for it in items)
    before, after = agent_evals.run(False), agent_evals.run(True)
    assert set(before) == set(after) == set(catalog.EMPLOYEES)
    for slug in before:
        assert after[slug] >= before[slug], slug
    assert sum(after.values()) / len(after) >= 75


def test_score_item_any_of_groups():
    assert agent_evals.score_item("VAT 15% ZATCA", [["15%"], ["ZATCA", "زكاة"], ["PDPL"]]) == 2 / 3
