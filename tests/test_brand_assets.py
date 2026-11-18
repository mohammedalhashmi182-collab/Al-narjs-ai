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
    assert data["short_name"] == "النرجس"
    for icon in data["icons"]:
        assert client.get(icon["src"]).status_code == 200, icon["src"]


def test_favicon_ico_route(client):
    r = client.get("/favicon.ico")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/x-icon"
    assert r.content[:4] == b"\x00\x00\x01\x00"


def test_landing_uses_new_logo(client):
    html = client.get("/ar/home").text
    assert "/static/logo.svg" in html
    assert 'rel="manifest"' in html
    assert "/static/favicon.svg" in html
    assert "/brand/og-image.jpg" in html
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
    assert {el.tag.rsplit("}", 1)[-1] for el in svg.iter()} <= {"svg", "g", "rect", "path"}


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
