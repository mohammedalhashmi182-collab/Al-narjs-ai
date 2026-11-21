"""Package pages use apex canonicals, appear in the sitemap, and open checkout."""

from xml.etree import ElementTree

from fastapi.testclient import TestClient
from src.main import app, templates
from src.services import payments
from src.services.catalog import PACKAGE_ORDER

NS = {
    "s": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "xhtml": "http://www.w3.org/1999/xhtml",
}


def _open_payments(monkeypatch) -> None:
    monkeypatch.setattr(payments, "payments_open", lambda: True)
    monkeypatch.setitem(templates.env.globals, "payments_open", lambda: True)


def test_package_pages_use_apex_canonical_and_checkout_cta(monkeypatch) -> None:
    _open_payments(monkeypatch)
    client = TestClient(app)
    for key in PACKAGE_ORDER:
        for lang in ("ar", "en"):
            path = f"/{lang}/packages/{key}"
            response = client.get(path, follow_redirects=True)
            assert response.status_code == 200, path
            html = response.text
            canonical = f"https://alnarjisai.com/{lang}/packages/{key}"
            assert f'href="{canonical}"' in html
            assert "www.alnarjisai.com" not in html
            assert 'content="https://alnarjisai.com/brand/og-image.jpg"' in html
            assert f"/portal?pkg={key}" in html
            assert "checkout=1" in html


def test_sitemap_and_llms_include_package_pages() -> None:
    client = TestClient(app)
    xml = client.get("/sitemap.xml").text
    root = ElementTree.fromstring(xml)
    locs = {el.text for el in root.findall("s:url/s:loc", NS)}
    alts = {el.get("href") for el in root.findall("s:url/xhtml:link", NS)}
    llms = client.get("/llms.txt").text
    for key in PACKAGE_ORDER:
        assert f"https://alnarjisai.com/ar/packages/{key}" in locs
        assert f"https://alnarjisai.com/en/packages/{key}" in alts
        assert f"/ar/packages/{key}" in llms
        assert f"/en/packages/{key}" in llms


def test_privacy_and_terms_have_description_and_canonical() -> None:
    client = TestClient(app)
    for lang, slug in (("ar", "privacy"), ("en", "privacy"), ("ar", "terms"), ("en", "terms")):
        path = f"/{lang}/{slug}"
        response = client.get(path, follow_redirects=True)
        assert response.status_code == 200, path
        html = response.text
        assert 'name="description"' in html
        assert f'href="https://alnarjisai.com/{lang}/{slug}"' in html
        assert 'content="https://alnarjisai.com/brand/og-image.jpg"' in html
