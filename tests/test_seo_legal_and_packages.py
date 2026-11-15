"""Legal pages and package pages carry canonical + description; packages are in the sitemap."""

import re

import httpx
import pytest

from src.services import seo


def test_sitemap_lists_package_pages():
    xml = seo.build_sitemap([], [])
    origin = seo.site_origin()
    assert origin == "https://alnarjisai.com"
    for key in ("bidaya", "numuw", "sharikat"):
        assert f"{origin}/ar/packages/{key}" in xml
        assert f"{origin}/en/packages/{key}" in xml
    assert "www.alnarjisai.com" not in xml
    assert "karmaai.online" not in xml


@pytest.mark.parametrize(
    "path",
    ["/ar/privacy", "/en/privacy", "/ar/terms", "/en/terms", "/ar/data-deletion", "/en/data-deletion",
     "/ar/packages/numuw", "/en/packages/bidaya"],
)
async def test_page_has_canonical_and_description(path):
    from src.main import app

    origin = seo.site_origin()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=origin) as client:
        response = await client.get(path)
    assert response.status_code == 200, path
    html = response.text
    canon = re.findall(r'<link rel="canonical" href="([^"]+)"', html)
    assert canon == [f"{origin}{path}"], (path, canon)
    desc = re.findall(r'<meta name="description" content="([^"]+)"', html)
    assert desc and len(desc[0]) > 30, path
    assert "www.alnarjisai.com" not in "".join(canon)
    assert "karmaai.online" not in "".join(canon)


def test_package_pages_are_indexable_for_suffix_redirects():
    assert seo.indexable_page("/packages/numuw")
    assert seo.suffix_canonical_redirect("/ar/packages/numuw/") == "/ar/packages/numuw"
    assert seo.suffix_canonical_redirect("/en/packages/bidaya/") == "/en/packages/bidaya"
