"""Realistic simulations must remain disclosed, isolated and accessible."""

import json
from html import escape
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from src.main import app, templates
from src.services import public_presence, seo

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_tour_is_public_localized_and_disclosed(lang):
    with TestClient(app) as client:
        r = client.get("/" + lang + "/tour")
    assert r.status_code == 200
    assert ("محاكاة افتراضية" if lang == "ar" else "Fictional simulation") in r.text
    assert ("الحوارات معدّة مسبقاً" if lang == "ar" else "Scripted conversations") in r.text
    assert "narjis-tour-60s.mp4" in r.text
    assert r.text.count("data-tour-step=") == 6
    assert '<track kind="captions"' in r.text
    assert seo.is_public_path("/" + lang + "/tour")


def test_tour_never_calls_business_or_payment_apis():
    script = (ROOT / "src/web/static/js/narjis-tour.js").read_text()
    for forbidden in ("fetch(", "XMLHttpRequest", "/api/", "innerHTML", "setInterval"):
        assert forbidden not in script
    assert "textContent" in script


def test_contact_uses_configured_business_number_and_rejects_invalid(monkeypatch):
    settings = public_presence.get_settings()
    monkeypatch.setattr(settings, "whatsapp_business_number", "0540799266")
    assert public_presence.presence()["whatsapp"].startswith("https://wa.me/966540799266?")
    monkeypatch.setattr(settings, "whatsapp_business_number", "javascript:alert(1)")
    assert public_presence.presence()["whatsapp"] == ""
    with TestClient(app) as client:
        assert 'class="nj-whatsapp-contact"' not in client.get("/ar/tour").text


def test_no_social_or_portrait_without_owner_evidence(tmp_path, monkeypatch):
    path = tmp_path / "identity.json"
    monkeypatch.setattr(public_presence, "_PATH", path)
    path.write_text(
        json.dumps(
            {
                "social_links": [
                    {
                        "label": "Fake",
                        "url": "https://instagram.com/example",
                        "owner_verified": False,
                    },
                    {
                        "label": "Unsafe",
                        "url": "https://instagram.com.evil.example/path",
                        "owner_verified": True,
                    },
                    {"label": "Unsafe", "url": "javascript:alert(1)", "owner_verified": True},
                    {
                        "label": "Profile",
                        "url": "https://linkedin.com/company/example",
                        "owner_verified": True,
                    },
                ],
                "founder_portrait": {"filename": "../other.png", "owner_approved": True},
            }
        )
    )
    data = public_presence.presence()
    assert data["social_links"] == [
        {"label": "Profile", "url": "https://linkedin.com/company/example"}
    ]
    assert data["founder_photo"] is None


def test_home_exposes_resources_tour_and_valid_whatsapp():
    with TestClient(app) as client:
        page = client.get("/ar/home").text
    assert 'id="resources"' in page
    assert 'href="/tour"' in page
    assert escape(public_presence.presence()["whatsapp"], quote=True) in page
    assert 'href="/sitemap.xml"' in page
    assert "تجربة افتراضية" in page or "محاكاة افتراضية" in page


def test_subscribe_cta_follows_live_capability_without_opening_payments(monkeypatch):
    with TestClient(app) as client:
        monkeypatch.setitem(templates.env.globals, "payments_open", lambda: False)
        closed = client.get("/ar/pricing").text
        assert "سجّل اهتمامك" in closed
        assert "اشترك الآن" not in closed
        monkeypatch.setitem(templates.env.globals, "payments_open", lambda: True)
        opened = client.get("/ar/pricing").text
        assert "اشترك الآن" in opened
        assert 'id="paymentsClosedBanner"' not in opened
