"""Public pre-written Wash Out demo page: example conversation, not a live bot."""

from fastapi.testclient import TestClient
import pytest

from src.main import app
from src.services import seo


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_washout_demo_is_not_indexable() -> None:
    assert not seo.is_public_path("/demo")
    assert not seo.is_public_path("/demo/washout")
    assert "Disallow: /demo" in seo.build_robots()


def test_washout_demo_not_in_sitemap(client: TestClient) -> None:
    body = client.get("/sitemap.xml").text
    assert "/demo/washout" not in body


@pytest.mark.parametrize("path", ["/demo/washout", "/demo/washout/"])
def test_washout_demo_page_renders_arabic_example(client: TestClient, path: str) -> None:
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "noindex" in response.headers.get("x-robots-tag", "").lower()
    html = response.text
    assert 'lang="ar"' in html
    assert 'dir="rtl"' in html
    assert 'name="robots" content="noindex, nofollow, noarchive"' in html
    assert "مثال محادثة مكتوب مسبقاً" in html
    assert "ليس بوت مباشر" in html
    assert "عندنا 6 سيارات للشركة" in html
    assert "باقة التوفير" in html
    assert "Salla" not in html
    assert "Zid" not in html
    assert "منصة سلة" not in html
    assert "منصة زد" not in html
    # Do not invent Wash Out prices; Al-Narjis plan prices also do not belong here.
    for price in ("790", "1,490", "1490", "2,990", "2990"):
        assert price not in html
