"""New logo: brand assets exist, are served, and are wired into templates."""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.main import app

STATIC = Path("src/web/static")
client = TestClient(app)


def test_svg_brand_files_exist():
    for name in ("logo.svg", "logo-dark.svg", "favicon.svg"):
        body = (STATIC / name).read_text(encoding="utf-8")
        assert body.startswith("<svg") and "</svg>" in body


def test_raster_brand_routes():
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


def test_manifest_valid_and_icons_resolve():
    data = json.loads((STATIC / "site.webmanifest").read_text(encoding="utf-8"))
    assert data["short_name"] == "النرجس"
    for icon in data["icons"]:
        assert client.get(icon["src"]).status_code == 200, icon["src"]


def test_favicon_ico_route():
    r = client.get("/favicon.ico")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/x-icon"
    assert r.content[:4] == b"\x00\x00\x01\x00"


def test_landing_uses_new_logo():
    html = client.get("/ar/home").text
    assert "/static/logo.svg" in html
    assert 'rel="manifest"' in html
    assert "/static/favicon.svg" in html
    assert "/brand/og-image.jpg" in html
    assert "/static/logo.png" not in html
