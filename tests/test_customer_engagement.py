"""CEO brief: intake, confirmation, specialist drafts, CRM row. No live model calls."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.owner_auth import make_session_token
from src.db.session import Base
from src.models import AcquisitionLead, LeadEvent, Task
from src.services import customer_engagement as eng


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


class _Model:
    _clients = {"gemini": object()}

    async def complete_with_fallback(self, _name, _request):
        class _Result:
            content = "مسودة من النموذج للاختبار فقط."

        return _Result()


async def test_confirming_a_brief_fans_out_degraded_drafts_and_a_lead(maker) -> None:
    async with maker() as session:
        row = await eng.open_engagement(
            session,
            message="أبغى تصميم هوية لمشروعي الجديد في الرياض",
            locale="ar",
            name="مقهى التجربة",
        )
        assert row.stage == "clarification"
        assert "لمن" in eng.public_view(row)["reply"]
        await eng.apply_turn(session, row, "أصحاب المقاهي الصغيرة")
        assert row.stage == "brief_pending"
        await eng.apply_turn(session, row, "موافق")
        await session.commit()
        view = eng.public_view(row)

    assert view["stage"] == "ready"
    assert view["degraded"] is True
    slugs = [item["slug"] for item in view["deliverables"]]
    assert slugs[0] == "orchestrator"
    assert "product_designer" in slugs and "prototype_engineer" in slugs and "quality_gate" in slugs
    assert all(item["degraded"] for item in view["deliverables"] if item["slug"] != "orchestrator")
    assert "لم يُستدعَ نموذج اللغة" in view["deliverables"][-1]["body"] or any(
        "لم يُستدعَ" in item["body"] for item in view["deliverables"]
    )

    async with maker() as session:
        lead = (await session.execute(select(AcquisitionLead))).scalar_one()
        assert lead.source == "ceo_brief"
        assert lead.lead_status == "NEW"
        assert lead.sales_representative == "owner"
        assert (lead.raw_data or {})["engagement"]["stage"] == "ready"
        events = (await session.execute(select(LeadEvent).where(LeadEvent.lead_id == lead.id))).scalars().all()
        assert any(event.event_type == "engagement" for event in events)
        tasks = (await session.execute(select(Task).where(Task.source == "customer_brief"))).scalars().all()
        assert {task.owner_agent for task in tasks} >= {"orchestrator", "product_designer", "quality_gate"}
        assert all(task.status == "completed" for task in tasks)


async def test_model_text_replaces_the_degraded_draft(maker) -> None:
    async with maker() as session:
        row = await eng.open_engagement(session, message="أبغى تصميم شعار لمحل هدايا", provider=_Model())
        await eng.apply_turn(session, row, "للعملاء من الشباب", provider=_Model())
        await eng.apply_turn(session, row, "confirm", provider=_Model())
        view = eng.public_view(row)
    assert view["degraded"] is False
    bodies = [item["body"] for item in view["deliverables"] if item["slug"] != "orchestrator"]
    assert bodies and all(body == "مسودة من النموذج للاختبار فقط." for body in bodies)


async def test_revision_stays_on_the_brief_until_approval(maker) -> None:
    async with maker() as session:
        row = await eng.open_engagement(session, message="أبغى مقترح خطة عمل لمخبز صغير في جدة")
        await eng.apply_turn(session, row, "أصحاب الأحياء المجاورة")
        assert row.stage == "brief_pending"
        await eng.apply_turn(session, row, "أضف أن الميزانية محدودة")
        assert row.stage == "brief_pending"
        assert "محدودة" in (row.brief or {}).get("constraints", "")


async def test_http_brief_is_owner_visible_and_hidden_without_the_token(maker, monkeypatch) -> None:
    from src.main import app

    async def _no_model(*_args, **_kwargs):
        return None

    monkeypatch.setattr(eng, "_complete", _no_model)
    app.state.session_factory = maker
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        page = await client.get("/ar/brief")
        assert page.status_code == 200
        assert "الرئيس التنفيذي" in page.text
        assert "AlNarjisai@gmail.com" in page.text
        assert 'href="/voice"' in page.text
        started = await client.post("/api/engagement", json={"message": "أبغى تصميم هوية كافية للاختبار", "lang": "ar"})
        assert started.status_code == 200
        token = started.json()["token"]
        denied = await client.get("/api/owner/engagements")
        assert denied.status_code == 401
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", cookies={"narjis_owner": make_session_token()}
    ) as owner:
        listing = await owner.get("/api/owner/engagements")
        assert listing.status_code == 200
        assert listing.json()["engagements"][0]["token"] == token
        missing = await owner.get("/api/engagement/not-a-real-token")
        assert missing.status_code == 404
