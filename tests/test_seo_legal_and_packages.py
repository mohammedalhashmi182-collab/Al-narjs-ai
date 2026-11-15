"""Legal pages and package pages carry canonical + description; packages are in the sitemap."""

import re

import httpx
import pytest

from src.services import seo


def test_sitemap_lists_package_pages():
    xml = seo.build_sitemap([], [])
    for key in ("bidaya", "numuw", "sharikat"):
        assert f"https://karmaai.online/ar/packages/{key}" in xml


@pytest.mark.parametrize(
    "path",
    ["/ar/privacy", "/en/privacy", "/ar/terms", "/en/terms", "/ar/data-deletion", "/en/data-deletion",
     "/ar/packages/numuw", "/en/packages/bidaya"],
)
async def test_page_has_canonical_and_description(path):
    from src.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://karmaai.online") as client:
        response = await client.get(path)
    assert response.status_code == 200, path
    html = response.text
    canon = re.findall(r'<link rel="canonical" href="([^"]+)"', html)
    assert canon == [f"https://karmaai.online{path}"], (path, canon)
    desc = re.findall(r'<meta name="description" content="([^"]+)"', html)
    assert desc and len(desc[0]) > 30, path
    assert "www.karmaai.online" not in "".join(canon)
