"""Phone quality gate on the public capture endpoint.

The early-access form blocks submission client-side; this is the server-side
enforcement that nothing reaches the database, the welcome email or the owner
Telegram alert with an unusable number.
"""

from __future__ import annotations

from uuid import UUID

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models import AcquisitionLead


async def _make_engine():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def api():
    from src.core.owner_auth import make_session_token
    from src.main import app

    engine, maker = await _make_engine()
    app.state.session_factory = maker
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"narjis_owner": make_session_token()},
    ) as client:
        yield client, maker
    await engine.dispose()


async def _count(maker) -> int:
    async with maker() as session:
        return (await session.execute(select(func.count()).select_from(AcquisitionLead))).scalar_one()


EARLY = {"name": "شركة الأثر", "email": "owner@example.com", "package": "early_access"}


@pytest.mark.parametrize(
    "phone",
    [
        None,
        "",
        "12345",
        "0512",
        "0123456789",
        "05501234567890",
        "+9665012",
        "abc",
        "+966 50 00",
    ],
)
async def test_early_access_rejects_unusable_numbers(api, phone: str | None) -> None:
    client, maker = api
    payload = dict(EARLY)
    if phone is not None:
        payload["phone"] = phone

    resp = await client.post("/api/leads", json=payload)

    assert resp.status_code == 400
    assert "رقم الجوال" in resp.json()["detail"]
    assert await _count(maker) == 0


@pytest.mark.parametrize(
    ("raw", "stored"),
    [
        ("0550123456", "+966550123456"),
        ("+966550123456", "+966550123456"),
        ("966550123456", "+966550123456"),
        ("0501234567", "+966501234567"),
        ("055 012 3456", "+966550123456"),
        ("+966 55 012 3456", "+966550123456"),
        ("٠٥٥٠١٢٣٤٥٦", "+966550123456"),
    ],
)
async def test_early_access_accepts_valid_saudi_mobiles(api, raw: str, stored: str) -> None:
    client, maker = api
    resp = await client.post("/api/leads", json={**EARLY, "phone": raw})

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True

    async with maker() as session:
        lead = (
            await session.execute(select(AcquisitionLead).where(AcquisitionLead.id == UUID(body["lead_id"])))
        ).scalar_one()
        assert lead.phone == stored
        assert lead.lead_status == "NEW"


async def test_any_funnel_rejects_a_nonsense_number(api) -> None:
    client, maker = api
    resp = await client.post(
        "/api/leads",
        json={"name": "محل الاختبار", "phone": "hello", "email": "a@b.com", "package": "social"},
    )
    assert resp.status_code == 400
    assert await _count(maker) == 0


async def test_guide_funnel_keeps_its_optional_phone(api) -> None:
    """The lead-magnet form still works without a number — only junk is rejected."""
    client, maker = api
    resp = await client.post(
        "/api/leads",
        json={"name": "قارئ الدليل", "email": "reader@example.com", "package": "guide"},
    )
    assert resp.status_code == 200
    assert await _count(maker) == 1


async def test_rejected_number_triggers_no_side_effects(api, monkeypatch) -> None:
    """No lead row, no welcome email, no owner alert for a rejected number."""
    client, _maker = api
    from src.services import email_service, telegram_sender

    calls: list[str] = []
    monkeypatch.setattr(email_service, "send_welcome", lambda *a, **k: calls.append("email"))
    monkeypatch.setattr(telegram_sender, "send_owner_alert", lambda *a, **k: calls.append("telegram"))

    resp = await client.post("/api/leads", json={**EARLY, "phone": "1234"})

    assert resp.status_code == 400
    assert calls == []