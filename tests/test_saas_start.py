"""Self-serve landing (/start): bilingual page, USD plans, live demo API."""
from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def client():
    from src.main import app

    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("lang,dir_,h1", [("ar", "rtl", "متجرك يبيع"), ("en", "ltr", "Your store sells")])
def test_start_page_renders_both_languages(client, lang, dir_, h1):
    r = client.get(f"/{lang}/start")
    assert r.status_code == 200
    html = r.text
    assert f'<html lang="{lang}" dir="{dir_}">' in html
    assert h1 in html
    assert 'hreflang="ar" href="https://alnarjisai.com/ar/start"' in html
    assert 'hreflang="en" href="https://alnarjisai.com/en/start"' in html
    assert f'rel="canonical" href="https://alnarjisai.com/{lang}/start"' in html
    assert 'id="demoForm"' in html and 'action="/api/demo/generate"' in html
    assert "/static/css/narjis-saas.css" in html and "/static/js/narjis-saas.js" in html
    assert 'href="#"' not in html
    for path in ("privacy", "data-deletion", "voice"):
        assert f"/{lang}/{path}" in html
    assert "mailto:AlNarjisai@gmail.com" in html
    assert "cdn.tailwindcss.com" not in html
    assert "cdn.paddle.com" not in html


def test_prices_come_from_the_catalog_in_sar(client):
    from src.services import saas_offer

    html = client.get("/en/start").text
    paid = [p for p in saas_offer.PLANS if p.monthly_sar]
    assert [p.monthly_sar for p in paid] == [79, 189, 489]
    assert [p.annual_total_sar for p in paid] == [758, 1814, 4694]  # 12 months at 20% off
    for p in paid:
        assert f'data-monthly="{p.monthly_sar}"' in html
        assert f'data-annual="{p.annual_monthly_sar}"' in html
    assert "SAR / month" in html


def test_paid_buttons_open_the_existing_moyasar_paypal_checkout(client):
    html = client.get("/ar/start").text
    for key in ("ss_starter", "ss_growth", "ss_pro"):
        assert f'href="/ar/portal?pkg={key}"' in html
        assert f'data-href-annual="/ar/portal?pkg={key}&amp;billing=annual"' in html
    assert "paddle" not in html.lower()


def test_self_serve_plans_are_billable_but_not_managed_tiers():
    from src.services import catalog, payments

    assert list(catalog.PACKAGES) == ["bidaya", "numuw", "sharikat"]
    for key in catalog.SELF_SERVE_ORDER:
        assert catalog.is_billable(key) and key not in catalog.PACKAGES
        assert catalog.setup_fee(key) == 0
    assert payments.package_amount("ss_growth") == 18900
    assert payments.package_amount("ss_growth", "annual") == 181400
    assert catalog.plan_limits("ss_pro")["conversations"] == 5000
    assert catalog.staff_team("ss_starter")[1:] == ["product_describer", "customer_service"]
    assert not catalog.is_billable("ss_unknown")


def test_portal_lists_self_serve_plans_only_on_request(client):
    managed = client.get("/api/portal/packages").json()["packages"]
    assert [p["key"] for p in managed] == ["bidaya", "numuw", "sharikat"]
    selfserve = client.get("/api/portal/packages?line=self").json()["packages"]
    assert [p["key"] for p in selfserve] == ["ss_starter", "ss_growth", "ss_pro"]
    assert selfserve[1]["annual_amount"] == 181400 and selfserve[1]["setup_fee"] == 0


def test_portal_can_create_a_self_serve_project(client):
    r = client.post("/api/portal/projects", json={
        "client_name": "Test Store", "phone": "0500000000", "email": "t@example.com", "package": "ss_starter",
    })
    assert r.status_code in (200, 201), r.text


@pytest.mark.parametrize("mode,name,details", [
    ("product", "Royal Oud", "long lasting, 100 ml"),
    ("reply", "Al-Ward", "Can it reach Riyadh today?"),
])
def test_demo_api_returns_text_without_a_model(client, mode, name, details):
    r = client.post("/api/demo/generate", json={"mode": mode, "name": name, "details": details, "lang": "en"})
    assert r.status_code == 200
    data = r.json()
    assert data["mode"] == mode and data["credits_used"] == 1
    assert data["text"].strip()
    assert "<" not in data["text"]


def test_demo_api_rejects_bad_input(client):
    assert client.post("/api/demo/generate", json={"mode": "hack", "name": "x", "details": "y"}).status_code == 400
    assert client.post("/api/demo/generate", json={"mode": "product", "name": "", "details": "y"}).status_code == 400


def test_demo_strips_markup_and_caps_length():
    from src.services import saas_offer

    mode, name, details = saas_offer.validate_demo("product", "<b>Oud</b>", "<script>x</script>" + "a" * 500)
    assert "<" not in name and "<" not in details
    assert len(details) <= saas_offer.MAX_FIELD
    out = asyncio.run(saas_offer.generate_demo(mode, name, details, lang="ar"))
    assert out["source"] == "template" and out["lang"] == "ar"


def test_start_is_in_the_sitemap(client):
    body = client.get("/sitemap.xml").text
    assert "https://alnarjisai.com/ar/start" in body or "https://alnarjisai.com/start" in body


def test_saas_script_parses_and_never_counts_credits_client_side():
    js = (ROOT / "src/web/static/js/narjis-saas.js").read_text(encoding="utf-8")
    assert "innerHTML" not in js
    assert "credits_used" not in js
    if shutil.which("node"):
        check = subprocess.run(["node", "--check", str(ROOT / "src/web/static/js/narjis-saas.js")],
                               capture_output=True, text=True, timeout=12, check=False)
        assert check.returncode == 0, check.stderr
