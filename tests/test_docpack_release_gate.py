"""DocPack release gating: no customer publication without independent QA.

These use local model stubs and synthetic files; they do not prove real
provider sandbox readiness, invoice settlement or durable artifact delivery.
"""
import json
from dataclasses import replace
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.agent_tools import docpack_tool
from src.services.docgen.pipeline import build_docpack
from src.services.docgen.release_gate import independent_review, require_release
from src.services.docgen.schema import DocGenError
from src.services.docgen.sample import load_sample_bytes


@pytest.fixture
async def sample_pack():
    return await build_docpack(
        brief="حلل المبيعات باستخدام أرقام الملف فقط.",
        file_bytes=load_sample_bytes(),
        filename="sales.xlsx",
        agent_key="data_analyst",
        agent_name_ar="محلل البيانات",
        agent_name_en="Data Analyst",
        formats=["xlsx"],
        model_provider=None,
        client_name="Test Customer",
        today=date(2026, 11, 7),
    )


class StubReviewer:
    def __init__(self, verdict="PASS", issues=None, raw=None):
        self.calls = []
        self.verdict = verdict
        self.issues = [] if issues is None else issues
        self.raw = raw

    async def complete_with_fallback(self, chain, request):
        self.calls.append((chain, request))
        content = self.raw if self.raw is not None else json.dumps({
            "verdict": self.verdict, "issues": self.issues
        })
        return SimpleNamespace(content=content)


async def test_approved_customer_delivery_requires_exact_reviewed_content(sample_pack, monkeypatch):
    reviewer = StubReviewer()
    approval = await independent_review(sample_pack, reviewer)
    assert len(reviewer.calls) == 1
    assert reviewer.calls[0][0] == "gemini"
    require_release(sample_pack, approval)

    published = docpack_tool.publish(
        sample_pack, scope="project", project_id="valid-project-id", approval=approval,
    )
    assert published["files"][0]["format"] == "xlsx"

    from src.services import email_service
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(email_service, "send_email", sender)
    assert not await docpack_tool.email_pack("client@example.org", sample_pack)
    sender.assert_not_awaited()
    assert await docpack_tool.email_pack(
        "client@example.org", sample_pack, approval=approval,
    )
    sender.assert_awaited_once()

    sample_pack.files[0] = replace(sample_pack.files[0], content=sample_pack.files[0].content + b"x")
    with pytest.raises(DocGenError, match="independently reviewed approval"):
        require_release(sample_pack, approval)
    with pytest.raises(DocGenError, match="independently reviewed approval"):
        docpack_tool.publish(
            sample_pack, scope="project", project_id="valid-project-id", approval=approval,
        )


@pytest.mark.parametrize("reviewer", [
    None,
    StubReviewer(verdict="RETURN", issues=["Missing evidence"]),
    StubReviewer(verdict="PASS", issues=["Not approved"]),
    StubReviewer(raw="Verdict: PASS"),
    StubReviewer(raw='{"verdict": "PASS"}'),
    StubReviewer(raw='{"verdict": "PASS", "issues": [], "other": true}'),
])
async def test_missing_or_invalid_independent_review_blocks_release(sample_pack, reviewer):
    with pytest.raises(DocGenError, match="review"):
        await independent_review(sample_pack, reviewer)


async def test_numeric_invention_blocks_review_even_when_model_says_pass(sample_pack):
    sample_pack.narrative.summary_ar += " حجم السوق 999999999 ريال"
    reviewer = StubReviewer()
    with pytest.raises(DocGenError, match="numeric claims"):
        await independent_review(sample_pack, reviewer)
    assert reviewer.calls == []


async def test_dropped_model_narrative_never_gets_release(sample_pack):
    sample_pack.narrative.source = "dropped"
    with pytest.raises(DocGenError, match="numeric safety"):
        await independent_review(sample_pack, StubReviewer())


async def test_public_demo_rejects_uploaded_files_even_with_valid_sample():
    from src.main import app
    import httpx

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/docpack/demo",
            data={"sample": "1"},
            files={"file": ("private.csv", b"revenue\n123\n", "text/csv")},
        )
    assert response.status_code == 400
    assert "لا تقبل" in response.text
