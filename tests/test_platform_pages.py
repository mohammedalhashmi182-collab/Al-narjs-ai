"""Public platform pages: docs, status, changelog, SLA, partnerships, signup."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.services import case_studies, catalog, sla
from src.services.public_status import status_host_home
from src.version import __version__

ARABIC = re.compile(r"[\u0600-\u06ff]")
DENIED = (
    "/api/owner",
    "/webhooks",
    "/health/deep",
    "moyasar-live-test",
    "/api/email",
    "/api/acquisition",
    "/api/company",
    "/api/governance",
    "/api/queue",
    "/api/schedules",
    "/api/executions",
    "/api/workflows",
    "/api/ceo/run",
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_version_is_1_0_0() -> None:
    assert __version__ == "1.0.0"


def _mounted_paths() -> set[str]:
    """Paths on the app, including routers FastAPI keeps nested."""
    found: set[str] = set()

    def walk(routes) -> None:
        for route in routes:
            path = getattr(route, "path", None)
            if isinstance(path, str):
                found.add(path)
            nested = getattr(route, "original_router", None)
            if nested is not None:
                walk(nested.routes)

    walk(app.routes)
    return found


def test_docs_excludes_sensitive_routes(client: TestClient) -> None:
    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    body = spec.json()
    assert body["info"]["title"] == "Al-Narjis AI Public API"
    assert body["info"]["version"] == "1.0.0"
    assert "portalSession" in body["components"]["securitySchemes"]
    scheme = body["components"]["securitySchemes"]["portalSession"]
    assert scheme["in"] == "cookie"
    assert scheme["name"] == "narjis_portal"
    paths = body["paths"]
    assert paths
    blob = " ".join(paths)
    text = spec.text
    for denied in DENIED:
        assert denied not in blob
    for needle in ("sk_live", "sk_test", "pk_live_", "whsec_", "BEGIN PRIVATE"):
        assert needle not in text
    app_paths = _mounted_paths()
    assert any(path.startswith("/api/owner") for path in app_paths)
    assert any("/webhooks/" in path for path in app_paths)
    assert "/payment/moyasar-live-test" in app_paths
    assert "/health/deep" in app_paths
    for published in paths:
        assert published in app_paths, published

    docs = client.get("/en/docs")
    assert docs.status_code == 200
    assert "/openapi.json" in docs.text
    assert "swagger-ui" in docs.text
    for denied in ("/api/owner", "/webhooks/moyasar", "moyasar-live-test", "/health/deep"):
        assert denied not in docs.text
    redoc = client.get("/redoc")
    assert redoc.status_code == 200
    assert "redoc" in redoc.text.lower()


def test_status_json_is_cached_and_quiet(client: TestClient) -> None:
    response = client.get("/api/status")
    assert response.status_code == 200
    assert "max-age=30" in response.headers["cache-control"]
    body = response.json()
    assert body["version"] == "1.0.0"
    assert body["status"] in {"operational", "degraded", "outage"}
    assert set(body["components"]) == {"site", "health", "portal", "agents"}
    assert body["components"]["agents"]["count"] == catalog.AGENT_COUNT == 39
    lowered = response.text.lower()
    for banned in ("sk_live", "sk_test", "password", "traceback", "database_url", "secret"):
        assert banned not in lowered
    page = client.get("/en/status")
    assert page.status_code == 200
    assert 'rel="canonical"' in page.text
    assert 'hreflang="ar"' in page.text and 'hreflang="en"' in page.text
    assert "max-age=30" in page.headers["cache-control"]
    arabic = client.get("/ar/status")
    assert 'lang="ar"' in arabic.text and 'dir="rtl"' in arabic.text


def test_status_host_root_opens_the_status_page() -> None:
    assert status_host_home("status.karmaai.online", "/") == "/ar/status"
    assert status_host_home("status.karmaai.online", "/en") == "/en/status"
    assert status_host_home("status.karmaai.online", "/ar/home") is None
    assert status_host_home("karmaai.online", "/") is None


def test_changelog_matches_history(client: TestClient) -> None:
    page = client.get("/en/changelog")
    assert page.status_code == 200
    for phrase in ("Moyasar", "39", "service pages", "llms.txt"):
        assert phrase in page.text
    arabic = client.get("/ar/changelog")
    assert "Moyasar" in arabic.text
    assert "39" in arabic.text
    notes = Path("CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [1.0.0] - 2026-11-12" in notes
    assert "Keep a Changelog" in notes
    for phrase in ("Moyasar", "39 agents", "service pages"):
        assert phrase in notes


def test_sla_is_marked_for_owner_review(client: TestClient) -> None:
    assert sla.OWNER_REVIEW_REQUIRED is True
    assert sla.UPTIME_PERCENT == "99.5"
    page = client.get("/en/sla")
    assert page.status_code == 200
    assert 'data-sla-review="required"' in page.text
    assert "Draft for review" in page.text
    assert "99.5" in page.text
    for price in ("790", "1,490", "2,990"):
        assert price in page.text
    assert "8 business hours" in page.text
    assert "10%" in page.text and "25%" in page.text and "50%" in page.text
    arabic = client.get("/ar/sla")
    assert "مسودة للمراجعة" in arabic.text
    assert "99.5" in arabic.text


def test_partnerships_do_not_claim_unreleased_integrations(client: TestClient) -> None:
    page = client.get("/en/partnerships")
    assert page.status_code == 200
    html = page.text
    assert html.count('data-status="in_development"') == 3
    for name in ("Salla", "Zid", "WhatsApp"):
        assert name in html
    assert "In development" in html
    assert "cannot be connected" in html
    assert "4,900" in html and "1,490" in html
    assert "9,900" in html and "1,000" in html
    assert 'href="/contact"' in html
    assert "mailto:AlNarjisai@gmail.com" in html
    for banned in ("2024", "2025", "2026", "2027", "Q1", "Q2", "available today"):
        assert banned not in html
    # The in-development cards must not use the available badge.
    for card in re.findall(r'data-status="in_development".*?</article>', html, re.S):
        assert "Available" not in card
        assert "In development" in card
    arabic = client.get("/ar/partnerships")
    assert "قيد التطوير" in arabic.text
    assert "متاح" not in re.findall(
        r'data-status="in_development".*?</article>', arabic.text, re.S
    )[0]


def test_case_studies_and_testimonials_stay_hidden(client: TestClient, tmp_path) -> None:
    assert case_studies.load() == []
    for path in ("/en/home", "/en/about", "/ar/about"):
        html = client.get(path).text
        assert "case-studies" not in html
        assert 'class="testimonials"' not in html
    pending = tmp_path / "cases.json"
    pending.write_text(
        '[{"title":"Northwind","summary":"A story.","approved":false,"logo":"x"}]',
        encoding="utf-8",
    )
    assert case_studies.load(pending) == []
    pending.write_text(
        '[{"title":"Northwind","summary":"A story.","approved":true}]',
        encoding="utf-8",
    )
    loaded = case_studies.load(pending)
    assert loaded[0]["title"] == "Northwind"


@pytest.mark.parametrize(
    ("path", "suffix"),
    [
        ("/signup", "/portal"),
        ("/ar/signup", "/ar/portal"),
        ("/en/signup", "/en/portal"),
    ],
)
def test_signup_redirects_to_the_portal(client: TestClient, path: str, suffix: str) -> None:
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 301
    assert response.headers["location"].endswith(suffix)
    landed = client.get(path)
    assert landed.status_code == 200


def test_new_pages_are_in_the_sitemap_and_bilingual(client: TestClient) -> None:
    xml = client.get("/sitemap.xml").text
    pages = ("/status", "/changelog", "/sla", "/partnerships", "/docs")
    for path in pages:
        assert f"https://karmaai.online/ar{path}" in xml
        english = client.get("/en" + path)
        arabic = client.get("/ar" + path)
        assert english.status_code == arabic.status_code == 200
        assert 'hreflang="en"' in english.text and 'hreflang="ar"' in english.text
        assert 'lang="en"' in english.text and 'dir="ltr"' in english.text
        assert 'lang="ar"' in arabic.text and 'dir="rtl"' in arabic.text
        body = english.text.split("<body", 1)[1]
        body = re.sub(r"(?s)<(script|style).*?</\1>", " ", body)
        visible = re.sub(r"(?s)<[^>]+>", " ", body)
        # The language switch is the Arabic name of the other language.
        visible = visible.replace("العربية", "")
        assert not ARABIC.search(visible), path
    assert "/signup" not in xml


def test_footer_links_the_new_pages(client: TestClient) -> None:
    home = client.get("/en/home").text
    for href in ("/status", "/changelog", "/sla", "/partnerships", "/docs"):
        assert f'href="{href}"' in home
