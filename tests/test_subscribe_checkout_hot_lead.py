"""Subscribe buttons open the existing checkout step, and a hot lead alerts the owner.

No gateway is called. Prices stay the catalog figures with VAT off by default.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from src.services import catalog, ceo_advisor, hot_lead, payments
from src.services.checkout_link import subscribe_path


def _open_payments(monkeypatch) -> None:
    from src.main import templates

    monkeypatch.setattr(payments, "payments_open", lambda: True)
    monkeypatch.setitem(templates.env.globals, "payments_open", lambda: True)


def test_catalog_prices_stay_final_without_a_code_change() -> None:
    assert {key: catalog.PACKAGES[key]["amount"] for key in catalog.PACKAGE_ORDER} == {
        "bidaya": 79000,
        "numuw": 149000,
        "sharikat": 299000,
    }
    assert [catalog.PACKAGES[key]["price"] for key in catalog.PACKAGE_ORDER] == ["790", "1490", "2990"]


def test_subscribe_path_adds_checkout_only_while_payments_are_open(monkeypatch) -> None:
    monkeypatch.setattr(payments, "payments_open", lambda: False)
    closed = {key: subscribe_path(key) for key in catalog.PACKAGE_ORDER}
    assert closed == {
        "bidaya": "/portal?pkg=bidaya",
        "numuw": "/portal?pkg=numuw",
        "sharikat": "/portal?pkg=sharikat",
    }
    annual = subscribe_path("numuw", billing="annual")
    assert annual == "/portal?pkg=numuw&billing=annual"
    monkeypatch.setattr(payments, "payments_open", lambda: True)
    assert subscribe_path("bidaya") == "/portal?pkg=bidaya&checkout=1"
    assert subscribe_path("numuw", billing="annual") == "/portal?pkg=numuw&billing=annual&checkout=1"
    assert subscribe_path("sharikat", addons=1, agents=["content_writer"]) == (
        "/portal?pkg=sharikat&agents=content_writer&addons=1&checkout=1"
    )


def test_plan_buttons_point_at_checkout_for_each_plan(monkeypatch) -> None:
    _open_payments(monkeypatch)
    from src.main import app

    with TestClient(app) as client:
        home = client.get("/home").text
        pricing = client.get("/pricing").text
    for key, shown in (("bidaya", "790"), ("numuw", "1,490"), ("sharikat", "2,990")):
        monthly = f"/portal?pkg={key}&amp;checkout=1"
        annual = f"/portal?pkg={key}&amp;billing=annual&amp;checkout=1"
        assert monthly in home and monthly in pricing
        assert annual in home
        assert shown in home
    assert "اشترك في" in home
    assert 'id="ceoSubscribe"' in home and "checkout=1" in home


def test_interest_links_stay_on_the_portal_while_payments_are_closed() -> None:
    from src.main import app

    with TestClient(app) as client:
        page = client.get("/pricing").text
    assert payments.payments_open() is False
    assert "checkout=1" not in page
    for key in catalog.PACKAGE_ORDER:
        assert f'href="/portal?pkg={key}"' in page


def test_portal_checkout_step_is_the_destination() -> None:
    from src.main import app

    with TestClient(app) as client:
        page = client.get("/portal?pkg=numuw&checkout=1").text
    assert 'id="step-checkout"' in page
    assert 'id="coIdentity"' in page
    assert "directCheckout" in page
    assert "أدخل الاسم والجوال لإتمام الدفع لهذه الباقة." in page


def test_ceo_subscribe_uses_the_same_checkout_link(monkeypatch) -> None:
    monkeypatch.setattr(payments, "payments_open", lambda: True)
    result = ceo_advisor.build_result(ceo_advisor.diagnose_rules("متجري على زد والردود تتأخر"))
    assert result["cta"]["subscribe"].startswith(f"/portal?pkg={result['plan']['key']}")
    assert result["cta"]["subscribe"].endswith("&checkout=1") or result["cta"]["subscribe"].endswith("checkout=1")


def test_consult_whatsapp_opens_the_published_number() -> None:
    from urllib.parse import unquote

    from src.main import app

    with TestClient(app) as client:
        page = client.get("/consult").text
    assert page.count("https://wa.me/966552978753?text=") >= 2
    assert "السلام عليكم، أبغى استشارة عن النرجس" in page
    assert unquote(page).count("السلام عليكم، أبغى استشارة عن النرجس") >= 2
    assert 'id="consultWhatsapp"' in page
    assert "/api/hot-leads" in page
    lowered = page.lower()
    for banned in ("purple", "violet", "pink", "#ff69b4", "#7a5cb8", "🌸", "🌷", "🌼"):
        assert banned not in lowered


def test_stamp_hot_sets_priority_and_leaves_status() -> None:
    hot_lead._recent.clear()
    lead = SimpleNamespace(
        id="lead-1",
        opt_out=False,
        lead_status="CONTACTED",
        priority="LOW",
        priority_score=12,
        priority_reason=["ملف مكتمل"],
        buying_signal=False,
        contact_name="نورة",
        company_name="متجر",
        phone="0550000000",
        email="n@example.com",
        source="website",
    )
    text = hot_lead.stamp_hot(lead, "trial", excerpt="أبغى تجربة ١٥ دقيقة")
    assert lead.lead_status == "CONTACTED"
    assert lead.priority == "HIGH"
    assert lead.priority_score == 90
    assert lead.buying_signal is True
    assert "ساخن: طلب تجربة ١٥ دقيقة" in lead.priority_reason
    assert text and "نورة" in text and "تجربة" in text
    assert hot_lead.stamp_hot(lead, "trial", excerpt="مرة ثانية") is None
    assert lead.lead_status == "CONTACTED"

    reply = SimpleNamespace(
        id="lead-2",
        opt_out=False,
        lead_status="NEW",
        priority="LOW",
        priority_score=0,
        priority_reason=[],
        buying_signal=False,
        contact_name="خالد",
        company_name="خالد",
        phone=None,
        email=None,
        source="whatsapp_inbound",
    )
    alert = hot_lead.stamp_hot(reply, "reply", excerpt="تمام أبغى التفاصيل")
    assert reply.lead_status == "NEW"
    assert reply.priority == "HIGH"
    assert reply.buying_signal is False
    assert alert and "ردّ" in alert

    opted = SimpleNamespace(
        id="lead-3", opt_out=True, lead_status="DO_NOT_CONTACT", priority="LOW",
        priority_score=0, priority_reason=[], buying_signal=False,
    )
    assert hot_lead.stamp_hot(opted, "reply", excerpt="لا") is None
    assert opted.priority == "LOW"


@pytest.mark.asyncio
async def test_deliver_alert_respects_the_flag(monkeypatch) -> None:
    monkeypatch.setenv("HOT_LEAD_ALERTS", "0")
    assert await hot_lead.deliver_alert("🔥 عميل ساخن") == {"ok": False, "skipped": True}
    monkeypatch.setenv("HOT_LEAD_ALERTS", "1")
    seen: list[str] = []

    async def fake(text: str) -> dict:
        seen.append(text)
        return {"ok": True}

    monkeypatch.setattr("src.services.telegram_sender.send_owner_alert", fake)
    result = await hot_lead.deliver_alert("🔥 عميل ساخن — النرجس")
    assert result["channel"] == "telegram"
    assert seen == ["🔥 عميل ساخن — النرجس"]


async def test_whatsapp_click_alerts_without_inventing_a_lead(monkeypatch) -> None:
    import httpx
    from sqlalchemy import func
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from src.db.session import Base
    from src.main import app
    from src.models import AcquisitionLead

    seen: list[str] = []

    async def fake(text: str) -> dict:
        seen.append(text)
        return {"ok": True, "channel": "telegram"}

    monkeypatch.setattr(hot_lead, "deliver_alert", fake)
    hot_lead._public_signals = None
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    previous = app.state.session_factory
    app.state.session_factory = maker
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/hot-leads", json={
                "kind": "whatsapp_click",
                "page": "/consult",
                "message": "السلام عليكم، أبغى استشارة عن النرجس",
            })
        async with maker() as session:
            count = (await session.execute(select(func.count()).select_from(AcquisitionLead))).scalar_one()
    finally:
        app.state.session_factory = previous
        await engine.dispose()
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True and body["alerted"] is True and body["lead_id"] is None
    assert count == 0
    assert seen and "واتساب" in seen[0] and "لم يُنشأ سجل عميل" in seen[0]


async def test_trial_request_on_the_site_form_marks_the_lead(monkeypatch) -> None:
    import httpx
    from uuid import UUID
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from src.db.session import Base
    from src.main import app
    from src.models import AcquisitionLead

    async def fake(*_args, **_kwargs) -> dict:
        return {"ok": True, "channel": "telegram"}

    monkeypatch.setattr(hot_lead, "deliver_alert", fake)
    monkeypatch.setattr("src.services.telegram_sender.send_owner_alert", fake)
    monkeypatch.setattr("src.services.email_service.send_welcome", fake)
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    previous = app.state.session_factory
    app.state.session_factory = maker
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/leads", json={
                "name": "مؤسسة السهل",
                "phone": "0553078711",
                "email": "sahla@example.com",
                "message": "أبغى تجربة ١٥ دقيقة",
            })
        assert response.status_code == 200
        payload = response.json()
        assert payload["hot"] is True
        async with maker() as session:
            lead = (
                await session.execute(select(AcquisitionLead).where(AcquisitionLead.id == UUID(payload["lead_id"])))
            ).scalar_one()
    finally:
        app.state.session_factory = previous
        await engine.dispose()
    assert lead.lead_status == "NEW"
    assert lead.priority == "HIGH"
    assert lead.priority_score >= 90
    assert any("تجربة" in reason for reason in (lead.priority_reason or []))
    assert lead.company_name == "مؤسسة السهل"
