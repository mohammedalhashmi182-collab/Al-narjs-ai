"""Regression tests: parallel specialists share only completed dependencies and QA gates release."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.automation.workflow_engine import WorkflowDefinition, WorkflowEngine, WorkflowStep
from src.core.state_manager import StateManager


def _agent(slug):
    return SimpleNamespace(
        slug=slug,
        category="general",
        default_parameters={},
        prompt_templates={"default": SimpleNamespace(template_text="Do the assigned work.")},
    )


def _workflow():
    return WorkflowDefinition(
        global_config={"slug": "ceo-team-proof"},
        steps=[
            WorkflowStep(id="research", agent_slug="market_analyst"),
            WorkflowStep(id="draft", agent_slug="content_writer"),
            WorkflowStep(id="review", agent_slug="quality_gate", depends_on=["research", "draft"]),
        ],
    )


@pytest.mark.asyncio
async def test_parallel_team_handoff_and_verified_quality_gate(monkeypatch):
    from src.services import agent_runtime

    registry = AsyncMock()
    registry.get_agent.side_effect = lambda slug: _agent(slug)
    started = set()
    both_started = asyncio.Event()
    seen = {}

    async def fake_execute(provider, agent, **kwargs):
        slug = agent.slug
        seen[slug] = kwargs
        if slug != "quality_gate":
            started.add(slug)
            if len(started) == 2:
                both_started.set()
            await asyncio.wait_for(both_started.wait(), 2)
            return SimpleNamespace(
                content=f"{slug}: completed", structured_output=None,
                tokens_used=1, model="fixture", quality={"passed": True}
            )
        handoff = kwargs["tool_context"]
        assert "market_analyst: completed" in handoff
        assert "content_writer: completed" in handoff
        return SimpleNamespace(
            content="Verdict: PASS\nAll requirements checked.", structured_output=None,
            tokens_used=1, model="fixture", quality={"passed": True}
        )

    monkeypatch.setattr(agent_runtime, "execute", fake_execute)
    engine = WorkflowEngine(registry, AsyncMock(), StateManager(), None, max_concurrent_steps=2)
    result = await engine.execute(_workflow(), {"client_request": "Create a professional client deliverable"})
    assert result.success, result.error
    assert result.steps_completed == 3
    assert both_started.is_set()
    assert seen["market_analyst"]["tool_context"] == ""
    assert seen["content_writer"]["tool_context"] == ""
    assert "Create a professional client deliverable" in seen["quality_gate"]["tool_context"]
    status = engine.get_workflow_status(result.workflow_id)
    assert status["steps"]["review"]["status"] == "completed"


@pytest.mark.asyncio
@pytest.mark.parametrize("verdict", ["Verdict: RETURN\nMissing sources.", "Unreviewed.", "Verdict: PASSING"])
async def test_quality_gate_does_not_release_failed_or_ambiguous_review(monkeypatch, verdict):
    from src.services import agent_runtime

    registry = AsyncMock()
    registry.get_agent.side_effect = lambda slug: _agent(slug)

    async def fake_execute(provider, agent, **kwargs):
        result = verdict if agent.slug == "quality_gate" else "draft complete"
        return SimpleNamespace(
            content=result, structured_output=None, tokens_used=1,
            model="fixture", quality={"passed": True}
        )

    monkeypatch.setattr(agent_runtime, "execute", fake_execute)
    engine = WorkflowEngine(registry, AsyncMock(), StateManager(), None)
    result = await engine.execute(_workflow(), {"client_request": "Draft"})
    assert not result.success
    assert result.steps_failed == 1
    assert "review" in (result.error or "")
    assert engine.get_workflow_status(result.workflow_id)["steps"]["review"]["status"] == "failed"
