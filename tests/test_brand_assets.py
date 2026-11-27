"""New logo: brand assets exist, are served, and are wired into templates."""
import json
from http import HTTPStatus
from pathlib import Path
from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient
from src.main import app

STATIC = Path("src/web/static")


@pytest.fixture(scope="module")
def client():
    # Close the app so the background indexer does not keep the test database open.
    with TestClient(app) as c:
        yield c


def test_svg_brand_files_exist():
    for name in ("logo.svg", "logo-dark.svg", "favicon.svg"):
        body = (STATIC / name).read_text(encoding="utf-8")
        assert body.startswith("<svg") and "</svg>" in body


def test_raster_brand_routes(client):
    expect = {
        "logo.png": (b"\x89PNG", "image/png"),
        "favicon.png": (b"\x89PNG", "image/png"),
        "apple-touch-icon.png": (b"\x89PNG", "image/png"),
        "icon-192.png": (b"\x89PNG", "image/png"),
        "icon-512.png": (b"\x89PNG", "image/png"),
        "og-image.jpg": (b"\xff\xd8\xff", "image/jpeg"),
        "favicon.ico": (b"\x00\x00\x01\x00", "image/x-icon"),
    }
    for name, (magic, ctype) in expect.items():
        r = client.get(f"/brand/{name}")
        assert r.status_code == 200, name
        assert r.headers["content-type"] == ctype
        assert r.content.startswith(magic), name
    assert client.get("/brand/nope.png").status_code == 404


def test_manifest_valid_and_icons_resolve(client):
    data = json.loads((STATIC / "site.webmanifest").read_text(encoding="utf-8"))
    assert data["name"] == "النرجس للذكاء الاصطناعي"
    assert data["short_name"] == "النرجس"
    assert "Al-Narjs" not in json.dumps(data)
    for icon in data["icons"]:
        assert client.get(icon["src"]).status_code == 200, icon["src"]


def test_apple_touch_icon_is_served_at_the_root(client):
    brand = client.get("/brand/apple-touch-icon.png")
    assert brand.status_code == 200
    for path in ("/apple-touch-icon.png", "/apple-touch-icon-precomposed.png"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert r.headers["content-type"] == "image/png"
        assert r.content.startswith(b"\x89PNG")
        assert r.content == brand.content


def test_favicon_ico_route(client):
    r = client.get("/favicon.ico")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/x-icon"
    assert r.content[:4] == b"\x00\x00\x01\x00"


def test_landing_uses_new_logo(client):
    html = client.get("/ar/home").text
    assert "/static/brand/approved-2026-11-27/mark.webp" in html
    assert "/static/logo.svg" not in html
    assert 'rel="manifest"' in html
    assert "/static/brand/approved-2026-11-27/favicon.png" in html
    assert "/static/brand/approved-2026-11-27/og-image.jpg" in html
    assert "/static/logo.png" not in html


@pytest.mark.parametrize("asset", [
    "logo.svg", "logo-dark.svg", "favicon.svg", "brand/vnext/mark-mono.svg",
    "brand/vnext/logo-ar.svg", "brand/vnext/logo-en.svg",
    "brand/vnext/app-icon.svg", "brand/vnext/app-icon-maskable.svg",
])
def test_vnext_mark_is_a_self_contained_vector(client: TestClient, asset: str) -> None:
    response = client.get(f"/static/{asset}")
    assert response.status_code == HTTPStatus.OK
    svg = ElementTree.fromstring(response.content)
    assert svg.tag == "{http://www.w3.org/2000/svg}svg" and svg.get("viewBox")
    assert {el.tag.rsplit("}", 1)[-1] for el in svg.iter()} <= {"svg", "g", "rect", "path", "image"}


@pytest.mark.parametrize(("lang", "direction"), [("ar", "rtl"), ("en", "ltr")])
def test_landing_links_to_localized_license_options(
    client: TestClient, lang: str, direction: str,
) -> None:
    page = client.get(f"/{lang}/home").text
    assert f'<html lang="{lang}" dir="{direction}">' in page
    assert f'href="/{lang}/partnerships#white-label-offer"' in page
    details = client.get(f"/{lang}/partnerships")
    assert details.status_code == HTTPStatus.OK
    assert 'id="white-label-offer"' in details.text


def test_render_glass_preview_does_not_index_or_track_but_keeps_canonical(client, monkeypatch):
    monkeypatch.setenv("DISABLE_LEGACY_REDIRECT", "1")
    preview = client.get("https://alnarjis-preview-pr200.onrender.com/ar/home", follow_redirects=False)
    primary = client.get("https://alnarjisai.com/ar/home", follow_redirects=False)
    assert preview.status_code == primary.status_code == 200
    assert 'name="robots" content="noindex,nofollow"' in preview.text
    assert 'name="robots" content="index,follow"' in primary.text
    for page in (preview, primary):
        assert 'rel="canonical" href="https://alnarjisai.com/ar/home"' in page.text
    for marker in ("google-site-verification", "cookieConsent", "sendBeacon('/api/events'"):
        assert marker not in preview.text
        assert marker in primary.text


@pytest.mark.parametrize("locale", ["ar", "en"])
def test_glass_home_keeps_reference_sections_and_ceo_on_one_page(client, locale):
    home = client.get(f"/{locale}/home")
    assert home.status_code == 200
    order = ("top", "services", "team", "how", "integrations", "pricing")
    positions = [home.text.index(f'id="{target}"') for target in order]
    assert positions == sorted(positions)
    assert home.text.index('id="results"') > positions[-1]
    assert home.text.count('id="start-ceo"') == 1
    assert home.text.count('href="#start-ceo"') >= 6
    assert 'href="/consult"' not in home.text


@pytest.mark.parametrize("locale", ["ar", "en"])
def test_workshop_home_shows_only_shipped_marketing_channels(client, locale):
    html = client.get(f"/{locale}/home").text
    for hidden in ("Moyasar", "feat-coming", "Salla or Zid connection", "ربط سلة أو زد",
                   "لا نعرض ربط متاجر كخدمة متاحة"):
        # The shared pricing stylesheet may still define feat-coming, but no badge renders.
        assert (f'class="{hidden}"' if hidden == "feat-coming" else hidden) not in html
    assert 'class="ag-grid ag-channel-grid"' in html
    assert 'href="/portal?pkg=' in html
    assert "<h3>WhatsApp</h3>" in html or "<h3>واتساب</h3>" in html
    for tower in ("kingdom", "faisaliah", "tv", "majdoul"):
        assert f'/static/img/narjis-glass-towers.svg#tower-{tower}' in html
    assert '<script src="/static/js/narjis-client-workspace.js" defer>' in html
    sprite = client.get("/static/img/narjis-glass-towers.svg")
    assert sprite.status_code == 200 and len(sprite.content) < 6_000
    assert sprite.headers["content-type"] == "image/svg+xml"


def test_workshop_keeps_only_released_items_on_dedicated_pricing(client):
    page = client.get("/ar/pricing")
    assert page.status_code == 200
    assert 'class="feat-coming"' not in page.text and "ربط سلة أو زد" not in page.text
