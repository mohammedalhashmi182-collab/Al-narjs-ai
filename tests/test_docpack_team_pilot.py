"""Internal paid-service candidate: actual DocPack bytes, team review, fail-closed QA."""
import hashlib
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from openpyxl import load_workbook

from src.automation.workflow_engine import WorkflowEngine
from src.core.state_manager import StateManager
from src.services.docgen.sample import load_sample_bytes
from src.services.docgen.schema import DocGenError
from src.services.docgen.team_pilot import prepare_docpack_team_preview, verify_pack_files


def agent(slug):
    return SimpleNamespace(
        slug=slug, category="general", default_parameters={},
        prompt_templates={"default": SimpleNamespace(template_text="Complete your task with evidence.")},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("review", ["Verdict: PASS", "Verdict: RETURN"])
async def test_docpack_real_file_is_released_to_preview_only_after_team_qa(monkeypatch, review):
    from src.services import agent_runtime

    registry = AsyncMock()
    registry.get_agent.side_effect = agent

    async def run(provider, selected_agent, **kwargs):
        return SimpleNamespace(
            content=review if selected_agent.slug == "quality_gate" else "Team task complete.",
            model="fixture", tokens_used=1, quality={"passed": True},
            structured_output=None,
        )

    monkeypatch.setattr(agent_runtime, "execute", run)
    engine = WorkflowEngine(registry, AsyncMock(), StateManager(), None)
    call = prepare_docpack_team_preview(
        engine,
        brief="حلّل ملف المبيعات مع أرقام مثبتة.",
        file_bytes=load_sample_bytes(),
        filename="sales.xlsx", formats=["xlsx"],
    )
    if "RETURN" in review:
        with pytest.raises(DocGenError, match="quality review failed"):
            await call
    else:
        result = await call
        assert result.quality_passed
        assert len(result.files) == 1
        file = result.pack.files[0]
        assert result.files[0].sha256 == hashlib.sha256(file.content).hexdigest()
        book = load_workbook(BytesIO(file.content))
        assert book.sheetnames
        assert result.workflow_id


def test_pack_structure_check_rejects_invalid_artifact_and_format():
    bad = SimpleNamespace(files=[SimpleNamespace(
        format="xlsx", filename="document.xlsx", content=b"not a spreadsheet"
    )])
    with pytest.raises(DocGenError, match="invalid office archive"):
        verify_pack_files(bad, ["xlsx"])
    with pytest.raises(DocGenError, match="file types"):
        verify_pack_files(bad, ["pdf"])


@pytest.mark.asyncio
async def test_empty_client_request_cannot_start_team_or_generate_files():
    engine = WorkflowEngine(AsyncMock(), AsyncMock(), StateManager(), None)
    with pytest.raises(DocGenError, match="missing client brief"):
        await prepare_docpack_team_preview(engine, brief="")
