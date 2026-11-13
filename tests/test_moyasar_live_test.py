"""Hidden 1 SAR Moyasar probe. It reuses hosted checkout and never activates a plan."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.config.settings import get_settings
from src.core.portal_auth import make_payment_token
from src.db.session import Base
from src.models import ClientProject
from src.services import payments as pm

TOKEN = "unit-test-payment-token-not-a-secret"
LIVE_SECRET = "sk_" + "live_unit_not_a_real_key"
LIVE_PUBLIC = "pk_" + "live_unit_not_a_real_key"
PATH = "/payment/moyasar-live-test"


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


def _token(monkeypatch, value):
    monkeypatch.setattr(get_settings(), "test_payment_token", value)


def _live(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "moyasar_api_secret", LIVE_SECRET)
    monkeypatch.setattr(settings, "moyasar_publishable_key", LIVE_PUBLIC)
    monkeypatch.setattr(settings, "moyasar_webhook_secret", None)
    pm._credential_cache.clear()


def _client(app):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    )


async def test_route_is_404_until_the_token_matches(monkeypatch):
    from src.main import app

    _token(monkeypatch, None)
    async with _client(app) as client:
        missing_env = await client.get(PATH, params={"token": TOKEN})
        assert missing_env.status_code == 404
        assert missing_env.headers.get("location") is None
    _token(monkeypatch, TOKEN)
    async with _client(app) as client:
        wrong = await client.get(PATH, params={"token": "nope"})
        bare = await client.get(PATH)
        posted = await client.post(PATH)
        assert wrong.status_code == bare.status_code == posted.status_code == 404


async def test_page_is_noindex_and_absent_from_nav_sitemap_and_llms(monkeypatch):
    from src.main import app

    _token(monkeypatch, TOKEN)
    async with _client(app) as client:
        page = await client.get(PATH, params={"token": TOKEN})
        assert page.status_code == 200, page.text
        assert TOKEN not in page.text
        assert 'content="noindex, nofollow"' in page.text
        assert page.headers["x-robots-tag"] == "noindex, nofollow"
        assert page.headers["referrer-policy"] == "no-referrer"
        assert "1.00" in page.text
        assert "دفعة تجريبية – النرجس" in page.text
        assert "<form" not in page.text  # checkout is closed without live keys
        sitemap = await client.get("/sitemap.xml")
        llms = await client.get("/llms.txt")
        robots = await client.get("/robots.txt")
    assert PATH not in sitemap.text
    assert PATH not in llms.text
    assert "TEST_PAYMENT" not in llms.text
    assert "Disallow: /payment" in robots.text
    for template in Path("src/web/templates").rglob("*.html"):
        assert PATH not in template.read_text(encoding="utf-8"), template
    from src.services import seo

    assert seo.is_public_path(PATH) is False


async def test_post_starts_a_one_sar_invoice_on_the_guest_webhook(monkeypatch, maker):
    from src.main import app

    _token(monkeypatch, TOKEN)
    _live(monkeypatch)
    monkeypatch.setattr(app.state, "session_factory", maker, raising=False)
    seen = {}

    async def _initiate(session, payment, source, **kwargs):
        seen["payment"] = payment
        seen["source"] = source
        seen["kwargs"] = kwargs
        payment.gateway = "moyasar"
        payment.gateway_payment_id = "inv_probe"
        payment.gateway_source = "invoice"
        await session.commit()
        return {
            "id": "inv_probe",
            "checkout_url": "https://checkout.moyasar.com/invoices/inv_probe?lang=ar",
        }

    monkeypatch.setattr(pm, "initiate_moyasar", _initiate)
    async with _client(app) as client:
        response = await client.post(PATH, params={"token": TOKEN})
    assert response.status_code == 303, response.text
    assert response.headers["location"] == "https://checkout.moyasar.com/invoices/inv_probe?lang=ar"
    assert TOKEN not in response.headers["location"]
    assert response.headers["referrer-policy"] == "no-referrer"
    payment = seen["payment"]
    assert payment.amount == 100
    assert payment.total_halalas == 100
    assert payment.description == "دفعة تجريبية – النرجس"
    assert payment.package == pm.MOYASAR_LIVE_TEST_PACKAGE
    assert payment.project_id is None and payment.lead_id is None
    assert payment.customer_phone is None
    assert seen["kwargs"]["callback_url"].endswith("/webhooks/moyasar")
    assert seen["kwargs"]["success_url"].startswith("http")
    assert "/payment/moyasar-live-test/result?" in seen["kwargs"]["success_url"]
    assert "token=" not in seen["kwargs"]["success_url"]
    assert TOKEN not in seen["kwargs"]["success_url"]
    assert seen["source"]["type"] == "creditcard"


async def test_paid_probe_does_not_activate_a_matching_project(maker):
    from src.main import _apply_paid_outcome

    async with maker() as session:
        project = ClientProject(
            client_name="probe",
            phone="0550000099",
            package=pm.MOYASAR_LIVE_TEST_PACKAGE,
            status="pending",
        )
        real_plan = ClientProject(
            client_name="real",
            phone="0550000099",
            package="bidaya",
            status="pending",
        )
        session.add(project)
        session.add(real_plan)
        payment = await pm.create_moyasar_live_test_payment(session)
        payment.status = "paid"
        payment.customer_phone = project.phone
        await session.commit()
        activation = await pm.activate_subscription(session, payment)
        outcome = await _apply_paid_outcome(session, payment.id, note="probe")
        await session.refresh(project)
        await session.refresh(real_plan)
        await session.refresh(payment)
    assert activation == {"activated": False, "reason": "live test payment"}
    assert outcome["activated"] is False
    assert outcome["reason"] == "live test payment"
    assert project.status == "pending"
    assert project.last_payment_id is None
    assert real_plan.status == "pending"
    assert real_plan.last_payment_id is None
    assert payment.status == "paid"


async def test_webhook_can_mark_the_probe_paid_without_a_subscription(monkeypatch, maker):
    from src.main import app

    _live(monkeypatch)
    probe_secret = "whsec_probe_unit_not_a_real_secret"
    monkeypatch.setattr(get_settings(), "moyasar_webhook_secret", probe_secret)
    monkeypatch.setattr(app.state, "session_factory", maker, raising=False)
    async with maker() as session:
        project = ClientProject(
            client_name="probe",
            phone="0550000099",
            package=pm.MOYASAR_LIVE_TEST_PACKAGE,
            status="pending",
        )
        session.add(project)
        payment = await pm.create_moyasar_live_test_payment(session)
        payment.gateway = "moyasar"
        payment.gateway_payment_id = "inv_probe"
        payment.gateway_source = "invoice"
        payment.customer_phone = project.phone
        await session.commit()
        payment_id = payment.id
        project_id = project.id

    class _Resp:
        status_code = 200

        def json(self):
            return {
                "id": "inv_probe",
                "status": "paid",
                "amount": 100,
                "currency": "SAR",
                "source": {"type": "creditcard"},
            }

    real_client = httpx.AsyncClient

    class _Client(real_client):
        async def get(self, url, *args, **kwargs):
            if "api.moyasar.com" in str(url):
                return _Resp()
            return await super().get(url, *args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    async with _client(app) as client:
        response = await client.post(
            "/webhooks/moyasar",
            json={
                "type": "payment_paid",
                "secret_token": probe_secret,
                "data": {
                    "status": "paid",
                    "amount": 1,
                    "currency": "USD",
                    "metadata": {"order_id": str(payment_id)},
                },
            },
        )
    assert response.status_code == 200, response.text
    async with maker() as session:
        payment = await session.get(pm.Payment, payment_id)
        project = await session.get(ClientProject, project_id)
    assert payment.status == "paid"
    assert project.status == "pending"
    assert project.last_payment_id is None


async def test_result_page_confirms_payment_and_hides_the_token(monkeypatch, maker):
    from src.main import app

    _token(monkeypatch, TOKEN)
    monkeypatch.setattr(app.state, "session_factory", maker, raising=False)
    async with maker() as session:
        payment = await pm.create_moyasar_live_test_payment(session)
        payment.status = "paid"
        await session.commit()
        payment_id = payment.id
    pt = make_payment_token(payment_id)
    async with _client(app) as client:
        missing = await client.get(f"{PATH}/result", params={"id": str(payment_id)})
        shown = await client.get(f"{PATH}/result", params={"id": str(payment_id), "pt": pt})
    assert missing.status_code == 404
    assert shown.status_code == 200, shown.text
    assert "لم يُنشأ اشتراك" in shown.text
    assert 'content="noindex, nofollow"' in shown.text
    assert TOKEN not in shown.text
    assert str(payment_id) in shown.text
