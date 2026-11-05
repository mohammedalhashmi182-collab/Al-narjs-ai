"""Pricing and portal follow the published payment method.

With the Al Rajhi account in content/transfer.json, bank transfer is a real
checkout option. The closed banner remains only when no method can take money.
"""

import httpx
import pytest

from src.config.settings import get_settings
from src.services import payments as pm

AR = "الدفع الإلكتروني قيد التفعيل حالياً. سجّل اهتمامك الآن ونتواصل معك بالبريد الإلكتروني عند فتح الدفع."
EN = "Online payment is not open yet."
TRANSFER_AR = "الدفع المتاح: تحويل بنكي."
TRANSFER_EN = "Payment available: bank transfer."


async def _get(path):
    from src.main import app

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", follow_redirects=True
    ) as client:
        r = await client.get(path)
    assert r.status_code == 200, (path, r.status_code)
    return r.text


@pytest.mark.parametrize(
    "path,note,cta,closed_cta",
    [
        ("/ar/pricing", TRANSFER_AR, "اشترك في ", "سجّل اهتمامك"),
        ("/en/pricing", TRANSFER_EN, ">Get ", "Register interest"),
    ],
)
async def test_pricing_offers_bank_transfer_instead_of_interest_only(path, note, cta, closed_cta):
    assert pm.payments_open()
    assert pm.capabilities()["card"] is False
    assert pm.capabilities()["invoice"] is True
    html = await _get(path)
    assert note in html
    assert 'id="bankTransferNote"' in html
    assert 'id="paymentsClosedBanner"' not in html
    assert cta in html
    assert closed_cta not in html


@pytest.mark.parametrize(
    "path,cta,absent",
    [
        ("/ar/portal", "ادفع بتحويل بنكي", "سجّل اهتمامك"),
        ("/en/portal", "Pay by bank transfer", "Register interest"),
    ],
)
async def test_portal_offers_bank_transfer_and_no_instant_promise(path, cta, absent):
    html = await _get(path)
    assert 'id="paymentsClosedBanner"' not in html
    assert cta in html
    assert absent not in html
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


async def test_banner_returns_when_no_payment_method_is_open(monkeypatch):
    monkeypatch.setattr(pm, "payments_open", lambda: False)
    from src.main import templates

    monkeypatch.setitem(templates.env.globals, "payments_open", lambda: False)
    html = await _get("/ar/pricing")
    assert 'id="paymentsClosedBanner"' in html
    assert AR in html
    assert "سجّل اهتمامك" in html


def test_payments_open_follows_paypal_or_published_bank_transfer(monkeypatch, tmp_path):
    from src.services import transfer as t

    monkeypatch.delenv("CUSTOMER_PAYPAL_ENABLED", raising=False)
    for key in ("PAYMENT_IBAN", "PAYMENT_ACCOUNT_NAME", "PAYMENT_BANK_NAME"):
        monkeypatch.delenv(key, raising=False)
    empty = tmp_path / "transfer.json"
    empty.write_text('{"bank_name":"","account_name":"","iban":"","swift":""}', encoding="utf-8")
    monkeypatch.setattr(t, "CONTENT_FILE", empty)
    cached = get_settings()
    monkeypatch.setattr(cached, "paypal_client_id", "id")
    monkeypatch.setattr(cached, "paypal_client_secret", "secret")
    monkeypatch.setattr(cached, "paypal_mode", "live")
    assert pm.payments_open() is False
    monkeypatch.setenv("CUSTOMER_PAYPAL_ENABLED", "1")
    assert pm.payments_open() is True
    monkeypatch.delenv("CUSTOMER_PAYPAL_ENABLED", raising=False)
    published = tmp_path / "published.json"
    published.write_text(
        '{"bank_name":"مصرف الراجحي","account_name":"Holder","iban":"SA5880000126608016363961","swift":"RJHISARI"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(t, "CONTENT_FILE", published)
    assert pm.customer_bank_transfer_enabled() is True
    assert pm.payments_open() is True
    assert pm.capabilities()["card"] is False
