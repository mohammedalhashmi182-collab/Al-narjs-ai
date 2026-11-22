"""Owner rule: the public site never announces a payment status.

The old black banner («الدفع الإلكتروني قيد التفعيل حالياً…» / "Online payment is
not open yet…") and its "register interest" wording must never render again, in
any state: payments on or off, Arabic or English, monthly or annual, home,
pricing, portal or the CEO answer. While checkout is off, plan buttons open the
plan request form on /portal (no checkout flag); when it is on, they open checkout.
"""

from pathlib import Path

import httpx
import pytest

from src.services import payments as pm

ROOT = Path(__file__).resolve().parents[1]

BANNED = (
    "قيد التفعيل",
    "سجّل اهتمامك",
    "سجل اهتمامك",
    "عند فتح الدفع",
    "Online payment is not open yet",
    "not open yet",
    "Register interest",
    "Register your interest",
    "register your interest",
    "when payment opens",
    "being activated",
    "paymentsClosedBanner",
    "payments-closed-banner",
)
PAGES = ("/ar/home", "/en/home", "/ar/pricing", "/en/pricing", "/ar/portal", "/en/portal")
CARD_AR = "الدفع المتاح: مدى أو فيزا أو ماستركارد"
CARD_EN = "Payment available: mada, Visa, or Mastercard"


async def _get(path):
    from src.main import app

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", follow_redirects=True
    ) as client:
        r = await client.get(path)
    assert r.status_code == 200, (path, r.status_code)
    return r.text


def _force(monkeypatch, open_: bool):
    from src.main import templates

    monkeypatch.setattr(pm, "payments_open", lambda: open_)
    monkeypatch.setitem(templates.env.globals, "payments_open", lambda: open_)


def _assert_clean(html, where):
    for bad in BANNED:
        assert bad not in html, (where, bad)


@pytest.mark.parametrize("open_", [False, True])
@pytest.mark.parametrize("path", PAGES)
async def test_payment_status_banner_never_renders(monkeypatch, path, open_):
    _force(monkeypatch, open_)
    html = await _get(path)
    _assert_clean(html, (path, open_))
    # annual tab is the same markup, swapped client-side: check both query states too
    html = await _get(path + "?billing=annual")
    _assert_clean(html, (path, "annual", open_))


async def test_default_state_is_closed_and_clean():
    assert pm.payments_open() is False
    for path in PAGES:
        _assert_clean(await _get(path), path)


def test_banner_partial_and_constants_are_gone():
    assert not (ROOT / "src/web/templates/partials/_payments_closed_banner.html").exists()
    assert not hasattr(pm, "PAYMENTS_CLOSED_AR") and not hasattr(pm, "PAYMENTS_CLOSED_EN")
    assert not hasattr(pm, "CARD_ACTIVATING_AR")
    for text in (pm.REQUEST_FOLLOWUP_AR, pm.REQUEST_FOLLOWUP_EN, pm.CHECKOUT_UNAVAILABLE_AR):
        _assert_clean(text, "constant")
        for bad in ("مجان", "free", "Free", "خصم", "discount", "VAT", "ضريبة"):
            assert bad not in text


def test_no_source_can_bring_the_banner_back():
    roots = [ROOT / "src", ROOT / "data" / "kb"]
    for base in roots:
        for f in base.rglob("*"):
            if f.suffix not in {".html", ".js", ".py", ".md", ".json", ".css", ".yaml", ".txt"}:
                continue
            text = f.read_text(encoding="utf-8", errors="ignore")
            for bad in ("قيد التفعيل", "سجّل اهتمامك", "Online payment is not open yet",
                        "Register interest", "عند فتح الدفع", "paymentsClosedBanner"):
                assert bad not in text, (str(f), bad)


async def test_closed_buttons_open_the_plan_request_form(monkeypatch):
    _force(monkeypatch, False)
    for path, label in (("/ar/pricing", "اطلب باقة"), ("/en/pricing", "Request ")):
        html = await _get(path)
        assert CARD_AR not in html and CARD_EN not in html
        assert "آيبان" not in html and "IBAN" not in html
        assert label in html
        assert 'href="/portal?pkg=bidaya"' in html
        assert 'data-href-annual="/portal?pkg=bidaya&amp;billing=annual"' in html
        assert "checkout=1" not in html
    for path, cta in (("/ar/portal", "أرسل طلبي"), ("/en/portal", "Send my request")):
        html = await _get(path)
        assert cta in html
        assert 'id="pendingCta"' not in html  # no dead "activate" button while checkout is off
        for bad in ("ادفع بتحويل بنكي", "Pay by bank transfer", "Pending / On Hold", "معلّق حالياً",
                    "serve you instantly", "خدمتك فوراً", "العمل لك فوراً",
                    "working for you instantly", "استقبل فريقي الذكي"):
            assert bad not in html, bad


async def test_open_buttons_still_go_to_checkout(monkeypatch):
    _force(monkeypatch, True)
    html = await _get("/ar/pricing")
    assert "checkout=1" in html and "اشترك في" in html
    portal = await _get("/ar/portal")
    assert 'id="pendingCta"' in portal


def test_ceo_pay_now_answer_has_no_status_wording(monkeypatch):
    from src.services import ceo_advisor

    monkeypatch.setattr(pm, "payments_open", lambda: False)
    r = ceo_advisor.public_output_check(
        {"diagnosis_ar": "x", "diagnosis_en": "x", "agents": [], "cta": {"subscribe": "/portal"}},
        "I want to pay by credit card right now, send me the payment link",
    )
    for key in ("diagnosis_ar", "diagnosis_en"):
        _assert_clean(r[key], key)
    assert r["diagnosis_ar"].startswith(pm.REQUEST_FOLLOWUP_AR)


def test_payments_open_follows_paypal_or_published_bank_transfer(monkeypatch, tmp_path):
    from src.config.settings import get_settings
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
    assert pm.customer_bank_transfer_enabled() is False
    assert pm.payments_open() is False
    assert pm.capabilities()["card"] is False
