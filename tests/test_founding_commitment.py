"""Founding commitment: 3 months upfront vs monthly with clawback on early cancellation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.owner_auth import make_session_token
from src.db.session import Base
from src.models import ClientProject
from src.services import catalog, founding
from src.services import payments as pm


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _project(s, package="radd"):
    proj = ClientProject(client_name="عميل", phone="0555000009", package=package, status="pending")
    s.add(proj)
    await s.commit()
    return proj


async def _paid(s, proj, period="monthly"):
    pay = await pm.create_payment(s, proj.package, "x", "0555000010", None, project_id=proj.id,
                                  billing_period=period, founding=None)
    pay.status = "paid"
    await s.commit()
    await pm.activate_subscription(s, pay)
    return pay


async def test_upfront_three_months_is_founding_only(maker):
    async with maker() as s:
        pay = await pm.create_payment(s, "radd", "a", "0555000001", None, billing_period="quarterly", founding=None)
        assert pay.founding
        assert pay.amount == 3 * catalog.founding_amount("radd", "monthly", 0)
        with pytest.raises(pm.PaymentError):
            await pm.create_payment(s, "radd", "b", "0555000002", None, billing_period="quarterly", founding=False)


async def test_upfront_activation_has_no_commitment_and_renews_monthly(maker):
    async with maker() as s:
        proj = await _project(s)
        await _paid(s, proj, "quarterly")
        assert proj.founding and proj.founding_commitment_until is None
        assert proj.billing_period == "monthly"
        assert proj.current_period_end - datetime.now(timezone.utc).replace(tzinfo=None if proj.current_period_end.tzinfo is None else timezone.utc) > timedelta(days=85)
        res = await founding.early_cancellation(s, proj)
        assert res["clawback"] is False


async def test_monthly_early_cancel_drafts_clawback_once_and_owner_approves(maker):
    async with maker() as s:
        proj = await _project(s)
        await _paid(s, proj, "monthly")
        assert founding.in_commitment(proj)
        diff = catalog.plan_amount("radd", "monthly", 0) - catalog.founding_amount("radd", "monthly", 0)
        assert await founding.clawback_amount(s, proj) == (diff, 1)
        res = await founding.early_cancellation(s, proj)
        assert res["clawback"] and res["amount"] == diff
        again = await founding.early_cancellation(s, proj)
        assert again["already"] and again["payment_id"] == res["payment_id"]
        from uuid import UUID
        from src.models import Payment
        draft = await s.get(Payment, UUID(res["payment_id"]))
        assert draft.status == founding.CLAWBACK_STATUS and draft.gateway == "invoice"
        assert (await founding.approve_clawback(s, draft))["status"] == "invoice"
        assert (await founding.approve_clawback(s, draft))["approved"] is False


async def test_no_clawback_after_commitment(maker):
    async with maker() as s:
        proj = await _project(s)
        await _paid(s, proj, "monthly")
        later = datetime.now(timezone.utc) + timedelta(days=100)
        assert not founding.in_commitment(proj, later)
        assert (await founding.early_cancellation(s, proj, later))["clawback"] is False


async def test_endpoints_owner_only_and_flow(maker):
    from src.main import app

    async with maker() as s:
        proj = await _project(s)
        await _paid(s, proj, "monthly")
    app.state.session_factory = maker
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as anon:
        assert (await anon.post(f"/api/owner/founding/{proj.id}/early-cancel")).status_code == 401
        terms = (await anon.get("/api/founding")).json()
        assert "3" in terms["commitment_terms_en"] and terms["commitment_terms_ar"]
    async with httpx.AsyncClient(transport=transport, base_url="http://test",
                                 cookies={"narjis_owner": make_session_token()}) as owner:
        r = await owner.post(f"/api/owner/founding/{proj.id}/early-cancel")
        assert r.status_code == 200 and r.json()["clawback"]
        pid = r.json()["payment_id"]
        assert (await anon_free(transport, pid)) == 401
        ok = await owner.post(f"/api/owner/founding/clawbacks/{pid}/approve")
        assert ok.status_code == 200
        assert (await owner.post(f"/api/owner/founding/clawbacks/{pid}/approve")).status_code == 409


async def anon_free(transport, pid):
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as anon:
        return (await anon.post(f"/api/owner/founding/clawbacks/{pid}/approve")).status_code


def test_terms_and_portal_show_commitment():
    from fastapi.testclient import TestClient

    from src.main import app

    c = TestClient(app)
    assert 'id="founding-commitment"' in c.get("/terms").text
    portal = c.get("/portal").text
    assert "coFoundingPlan" in portal and "quarterly" in portal
