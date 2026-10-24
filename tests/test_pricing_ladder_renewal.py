"""Feasibility-study ladder, add-on agents, annual billing and renewals."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest

# Retain mocked integration coverage for the separately approved future release.
pytestmark = pytest.mark.usefixtures("moyasar_release")
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.owner_auth import make_session_token
from src.db.session import Base
from src.models import ClientProject, Payment
from src.models.company import OutboundMessage
from src.services import catalog, ceo_advisor, renewals
from src.services import payments as pm

@pytest.fixture(autouse=True)
def _bank_transfer_code_path(monkeypatch):
    monkeypatch.setenv("CUSTOMER_BANK_TRANSFER_ENABLED", "1")


NOW = datetime(2026, 10, 13, 9, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------- catalog

def test_ladder_prices_and_agents():
    ladder = {k: (catalog.PACKAGES[k]["name"], catalog.PACKAGES[k]["amount"], catalog.plan_agent_count(k))
              for k in catalog.PACKAGE_ORDER}
    assert ladder == {
        "bidaya": ("البداية", 79000, 5),
        "numuw": ("النمو", 149000, 15),
        "sharikat": ("الشركات", 299000, 34),
    }
    assert catalog.PACKAGES["sharikat"]["display_agents"] == 35
    assert catalog.RECOMMENDED_PACKAGE == "numuw"
    # retired public ids stay billable only as grandfathered renewals
    assert catalog.is_legacy_tier("radd") and catalog.LEGACY_TIERS["radd"]["amount"] == 59900
    assert catalog.is_legacy_tier("bay") and catalog.is_legacy_tier("tashgheel")
    assert "radd" not in catalog.PACKAGES


def test_addon_and_annual_amounts():
    assert catalog.ADDON_AGENT["amount"] == 14900 and catalog.ADDON_AGENT["price"] == "149"
    assert catalog.plan_amount("bidaya", "monthly", 2) == 79000 + 2 * 14900
    # annual: pay 10 months, get 12
    assert catalog.plan_amount("numuw", "annual") == 149000 * 10
    assert catalog.plan_amount("bidaya", "annual", 1) == (79000 + 14900) * 10
    # a ردّ subscriber renews at the old price and the old 299 add-on
    assert catalog.plan_amount("radd", "monthly", 2) == 59900 + 2 * 29900
    assert catalog.BILLING_PERIODS["annual"]["months_granted"] == 12


@pytest.mark.parametrize("n,expected", [
    (1, ("bidaya", 0)),
    (5, ("bidaya", 0)),
    (6, ("bidaya", 1)),     # 939 < 1,490
    (7, ("bidaya", 2)),     # 1,088 < 1,490
    (8, ("numuw", 0)),      # three add-ons is more than "slightly"
    (15, ("numuw", 0)),
    (16, ("numuw", 1)),     # 1,639 < 2,990
    (17, ("numuw", 2)),     # 1,788 < 2,990
    (18, ("sharikat", 0)),
    (34, ("sharikat", 0)),
    (36, ("sharikat", 2)),  # beyond the roster the gap is add-ons
])
def test_recommend_offer_uses_addons_only_when_cheaper(n, expected):
    plan, addons = ceo_advisor.recommend_offer(n)
    assert (plan, addons) == expected
    assert catalog.plan_agent_count(plan) + addons >= n
    assert addons <= catalog.MAX_SUGGESTED_ADDONS or plan == catalog.PACKAGE_ORDER[-1]


def test_full_company_request_is_the_top_tier():
    assert ceo_advisor.recommend_offer(3, full_company=True) == ("sharikat", 0)


def test_build_result_exposes_addons_and_annual():
    # Agents that ARE in the Bidaya team (the plan must really include them).
    d = ceo_advisor.Diagnosis(agents=catalog.PACKAGE_TEAMS["bidaya"][1:4])
    r = ceo_advisor.build_result(d)
    plan = r["plan"]
    assert plan["key"] == "bidaya" and plan["addons"] == 0
    assert plan["agents_included"] == 5
    assert plan["base_halalas"] == 79000
    assert plan["total_halalas"] == pm.total_with_vat(79000)
    assert plan["annual_halalas"] == 79000 * 10
    assert r["cta"]["subscribe"].startswith("/portal?pkg=bidaya&agents=")


# ---------------------------------------------------------------- payments

def test_package_amount_validates_period_and_addons():
    assert pm.package_amount("numuw") == 149000
    assert pm.package_amount("numuw", "annual") == 1490000
    assert pm.package_amount("numuw", "monthly", 3) == 149000 + 3 * 14900
    with pytest.raises(pm.PaymentError):
        pm.package_amount("numuw", "weekly")
    with pytest.raises(pm.PaymentError):
        pm.package_amount("numuw", "monthly", -1)
    with pytest.raises(pm.PaymentError):
        pm.package_amount("numuw", "monthly", catalog.MAX_ADDON_AGENTS + 1)
    # retired tiers can no longer be bought
    with pytest.raises(pm.PaymentError):
        pm.package_amount("team")
    with pytest.raises(pm.PaymentError):
        pm.package_amount("radd")


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
        p = await pm.create_payment(s, "numuw", "x", "0555000000", None, billing_period="annual", addons=1)
    assert p.amount == (149000 + 14900) * 10  # annual: setup fee waived
    assert p.billing_period == "annual" and p.addon_agents == 1
    assert "سنوي" in p.description and "وكيل إضافي" in p.description
    total = pm.total_with_vat(p.amount)
    assert pm.expected_charge(p) == total
    assert pm.gateway_amount_matches(p, {"amount": total, "currency": "SAR"})
    assert not pm.gateway_amount_matches(p, {"amount": pm.total_with_vat(179900), "currency": "SAR"})


@pytest.mark.usefixtures("vat15")
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
    monkeypatch.setattr(st, "moyasar_publishable_key", "pk_" + "live_FAKE-FOR-TESTS")
    async with maker() as s:
        p = await pm.create_payment(s, "numuw", "x", None, None, billing_period="annual")
        await pm.initiate_moyasar(s, p, pm.source_mada())
    assert captured["amount"] == pm.total_with_vat(1490000) == 1713500


async def _project(s, *, end, period="monthly", addons=0, status="active", package="team"):
    proj = ClientProject(client_name="عميل", phone="0555000001", package=package, status=status,
                         billing_period=period, addon_agents=addons, current_period_end=end)
    s.add(proj)
    await s.commit()
    return proj


async def test_payment_sets_and_extends_the_period(maker):
    async with maker() as s:
        proj = ClientProject(client_name="c", phone="0555000002", package="numuw", status="pending")
        s.add(proj)
        await s.commit()
        pay = await pm.create_payment(s, "numuw", "c", "0555000002", None, project_id=proj.id)
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
        ren = await pm.create_payment(s, "numuw", "c", "0555000002", None, project_id=proj.id,
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
        # grandfathered: a legacy "team" subscriber renews at the old 1,499 + 499 add-on
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


async def test_renewal_reminder_links_only_to_consent_gated_invoice(maker, monkeypatch):
    from sqlalchemy import select
    from src.models.company import OutboundMessage

    async def _initiate(session, payment, source, **kw):
        payment.gateway = "moyasar"
        payment.gateway_payment_id = "inv_r2"
        await session.commit()
        return {"id": "inv_r2", "checkout_url": "https://checkout.moyasar.com/invoices/inv_r2"}

    monkeypatch.setattr(pm, "initiate_moyasar", _initiate)
    async with maker() as s:
        await _project(s, end=NOW + timedelta(days=1))
        out = await renewals.run_renewals(s, now=NOW, use_gateway=True, base_url="https://karmaai.online")
        pid = out["invoiced"][0]["payment_id"]
        msgs = (await s.execute(select(OutboundMessage))).scalars().all()
    assert msgs
    for m in msgs:
        assert "moyasar.com" not in m.text and "inv_r2" not in m.text
        assert f"https://karmaai.online/invoice/{pid}" in m.text


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


@pytest.mark.usefixtures("founding_full")
async def test_checkout_api_bills_annual_with_addons(maker):
    from src.main import app

    app.state.session_factory = maker
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", cookies={"narjis_owner": make_session_token()}
    ) as c:
        r = await c.post("/api/payments", json={"refund_consent": True, "package": "bidaya", "method": "invoice",
                                                "billing_period": "annual", "addons": 1})
        bad = await c.post("/api/payments", json={"refund_consent": True, "package": "bidaya", "method": "invoice",
                                                  "billing_period": "weekly"})
    body = r.json()
    assert body["amount"] == (79000 + 14900) * 10
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


# ---------------------------------------------------------------- pricing v2

def test_usage_limits_are_in_the_catalog():
    assert {k: catalog.PACKAGES[k]["limits"] for k in catalog.PACKAGE_ORDER} == {
        "bidaya": {"conversations": 1000, "voice_minutes": 0, "meta_cap": 10000},
        "numuw": {"conversations": 4000, "voice_minutes": 0, "meta_cap": 25000},
        "sharikat": {"conversations": 10000, "voice_minutes": 0, "meta_cap": 50000},
    }
    assert catalog.plan_limits("numuw", addon_conversations=2)["conversations"] == 6000
    # a بيع subscriber keeps the voice allowance that plan was sold with
    assert catalog.plan_limits("bay", addon_voice=1)["voice_minutes"] == 250


def test_usage_addons_and_enterprise():
    assert catalog.USAGE_ADDONS["conversations"]["amount"] == 9900
    assert catalog.USAGE_ADDONS["voice_minutes"]["amount"] == 9900
    assert catalog.USAGE_ADDONS["meta_overage"]["at_cost"] is True
    assert catalog.ENTERPRISE["by_quote"] and catalog.ENTERPRISE["price_from"] == "6000"
    assert "enterprise" not in catalog.PACKAGES  # by quote only, never a checkout key


def test_setup_fee_first_monthly_order_only():
    assert [catalog.PACKAGES[k]["setup_fee"] for k in catalog.PACKAGE_ORDER] == [0, 99000, 199000]
    assert catalog.setup_fee("numuw") == 99000
    assert catalog.setup_fee("numuw", "annual") == 0
    assert catalog.setup_fee("numuw", renewal=True) == 0
    assert catalog.setup_fee("sharikat", founding=True) == 0


def test_founding_offer_and_guarantee():
    f = catalog.FOUNDING_OFFER
    assert (f["seats"], f["annual_pct"], f["monthly_pct"], f["monthly_commitment_months"]) == (15, 30, 20, 3)
    assert catalog.founding_amount("numuw", "annual") == 1490000 * 70 // 100
    assert catalog.founding_amount("numuw") == 149000 - 149000 * 20 // 100
    assert catalog.SETUP_GUARANTEE["business_days"] == 10
    assert catalog.SETUP_GUARANTEE["refunds"] == "setup_fee"


def test_per_agent_price_falls_with_the_plan():
    assert [catalog.PACKAGES[k]["per_agent_price"] for k in catalog.PACKAGE_ORDER] == ["158", "99", "85"]


async def test_first_monthly_order_adds_setup_fee_outside_promo(maker):
    async with maker() as s:
        p = await pm.create_payment(s, "numuw", "x", "0555000000", None)
        r = await pm.create_payment(s, "numuw", "x", "0555000000", None, is_renewal=True)
    assert p.amount == 149000 + 99000 and "رسوم إعداد" in p.description
    assert r.amount == 149000


async def test_legacy_tier_renews_at_old_price_but_cannot_be_bought(maker):
    async with maker() as s:
        ren = await pm.create_payment(s, "scale", "x", None, None, addons=1, is_renewal=True)
        assert ren.amount == 299900 + 49900 and ren.package == "scale"
        with pytest.raises(pm.PaymentError):
            await pm.create_payment(s, "scale", "x", None, None)
        kept = await pm.create_payment(s, "radd", "x", None, None, addons=1, is_renewal=True)
        assert kept.amount == 59900 + 29900 and kept.package == "radd"
        with pytest.raises(pm.PaymentError):
            await pm.create_payment(s, "bay", "x", None, None)


def test_portal_sends_addons_as_an_integer():
    html = open("src/web/templates/portal.html", encoding="utf-8").read()
    assert "const coAddons = Math.max(0, Math.min(12, parseInt(" in html
    assert "addons: coAddons," in html


async def test_checkout_api_rejects_a_list_of_addons(maker):
    from src.main import app

    app.state.session_factory = maker
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/payments", json={"refund_consent": True, "package": "numuw", "method": "invoice",
                                                "addons": ["sales_closer"]})
    assert r.status_code == 422


def test_copy_no_longer_promises_five_agents_per_subscription():
    from src.services import blog_articles_1, blog_en

    text = repr(blog_en.__dict__) + repr(blog_articles_1.ARTICLES)
    assert "five agents" not in text and "five-agent team" not in text
    assert "خمسة وكلاء" not in text


def test_portal_packages_api_exposes_limits_and_enterprise():
    from fastapi.testclient import TestClient

    from src.main import app

    with TestClient(app) as c:
        d = c.get("/api/portal/packages").json()
    assert [p["key"] for p in d["packages"]] == catalog.PACKAGE_ORDER
    assert d["packages"][1]["recommended"] and d["packages"][1]["setup_fee"] == 99000
    assert d["enterprise"] is None and d["addon"]["price"] == "149"
    assert d["usage_addons"]["conversations"]["purchasable"] is False
