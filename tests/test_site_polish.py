"""Site polish (Oct 2026): pages, headers, language, consent, contact policy."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("path", ["/refund-policy", "/about", "/pricing", "/contact", "/home"])
def test_unprefixed_public_pages_redirect_to_arabic(client, path):
    r = client.get(path, follow_redirects=False)
    assert r.status_code == 301, path
    assert r.headers["location"] == f"/ar{path}", path


@pytest.mark.parametrize("path", ["/en/refund-policy", "/en/about", "/en/pricing", "/ar/contact", "/ar/home"])
def test_prefixed_public_pages_render(client, path):
    r = client.get(path, follow_redirects=False)
    assert r.status_code == 200, path


def test_pricing_is_a_real_page_with_plans_and_meta(client):
    from src.services import catalog

    html = client.get("/en/pricing").text
    assert '<meta name="description"' in html and "application/ld+json" in html
    for key in catalog.PACKAGE_ORDER:
        assert catalog.PACKAGES[key]["name_en"] in html
    assert "setup fee" in html.lower()
    assert "By quote" not in html


def test_refund_policy_quotes_the_terms_and_is_linked(client):
    from src.services import policies

    html = client.get("/ar/refund-policy").text
    assert policies.REFUND_CONSENT_AR in html
    assert "لا نعد هنا بنتيجة استرداد" in html
    assert 'href="/refund-policy"' in client.get("/terms").text
    assert 'href="/refund-policy"' in client.get("/home").text


def test_about_has_operator_facts_and_no_invented_testimonials(client):
    html = client.get("/ar/about").text
    assert "FL-272182297" in html and "منصة النرجس" in html and "المؤسس: كريم" in html and "محمد" not in html
    assert "Founder: Karim" in client.get("/en/about").text
    assert "testimonials" not in html  # empty list -> no section


def test_testimonials_only_load_approved_real_entries(tmp_path):
    from src.services import testimonials

    f = tmp_path / "t.json"
    f.write_text('[{"name":"A","quote":"q","approved":true},{"name":"B","quote":"q"},{"name":"","quote":"q","approved":true}]', encoding="utf-8")
    assert [t["name"] for t in testimonials.load(f)] == ["A"]
    assert testimonials.load() == []


def test_root_is_a_permanent_redirect_and_favicon_exists(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 301 and r.headers["location"].endswith("/home")
    assert client.get("/favicon.ico").status_code == 200


def test_security_headers(client):
    h = client.get("/home").headers
    assert "max-age=" in h["strict-transport-security"]
    csp = h["content-security-policy"]
    for needle in ("frame-ancestors 'none'", "connect.facebook.net", "fonts.googleapis.com", "paypal.com"):
        assert needle in csp
    assert h["x-content-type-options"] == "nosniff"
    assert h["referrer-policy"]


def test_english_home_is_english(client):
    html = client.get("/en/home").text
    assert '<html lang="en" dir="ltr">' in html
    assert "رئيسك التنفيذي الذكي" not in html
    h1 = re.search(r"<h1>(.*?)</h1>", html).group(1)
    assert h1 == "Al-Narjis — AI solutions and business automation in Saudi Arabia"
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        assert not re.search(r"[\u0600-\u06FF]", block), block[:120]


def test_arabic_home_has_no_english_ceo_mixing(client):
    html = client.get("/ar/home").text
    assert "Your AI CEO" not in html and "الـ CEO" not in html


def test_logo_images_have_alt_text(client):
    html = client.get("/home").text
    for tag in re.findall(r'<img[^>]+logo\.png[^>]*>', html):
        assert re.search(r'alt="[^"]+"', tag), tag


def test_hidden_bilingual_spans_carry_their_own_lang():
    from pathlib import Path

    for p in Path("src/web/templates").rglob("*.html"):
        for tag in re.findall(r'<[a-z0-9]+[^<>]*\sdata-lang="(?:ar|en)"[^<>]*>', p.read_text(encoding="utf-8")):
            if tag.startswith(("<html", "<body")):
                continue
            assert " lang=" in tag, (p, tag)


def test_consult_does_not_load_the_tailwind_cdn(client):
    html = client.get("/consult").text
    assert "cdn.tailwindcss.com" not in html and "/static/css/consult-tw.css" in html


def test_trackers_wait_for_consent(client, monkeypatch):
    from src.main import templates

    monkeypatch.setattr(templates.env.globals["settings"], "meta_pixel_id", "1234567890123")
    html = client.get("/home").text
    assert "narjs_consent" in html and "cookieAccept" in html
    # the pixel bootstrap sits inside load(), which only runs on granted consent
    load = html[html.index("function load()"):html.index("window.narjsConsent")]
    assert "fbevents.js" in load
    assert "<noscript><img" not in html


def test_plan_wording(client):
    from src.services import catalog

    for pkg in catalog.PACKAGES.values():
        lines = pkg["scope"] + pkg["coming"]
        assert not any("ميسّر" in line or "ميسر" in line for line in lines)
        assert not any("تيليجرام" in line or "ماسنجر" in line for line in lines)
        assert not any("SLA" in line or "WhatsApp" in line for line in pkg["scope"])


def test_support_handoff_is_the_company_phone():
    from src.services.support import support_contact

    contact = support_contact()
    assert contact["channel"] == "call"
    assert contact["href"] == "tel:+966540799266"
    assert contact["value"] == "0540799266"
    assert contact["email"] == "AlNarjisai@gmail.com"


def test_assistant_offers_customer_service_handoff(client):
    html = client.get("/ar/home").text
    # Public pages no longer carry a phone hand-off; the assistant's staff ticket does.
    assert 'id="saHandoff"' not in html and "tel:" not in html
    assert 'id="siteAssistant"' not in html
