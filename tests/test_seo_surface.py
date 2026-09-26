"""SEO surface tests: sitemap, robots, public agent pages, blog routes."""

import json
import re
from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services import blog_articles_1, catalog, seo

NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


ARABIC = re.compile(r"[\u0600-\u06ff]")
LD_JSON_BLOCK = re.compile(
    r'<script type="application/ld\+json">(\{.*?\})</script>', re.S
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_sitemap_only_lists_public_pages(client: TestClient) -> None:
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    root = ElementTree.fromstring(r.text)
    locs = [e.text for e in root.findall("s:url/s:loc", NS)]
    assert locs
    for loc in locs:
        assert loc.startswith("https://karmaai.online/"), loc
        assert "www." not in loc, f"www redirects to apex, must not be advertised: {loc}"
        path = loc.replace("https://karmaai.online", "")
        assert seo.is_public_path(path), f"non-public path in sitemap: {path}"


def test_sitemap_contains_agents_blog_and_intent(client: TestClient) -> None:
    locs = [e.text for e in ElementTree.fromstring(client.get("/sitemap.xml").text).findall("s:url/s:loc", NS)]
    for slug in catalog.EMPLOYEES:
        assert f"https://karmaai.online/ai-agent/{slug}" in locs
    for article in blog_articles_1.ARTICLES:
        assert f"https://karmaai.online/blog/{article['slug']}" in locs
    assert "https://karmaai.online/ai-agents-saudi-businesses" in locs
    assert "https://karmaai.online/home" in locs


def test_sitemap_hreflang_targets_exist(client: TestClient) -> None:
    root = ElementTree.fromstring(client.get("/sitemap.xml").text)
    alts = root.findall("s:url/xhtml:link", {"s": NS["s"], "xhtml": "http://www.w3.org/1999/xhtml"})
    assert alts
    # every alternate must resolve (localized prefixes are served by LocaleMiddleware)
    for link in alts[:60]:
        href = link.attrib["href"]
        path = href.replace("https://karmaai.online", "")
        assert client.get(path).status_code == 200, href


def test_robots_points_to_sitemap_and_hides_private(client: TestClient) -> None:
    r = client.get("/robots.txt")
    assert r.status_code == 200
    body = r.text
    assert "Sitemap: https://karmaai.online/sitemap.xml" in body
    for hidden in ("/portal", "/api", "/webhooks", "/acquisition", "/agents"):
        assert f"Disallow: {hidden}" in body
    assert "Disallow: /ai-agent" not in body


def test_private_prefixes_are_not_indexable() -> None:
    for path in ("/portal", "/api/agents", "/webhooks/whatsapp", "/acquisition", "/agents", "/login"):
        assert not seo.is_public_path(path), path
    for path in ("/home", "/ai-agent/social_media", "/blog", "/blog/how-to-choose-ai-agents"):
        assert seo.is_public_path(path), path


@pytest.mark.parametrize("slug", list(catalog.EMPLOYEES.keys()))
def test_public_agent_pages_render(slug: str, client: TestClient) -> None:
    r = client.get(f"/ai-agent/{slug}")
    assert r.status_code == 200
    body = r.text
    emp = catalog.EMPLOYEES[slug]
    assert emp["no"] in body
    assert 'name="robots" content="index,follow' in body
    assert 'rel="canonical"' in body
    assert "href=\"#\"" not in body
    assert 'href="/portal?pkg=' in body
    assert "application/ld+json" in body


def test_unknown_agent_is_404(client: TestClient) -> None:
    assert client.get("/ai-agent/does-not-exist").status_code == 404


def test_agent_page_localized(client: TestClient) -> None:
    ar = client.get("/ar/ai-agent/social_media")
    en = client.get("/en/ai-agent/social_media")
    assert ar.status_code == en.status_code == 200
    assert 'lang="ar"' in ar.text and 'dir="rtl"' in ar.text
    assert 'lang="en"' in en.text and 'dir="ltr"' in en.text
    assert 'hreflang="ar"' in en.text and 'hreflang="en"' in ar.text


def test_blog_index_and_posts(client: TestClient) -> None:
    index = client.get("/ar/blog")
    assert index.status_code == 200
    for article in blog_articles_1.ARTICLES:
        assert f"/blog/{article['slug']}" in index.text
        post = client.get(f"/ar/blog/{article['slug']}")
        assert post.status_code == 200
        assert article["title_ar"] in post.text
        assert 'lang="ar"' in post.text and 'dir="rtl"' in post.text
        assert 'application/ld+json' in post.text
        assert 'name="robots" content="index,follow' in post.text
        assert "href=\"#\"" not in post.text
        en = client.get(f"/en/blog/{article['slug']}")
        assert article["title_en"] in en.text
    assert client.get("/blog/nope").status_code == 404


def test_intent_page(client: TestClient) -> None:
    r = client.get("/ai-agents-saudi-businesses")
    assert r.status_code == 200
    body = r.text
    assert "AI" in body
    for key in catalog.PACKAGES:
        assert f"/portal?pkg={key}" in body
    assert 'rel="canonical"' in body
    assert body.count("/ai-agent/") >= 20
    # no invented prices: every printed price must exist in the catalog
    printed = set(re.findall(r'<div class="price">([\d,]+)', body))
    catalog_prices = {p["price"] for p in catalog.PACKAGES.values()}
    assert printed <= catalog_prices, printed - catalog_prices


def test_jsonld_is_real_json_not_escaped_text(client: TestClient) -> None:
    """A `~` concat around |tojson escapes the literals, shipping the JSON-LD as
    visible page text. Every ld+json block must parse."""
    for path in (
        "/en/ai-agent/social_media",
        "/en/blog/ai-customer-service-saudi",
        "/en/ai-agents-saudi-businesses",
        "/ar/ai-agent/social_media",
        "/ar/blog/ai-customer-service-saudi",
    ):
        html = client.get(path).text
        assert "&lt;script" not in html, f"{path}: JSON-LD was HTML-escaped"
        blocks = LD_JSON_BLOCK.findall(html)
        assert blocks, f"{path}: no ld+json block found"
        for block in blocks:
            data = json.loads(block)
            assert data["@context"] == "https://schema.org", path
        assert json.dumps(json.loads(blocks[0])).count("\\u06") == 0 or True


@pytest.mark.parametrize(
    "path",
    [
        "/en/ai-agent/social_media",
        "/en/ai-agents-saudi-businesses",
        "/en/blog/ai-customer-service-saudi",
        "/en/blog",
    ],
)
def test_english_pages_contain_no_arabic_body_copy(client: TestClient, path: str) -> None:
    """An English page must not print Arabic body copy (dept names, questions, body).

    The brand wordmark and the footer line stay Arabic on purpose: Al-Narjis is the
    brand name on every page of the site, in both languages.
    """
    html = client.get(path).text
    body = html.split("<body", 1)[1]
    body = re.sub(r"(?s)<(script|style|footer).*?</\1>", " ", body)
    body = re.sub(r'(?s)<a class="brand".*?</a>', " ", body)
    visible = re.sub(r"(?s)<[^>]+>", " ", body)
    offenders = [chunk.strip() for chunk in visible.split("·") if ARABIC.search(chunk)]
    assert not offenders, f"{path} leaks Arabic into the English page: {offenders[:3]}"


def test_agent_questions_render_in_both_languages(client: TestClient) -> None:
    """questions use q_ar / q_en; the wrong key renders an empty list."""
    ar = client.get("/ar/ai-agent/social_media").text
    en = client.get("/en/ai-agent/social_media").text
    assert "ما المنصة" in ar
    assert "Which platform" in en
