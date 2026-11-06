"""Terms state yearly billing (pay 10 months, get 12) and the setup fee on both cycles."""

import re

import httpx
import pytest
from src.main import app


async def _get(path):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", follow_redirects=True
    ) as c:
        r = await c.get(path)
    assert r.status_code == 200
    return r.text


async def test_terms_ar_mentions_yearly():
    html = await _get("/ar/terms")
    assert "تدفع 10 أشهر وتحصل على 12 شهراً" in html
    assert "الشهري والسنوي على حدّ سواء" in html


async def test_terms_en_mentions_yearly():
    html = await _get("/en/terms")
    assert "pay for 10 months, get 12" in html
    assert "monthly and yearly billing alike" in html


@pytest.mark.parametrize("lang", ["ar", "en"])
@pytest.mark.parametrize("vat_rate", ["0", "0.15"])
async def test_terms_state_final_prices_without_vat(monkeypatch, lang, vat_rate) -> None:
    # Legal status is an owner decision, not a promise toggled by VAT_RATE.
    monkeypatch.setenv("VAT_RATE", vat_rate)
    html = await _get(f"/{lang}/terms")
    assert not re.search(r"(?:15|\u0661\u0665)\s*[%٪]", html)
    for claim in ("تُضاف ضريبة", "VAT (", "VAT is added to", "Simplified Tax Invoice"):
        assert claim not in html
    if lang == "ar":
        assert "الأسعار نهائية ولا تُضاف عليها ضريبة القيمة المضافة" in html
        assert "النرجس غير مسجّلة في ضريبة القيمة المضافة" in html
        assert "لا نصدر فواتير ضريبية" in html
        assert "نصدر فاتورة أو إيصال دفع بالمبلغ النهائي" in html
    else:
        assert "Prices are final and no VAT is added" in html
        assert "Al-Narjs is not VAT-registered" in html
        assert "we do not issue tax invoices" in html
        assert "we issue an invoice or payment receipt for the final amount" in html


@pytest.mark.parametrize("lang", ["ar", "en"])
@pytest.mark.parametrize("path", ["home", "pricing", "agents", "portal"])
async def test_related_public_pages_do_not_promise_vat(monkeypatch, lang, path) -> None:
    monkeypatch.setenv("VAT_RATE", "0")
    html = await _get(f"/{lang}/{path}")
    for claim in ("تُضاف ضريبة", "فاتورة ضريبية", "الفواتير الضريبية",
                  "فواتير ضريبية", "Tax invoices", "Tax invoice", "official VAT invoices",
                  "VAT is added at checkout", "Prices exclude", "قبل الضريبة"):
        assert claim not in html
    assert not re.search(r"(?:15|\u0661\u0665)\s*[%٪]", html)
