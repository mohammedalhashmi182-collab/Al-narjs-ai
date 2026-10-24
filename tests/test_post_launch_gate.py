"""Post-launch gate regressions (main 802917e)."""
from __future__ import annotations

import pathlib

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.config import settings as st
from src.db.session import Base
from src.services import payments as pm


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_invoice_page_hides_card_button_while_moyasar_on_hold(maker, monkeypatch):
    from src.main import app

    monkeypatch.setenv("VAT_RATE", "0")
    monkeypatch.setattr(st, "moyasar_api_secret", "sk_" + "live_" + "FAKE-FOR-TESTS")
    monkeypatch.setattr(pm, "MOYASAR_ON_HOLD", True)
    app.state.session_factory = maker
    async with maker() as s:
        p = await pm.create_payment(s, "bidaya", "a", "0555000001", None, founding=False)
        p.gateway = "invoice"
        await s.commit()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get(f"/invoice/{p.id}")
    assert r.status_code == 200
    assert 'id="invoicePayCard"' not in r.text


def test_checkout_total_with_setup_fee_is_not_labelled_monthly():
    src = pathlib.Path("src/web/templates/portal.html").read_text(encoding="utf-8")
    assert "Due today: " in src and "المستحق اليوم: " in src
