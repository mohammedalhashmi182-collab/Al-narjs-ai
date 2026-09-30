"""Guards for the KarmaAI consultant persona, silent lead extraction and the
consult-assistant lead capture helper (src/core/karma_persona.py,
src/services/karma_lead.py).

The persona is operator-facing product config: it must keep the project rules
(real prices only, no fabricated proof) and its lead block must never leak into
the visible assistant reply.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.karma_persona import LEAD_MARK, build_consult_system_prompt, extract_lead


# ---------------------------------------------------------------------------
# persona
# ---------------------------------------------------------------------------


def test_persona_bundles_identity_products_and_rules():
    prompt = build_consult_system_prompt(
        locale="ar",
        packages_text="باقة أساسية (199 SAR/mo)",
        employees_text="مديرة السوشيال ميديا",
    )
    assert "KarmaAI" in prompt
    assert "karmaai.online" in prompt
    assert "باقة أساسية (199 SAR/mo)" in prompt
    for marker in ("Automated Digital Teams", "Workflow Automation", "Custom AI Integrations"):
        assert marker in prompt
    assert "lead_qualification" in prompt
    assert LEAD_MARK in prompt
    assert "never invent" in prompt or "never invent or guess" in prompt


def test_persona_honours_locale_language_instruction():
    ar = build_consult_system_prompt(locale="ar", packages_text="x", employees_text="y")
    en = build_consult_system_prompt(locale="en", packages_text="x", employees_text="y")
    assert "اللغة العربية الفصحى" in ar
    assert "اللغة العربية الفصحى" not in en
    assert "business English" in en


# ---------------------------------------------------------------------------
# silent lead extraction
# ---------------------------------------------------------------------------


def test_extract_lead_missing_returns_unchanged():
    content = "رد عادي بدون أيدي\n\nالتفاصيل كاملة"
    data, reply = extract_lead(content)
    assert data is None
    assert reply == content.strip()


def test_extract_lead_valid_block_is_stripped_from_reply():
    payload = (
        '{"event":"lead_qualification","client_name":"متجر الأناقة",'
        '"phone":"0551112223","qualification_score":"High"}'
    )
    content = f"هذا الرد للمسافر\n\n{LEAD_MARK}\n{payload}"
    data, reply = extract_lead(content)
    assert data is not None
    assert data["client_name"] == "متجر الأناقة"
    assert data["qualification_score"] == "High"
    assert LEAD_MARK not in reply
    assert "lead_qualification" not in reply
    assert "لم نشق" not in reply


def test_extract_lead_garbage_json_keeps_reply():
    content = f"رد \n\n{LEAD_MARK}\n{{not json}}"
    data, reply = extract_lead(content)
    assert data is None
    assert reply == "رد"


# ---------------------------------------------------------------------------
# consult-assistant lead capture
# ---------------------------------------------------------------------------


async def _make_engine():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        from src.models import Base
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def maker():
    from src.main import app

    engine, maker_ = await _make_engine()
    app.state.session_factory = maker_
    yield maker_
    await engine.dispose()


async def test_capture_creates_and_dedupes(maker) -> None:
    from src.models import AcquisitionLead
    from src.services.karma_lead import capture_consult_lead

    result = await capture_consult_lead(maker, {
        "client_name": "مطعم الأصالة",
        "phone": "0553078789",
        "email": "lead@example.com",
        "business_type": "restaurant_food",
        "primary_bottleneck": "لا يوجد محتوى يومي",
        "qualification_score": "High",
    })
    assert result["created"] is True

    async with maker() as session:
        rows = (await session.execute(select(AcquisitionLead))).scalars().all()
        assert len(rows) == 1
        lead = rows[0]
        assert lead.source == "consult_assistant"
        assert lead.lead_status == "NEW"
        assert lead.phone == "+966553078789"

    again = await capture_consult_lead(maker, {
        "client_name": "مطعم الأصالة",
        "phone": "0553078789",
        "email": "lead@example.com",
        "qualification_score": "High",
    })
    assert again["created"] is False
    assert again["dedupe"] is True
    async with maker() as session:
        rows = (await session.execute(select(AcquisitionLead))).scalars().all()
        assert len(rows) == 1


async def test_capture_swallows_empty_input(maker) -> None:
    from src.services.karma_lead import capture_consult_lead

    assert await capture_consult_lead(maker, {}) == {
        "created": False, "lead_id": None, "dedupe": False,
    }