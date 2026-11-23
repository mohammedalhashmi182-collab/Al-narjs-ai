"""Live team run: real agents only, no fake work when no model is configured."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from src.services import ceo_live


class FakeProvider:
    def __init__(self, text="ok"):
        self.text = text
        self.calls = []

    async def complete_with_fallback(self, chain, request):
        self.calls.append(request.system_prompt)
        return SimpleNamespace(content=self.text)


async def _collect(problem, provider, lang="ar"):
    return [event async for event in ceo_live.run_team(problem, provider=provider, lang=lang)]


def test_no_model_is_reported_as_unavailable_with_no_agent_work(monkeypatch):
    monkeypatch.setattr(ceo_live.ceo_advisor, "_has_cloud_model", lambda p: False)
    events = asyncio.run(_collect("ابي اعرف كيف أرد على عملاء واتساب بسرعة", FakeProvider()))
    assert events == [{"type": "unavailable"}]


def test_agent_selection_is_capped_and_uses_real_catalog_slugs():
    slugs = ceo_live.select_agents("متجري الإلكتروني يحتاج خدمة عملاء وتسويق ومبيعات وتقارير وإعلانات")
    assert len(slugs) <= ceo_live.MAX_AGENTS
    assert all(slug in ceo_live.catalog.EMPLOYEES for slug in slugs)
    assert len(slugs) == len(set(slugs))


def test_full_run_emits_agent_steps_then_final(monkeypatch):
    monkeypatch.setattr(ceo_live.ceo_advisor, "_has_cloud_model", lambda p: True)
    provider = FakeProvider("نقطة واحدة")
    events = asyncio.run(_collect("متجري الإلكتروني يحتاج خدمة عملاء على واتساب", provider))
    types = [e["type"] for e in events]
    assert types[0] == "team"
    assert types[-1] == "final"
    assert types.count("agent_start") == types.count("agent_done") >= 1
    assert events[-1]["text"] == "نقطة واحدة"
    assert len(provider.calls) == types.count("agent_done") + 1


def test_sse_line_is_valid_event_stream():
    line = ceo_live.sse_line({"type": "final", "text": "جواب"})
    assert line.startswith("data: ") and line.endswith("\n\n")
    assert json.loads(line[len("data: "):]) == {"type": "final", "text": "جواب"}


def test_one_free_team_run_per_visitor_per_day():
    from starlette.requests import Request
    from fastapi import HTTPException
    from src.utils import rate_limit

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/ceo/team-run",
        "query_string": b"",
        "headers": [],
        "client": ("198.51.100.77", 4321),
    }
    first = Request(scope)
    rate_limit.rate_limit_team_run(first)
    with pytest.raises(HTTPException) as blocked:
        rate_limit.rate_limit_team_run(Request(scope))
    assert blocked.value.status_code == 429
