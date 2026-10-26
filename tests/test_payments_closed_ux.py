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


def test_flag_follows_moyasar_hold(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "moyasar_api_secret", "sk_" + "live_FAKE")
    monkeypatch.setattr(s, "moyasar_publishable_key", "pk_" + "live_FAKE")
    assert pm.payments_open() is False  # MOYASAR_ON_HOLD keeps it closed
    monkeypatch.setattr(pm, "MOYASAR_ON_HOLD", False)
    assert pm.payments_open() is True
