"""Every /ai-agent/<slug> page links only to internal pages that exist."""

import re

import httpx

from src.services import catalog

HREF = re.compile(r'href="(/[^"#?]*)(?:[?#][^"]*)?"')


def _public_slugs():
    return [s for s in catalog.EMPLOYEES]


async def test_all_agent_pages_have_working_internal_links():
    from src.main import app

    slugs = _public_slugs()
    assert len(slugs) == 35
    links: dict[str, str] = {}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", follow_redirects=True
    ) as client:
        for slug in slugs:
            page = await client.get(f"/ai-agent/{slug}")
            assert page.status_code == 200, slug
            assert 'href="/ai-agent/"' not in page.text, slug
            cards = page.text.split(
                "same department" if "same department" in page.text else "نفس القسم", 1
            )[-1]
            assert len(re.findall(r'href="/ai-agent/[a-z0-9_]+"', cards)) >= 6, slug
            for href in HREF.findall(page.text):
                if href.startswith("//") or href.startswith("/static/"):
                    continue
                links.setdefault(href, slug)
        bad = {}
        for href, slug in sorted(links.items()):
            r = await client.get(href)
            if r.status_code != 200:
                bad[href] = (r.status_code, slug)
    assert not bad, bad
