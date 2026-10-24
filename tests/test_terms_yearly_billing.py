"""Terms state yearly billing (pay 10 months, get 12) and the setup fee on both cycles."""
import httpx

from src.main import app


async def _get(path):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                                 follow_redirects=True) as c:
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
