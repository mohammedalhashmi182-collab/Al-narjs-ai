"""Feasibility-study ladder, add-on agents, annual billing and renewals."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.owner_auth import make_session_token
from src.db.session import Base
from src.models import ClientProject, Payment
from src.models.company import OutboundMessage
from src.services import catalog, ceo_advisor, renewals
from src.services import payments as pm

NOW = datetime(2026, 10, 13, 9, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------- catalog

def test_ladder_prices_and_agents():
    ladder = {k: (catalog.PACKAGES[k]["name"], catalog.PACKAGES[k]["amount"], catalog.plan_agent_count(k))
              for k in catalog.PACKAGE_ORDER}
    assert ladder == {
        "starter": ("انطلاقة", 49900, 1),
        "team": ("فريق", 149900, 3),
        "scale": ("توسّع", 299900, 6),
        "company": ("الشركة الكاملة", 599900, 12),
    }
    assert catalog.RECOMMENDED_PACKAGE == "scale"


def test_addon_and_annual_amounts():
    assert catalog.ADDON_AGENT["amount"] == 49900 and catalog.ADDON_AGENT["price"] == "499"
    assert catalog.plan_amount("team", "monthly", 2) == 149900 + 2 * 49900
    # annual: pay 10 months, get 12
    assert catalog.plan_amount("scale", "annual") == 299900 * 10
    assert catalog.plan_amount("team", "annual", 1) == (149900 + 49900) * 10
    assert catalog.BILLING_PERIODS["annual"]["months_granted"] == 12


@pytest.mark.parametrize("n,expected", [
    (1, ("starter", 0)),
    (2, ("starter", 1)),   # 898 < 1,499
    (3, ("starter", 2)),   # 1,297 < 1,499
    (4, ("team", 1)),      # 1,898 < 2,999
    (5, ("team", 2)),      # 2,297 < 2,999
    (6, ("scale", 0)),     # team + 3 is more than "slightly"
    (7, ("scale", 1)),     # 3,398 < 5,999
    (8, ("scale", 2)),
    (9, ("company", 0)),
    (12, ("company", 0)),
    (14, ("company", 2)),  # beyond the top tier the gap is add-ons
])
def test_recommend_offer_uses_addons_only_when_cheaper(n, expected):
    plan, addons = ceo_advisor.recommend_offer(n)
    assert (plan, addons) == expected
    assert catalog.plan_agent_count(plan) + addons >= n
    assert addons <= catalog.MAX_SUGGESTED_ADDONS or plan == catalog.PACKAGE_ORDER[-1]


def test_full_company_request_is_the_top_tier():
    assert ceo_advisor.recommend_offer(3, full_company=True) == ("company", 0)


def test_build_result_exposes_addons_and_annual():
    d = ceo_advisor.Diagnosis(agents=["store_manager", "customer_service"])
    r = ceo_advisor.build_result(d)
    plan = r["plan"]
    assert plan["key"] == "starter" and plan["addons"] == 1
    assert plan["agents_included"] == 2
    assert plan["base_halalas"] == 49900 + 49900
    assert plan["total_halalas"] == pm.total_with_vat(99800)
    assert plan["annual_halalas"] == 99800 * 10
    assert r["cta"]["subscribe"].startswith("/portal?pkg=starter&addons=1&agents=")


# ---------------------------------------------------------------- payments

def test_package_amount_validates_period_and_addons():
    assert pm.package_amount("team") == 149900
    assert pm.package_amount("team", "annual") == 1499000
    assert pm.package_amount("team", "monthly", 3) == 149900 + 3 * 49900
    with pytest.raises(pm.PaymentError):
        pm.package_amount("team", "weekly")
    with pytest.raises(pm.PaymentError):
        pm.package_amount("team", "monthly", -1)
    with pytest.raises(pm.PaymentError):
        pm.package_amount("team", "monthly", catalog.MAX_ADDON_AGENTS + 1)


def test_add_months_clamps_to_month_end():
    assert pm.add_months(datetime(2026, 1, 31, tzinfo=timezone.utc), 1).day == 28
    assert pm.add_months(datetime(2026, 11, 15, tzinfo=timezone.utc), 12).year == 2027


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_annual_order_amount_vat_and_gateway_check_agree(maker):
    async with maker() as s:
        p = await pm.create_payment(s, "scale", "x", "0555000000", None, billing_period="annual", addons=1)
    assert p.amount == (299900 + 49900) * 10
    assert p.billing_period == "annual" and p.addon_agents == 1
    assert "سنوي" in p.description and "وكيل إضافي" in p.description
    total = pm.total_with_vat(p.amount)
    assert pm.expected_charge(p) == total
    assert pm.gateway_amount_matches(p, {"amount": total, "currency": "SAR"})
    assert not pm.gateway_amount_matches(p, {"amount": pm.total_with_vat(349900), "currency": "SAR"})


async def test_initiate_moyasar_charges_the_annual_total(maker, monkeypatch):
    from src.config import settings as st

    captured = {}

    class _R:
        status_code = 201
        text = ""

        def json(self):
            return {"id": "inv_1", "url": "https://checkout.moyasar.com/invoices/inv_1"}

    async def _post(self, url, *a, **k):
        captured.update(k.get("json") or {})
        return _R()

    monkeypatch.setattr(httpx.AsyncClient, "post", _post)
    monkeypatch.setattr(st, "moyasar_api_secret", "sk_" + "live_FAKE-FOR-TESTS")
    async with maker() as s:
        p = await pm.create_payment(s, "team", "x", None, None, billing_period="annual")
        await pm.initiate_moyasar(s, p, pm.source_mada())
    assert captured["amount"] == pm.total_with_vat(1499000) == 1723850


async def _project(s, *, end, period="monthly", addons=0, status="active", package="team"):
    proj = ClientProject(client_name="عميل", phone="0555000001", package=package, status=status,
                         billing_period=period, addon_agents=addons, current_period_end=end)
    s.add(proj)
    await s.commit()
    return proj


async def test_payment_sets_and_extends_the_period(maker):
    async with maker() as s:
        proj = ClientProject(client_name="c", phone="0555000002", package="team", status="pending")
        s.add(proj)
        await s.commit()
        pay = await pm.create_payment(s, "team", "c", "0555000002", None, project_id=proj.id)
        pay.status = "paid"
        await s.commit()
        first = await pm.activate_subscription(s, pay)
        assert first["activated"] and proj.status == "active"
        end1 = proj.current_period_end
        assert end1 is not None
        # idempotent: the same order never extends twice
        await pm.activate_subscription(s, pay)
        assert proj.current_period_end == end1
        # an annual renewal paid early extends from the old end by 12 months
        ren = await pm.create_payment(s, "team", "c", "0555000002", None, project_id=proj.id,
                                      billing_period="annual", is_renewal=True)
        ren.status = "paid"
        await s.commit()
        await pm.activate_subscription(s, ren)
        end2 = proj.current_period_end
        if end1.tzinfo is None:
            end1 = end1.replace(tzinfo=timezone.utc)
        if end2.tzinfo is None:
            end2 = end2.replace(tzinfo=timezone.utc)
        assert end2 == pm.add_months(end1, 12)
        assert proj.billing_period == "annual"


async def test_renewal_invoices_once_and_queues_a_draft_reminder(maker):
    async with maker() as s:
        proj = await _project(s, end=NOW + timedelta(days=3), period="annual", addons=1)
        first = await renewals.run_renewals(s, now=NOW, days_before=5, use_gateway=False)
        second = await renewals.run_renewals(s, now=NOW, days_before=5, use_gateway=False)
        assert len(first["invoiced"]) == 1 and second["invoiced"] == []
        pay = (await s.execute(select(Payment).where(Payment.project_id == proj.id))).scalars().all()
        assert len(pay) == 1
        assert pay[0].is_renewal and pay[0].billing_period == "annual" and pay[0].addon_agents == 1
        assert pay[0].amount == (149900 + 49900) * 10
        assert pay[0].status == "invoice"
        msgs = (await s.execute(select(OutboundMessage))).scalars().all()
        assert len(msgs) == 1
        assert msgs[0].status == renewals.REMINDER_STATUS == "draft"  # recorded, never sent
        assert str(pay[0].id) in msgs[0].text


async def test_renewal_ignores_far_and_legacy_projects(maker):
    async with maker() as s:
        await _project(s, end=NOW + timedelta(days=20))
        await _project(s, end=None)
        out = await renewals.run_renewals(s, now=NOW, days_before=5, use_gateway=False)
        assert out["invoiced"] == [] and out["expired"] == []


async def test_renewal_uses_moyasar_when_configured(maker, monkeypatch):
    seen = {}

    async def _initiate(session, payment, source, **kw):
        seen["amount"] = pm.total_with_vat(payment.amount)
        seen["callback"] = kw.get("callback_url")
        payment.gateway = "moyasar"
        payment.gateway_payment_id = "inv_r1"
        await session.commit()
        return {"id": "inv_r1", "checkout_url": "https://checkout.moyasar.com/invoices/inv_r1"}

    monkeypatch.setattr(pm, "initiate_moyasar", _initiate)
    async with maker() as s:
        await _project(s, end=NOW + timedelta(days=1))
        out = await renewals.run_renewals(s, now=NOW, use_gateway=True, base_url="https://karmaai.online")
    assert out["invoiced"][0]["gateway"] == "moyasar"
    assert seen["amount"] == pm.total_with_vat(149900)
    assert seen["callback"] == "https://karmaai.online/webhooks/moyasar"


async def test_access_expires_only_after_the_grace_period(maker):
    async with maker() as s:
        in_grace = await _project(s, end=NOW - timedelta(days=2))
        lapsed = await _project(s, end=NOW - timedelta(days=4))
        out = await renewals.run_renewals(s, now=NOW, use_gateway=False)
        assert str(lapsed.id) in out["expired"]
        assert lapsed.status == "expired"
        assert in_grace.status == "active"
        assert any(i["project_id"] == str(in_grace.id) for i in out["invoiced"])


async def test_owner_endpoint_runs_renewals_and_is_owner_only(maker):
    from src.main import app

    app.state.session_factory = maker
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as anon:
        assert (await anon.post("/api/owner/billing/renewals/run")).status_code == 401
    async with httpx.AsyncClient(transport=transport, base_url="http://test",
                                 cookies={"narjis_owner": make_session_token()}) as owner:
        r = await owner.post("/api/owner/billing/renewals/run?days_before=5")
    assert r.status_code == 200
    assert r.json()["grace_days"] == 3


async def test_checkout_api_bills_annual_with_addons(maker):
    from src.main import app

    app.state.session_factory = maker
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/payments", json={"package": "starter", "method": "invoice",
                                                "billing_period": "annual", "addons": 1})
        bad = await c.post("/api/payments", json={"package": "starter", "method": "invoice",
                                                  "billing_period": "weekly"})
    body = r.json()
    assert body["amount"] == (49900 + 49900) * 10
    assert body["total"] == pm.total_with_vat(body["amount"])
    assert bad.status_code == 400


def test_landing_has_the_billing_toggle_and_annual_prices():
    from fastapi.testclient import TestClient

    from src.main import app

    with TestClient(app) as c:
        page = c.get("/home").text
    assert 'id="billingToggle"' in page and 'data-billing="annual"' in page
    for key in catalog.PACKAGE_ORDER:
        annual = catalog.plan_amount(key, "annual") // 100
        assert f'data-annual="{annual:,}"' in page
        assert f"/portal?pkg={key}&amp;billing=annual" in page
    assert catalog.ADDON_AGENT["price"] in page
