"""While payments are closed, pricing and portal say so plainly and invite interest only."""

import httpx
import pytest

from src.config.settings import get_settings
from src.services import payments as pm

AR = "الدفع الإلكتروني قيد التفعيل حالياً. سجّل اهتمامك الآن ونتواصل معك بالبريد الإلكتروني عند فتح الدفع."
EN = "Online payment is not open yet."


async def _get(path):
    from src.main import app

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", follow_redirects=True
    ) as client:
        r = await client.get(path)
    assert r.status_code == 200, (path, r.status_code)
    return r.text


@pytest.mark.parametrize(
    "path,banner,cta,old_cta",
    [
        ("/ar/pricing", AR, "سجّل اهتمامك", "اشترك في "),
        ("/en/pricing", EN, "Register interest", ">Get "),
    ],
)
async def test_pricing_shows_closed_banner_above_plans(path, banner, cta, old_cta):
    assert not pm.payments_open()
    html = await _get(path)
    assert banner in html
    assert html.index('id="paymentsClosedBanner"') < html.index('class="plans"')
    assert cta in html
    assert old_cta not in html


@pytest.mark.parametrize(
    "path,banner,cta",
    [
        ("/ar/portal", AR, "سجّل اهتمامك"),
        ("/en/portal", EN, "Register interest"),
    ],
)
async def test_portal_shows_closed_banner_and_no_instant_promise(path, banner, cta):
    html = await _get(path)
    assert banner in html
    assert html.index('id="paymentsClosedBanner"') < html.index('id="pkg-grid"')
    assert cta in html
    for bad in (
        "Pending / On Hold",
        "معلّق حالياً",
        "serve you instantly",
        "خدمتك فوراً",
        "العمل لك فوراً",
        "working for you instantly",
        "استقبل فريقي الذكي",
    ):
        assert bad not in html, bad


async def test_banner_disappears_when_payments_open(monkeypatch):
    monkeypatch.setattr(pm, "payments_open", lambda: True)
    from src.main import templates

    monkeypatch.setitem(templates.env.globals, "payments_open", lambda: True)
    html = await _get("/ar/pricing")
    assert 'id="paymentsClosedBanner"' not in html
    assert "اشترك في " in html


def test_payments_open_follows_paypal_or_bank_transfer(monkeypatch):
    s = get_settings()
    monkeypatch.delenv("CUSTOMER_PAYPAL_ENABLED", raising=False)
    monkeypatch.delenv("CUSTOMER_BANK_TRANSFER_ENABLED", raising=False)
    monkeypatch.setattr(s, "paypal_client_id", "id")
    monkeypatch.setattr(s, "paypal_client_secret", "secret")
    monkeypatch.setattr(s, "paypal_mode", "live")
    assert pm.payments_open() is False
    monkeypatch.setenv("CUSTOMER_PAYPAL_ENABLED", "1")
    assert pm.payments_open() is True
    monkeypatch.delenv("CUSTOMER_PAYPAL_ENABLED", raising=False)
    monkeypatch.setenv("CUSTOMER_BANK_TRANSFER_ENABLED", "1")
    assert pm.payments_open() is True
