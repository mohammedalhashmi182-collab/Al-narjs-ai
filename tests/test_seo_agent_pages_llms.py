"""Agent-page depth, llms.txt, and locale redirects that must not drop English."""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services import agent_pages, catalog, seo

ARABIC = re.compile(r"[\u0600-\u06ff]")
LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_every_agent_page_has_unique_long_copy() -> None:
    seen_ar = set()
    seen_en = set()
    for slug in catalog.EMPLOYEES:
        page = agent_pages.page_for(slug)
        assert page is not None, slug
        assert agent_pages.visible_words(slug, "ar") >= 300, slug
        assert agent_pages.visible_words(slug, "en") >= 300, slug
        assert len(page["faq_ar"]) >= 3 and len(page["faq_en"]) >= 3
        assert len(page["example_ar"].split()) >= 30
        assert len(page["example_en"].split()) >= 30
        opening_ar = page["paragraphs_ar"][0][:80]
        opening_en = page["paragraphs_en"][0][:80]
        assert opening_ar not in seen_ar
        assert opening_en not in seen_en
        seen_ar.add(opening_ar)
        seen_en.add(opening_en)
        blob = " ".join(page["paragraphs_ar"]) + page["example_ar"] + " ".join(page["paragraphs_en"])
        for banned in ("عميلنا", "★★", "case study"):
            assert banned not in blob
        assert not re.search(r"[A-Za-z]{3,}", " ".join(page["paragraphs_ar"]) + page["example_ar"])


@pytest.mark.parametrize("slug", ["social_media", "arabic_ocr", "legal_privacy"])
def test_rendered_agent_page_has_example_and_faq(client: TestClient, slug: str) -> None:
    page = agent_pages.page_for(slug)
    ar = client.get(f"/ar/ai-agent/{slug}")
    en = client.get(f"/en/ai-agent/{slug}")
    assert ar.status_code == en.status_code == 200
    assert page["faq_ar"][0]["q"] in ar.text
    assert page["faq_en"][0]["q"] in en.text
    assert "مثال توضيحي" in ar.text
    assert "not a client story" in en.text
    assert f'href="/ar/voice"' in ar.text
    assert f'href="/en/voice"' in en.text
    blocks = [json.loads(raw) for raw in LD.findall(ar.text)]
    graph = blocks[0]["@graph"]
    assert {node["@type"] for node in graph} == {"Service", "FAQPage"}
    assert len(graph[1]["mainEntity"]) == len(page["faq_ar"])
    visible = en.text.split("<body", 1)[1]
    visible = re.sub(r"(?s)<(script|style|footer).*?</\1>", " ", visible)
    visible = re.sub(r'(?s)<a class="brand".*?</a>', " ", visible)
    assert not ARABIC.search(re.sub(r"(?s)<[^>]+>", " ", visible))


def test_llms_txt_is_public_plain_text(client: TestClient) -> None:
    bare = client.get("/llms.txt", follow_redirects=False)
    assert bare.status_code == 200
    assert bare.headers["content-type"].startswith("text/plain")
    body = bare.text
    assert "https://karmaai.online" in body
    assert "AlNarjisai@gmail.com" in body
    assert "/llms.txt" not in seo.build_sitemap([], [])
    for key in catalog.PACKAGE_ORDER:
        pkg = catalog.PACKAGES[key]
        assert pkg["name_en"] in body
        assert pkg["name"] in body
        assert pkg["price"] in body
    assert catalog.ADDON_AGENT["price"] in body
    assert "/en/ai-agent/social_media" in body
    robots = client.get("/robots.txt").text
    assert "https://karmaai.online/llms.txt" in robots


@pytest.mark.parametrize(
    "source,target",
    [
        ("/en/refund-policy-", "/en/refund-policy"),
        ("/ar/refund-policy-", "/ar/refund-policy"),
        ("/en/refund-policy/", "/en/refund-policy"),
        ("/ar/services/content-writing/", "/ar/services/content-writing"),
        ("/en/services/content-writing-", "/en/services/content-writing"),
        ("/en/ai-agent/social_media-", "/en/ai-agent/social_media"),
        ("/ar/ai-agent/social_media/", "/ar/ai-agent/social_media"),
        ("/en/blog/ai-customer-service-saudi-", "/en/blog/ai-customer-service-saudi"),
        ("/en/home/", "/en/home"),
        ("/refund-policy-", "/ar/refund-policy"),
        ("/refund-policy/", "/ar/refund-policy"),
    ],
)
def test_hyphen_and_trailing_slash_stay_on_the_right_language(client: TestClient, source: str, target: str) -> None:
    response = client.get(source, follow_redirects=False)
    assert response.status_code == 301, source
    assert response.headers["location"] == target
    if target.startswith("/en/"):
        page = client.get(target)
        assert page.status_code == 200
        assert 'lang="en"' in page.text
    if target.startswith("/ar/"):
        page = client.get(target)
        assert page.status_code == 200
        assert 'lang="ar"' in page.text


def test_unknown_hyphen_suffix_is_not_redirected(client: TestClient) -> None:
    assert client.get("/en/not-a-real-page-", follow_redirects=False).status_code == 404
    assert client.get("/en/ai-agent/does-not-exist-", follow_redirects=False).status_code == 404


def test_plain_english_pages_are_not_redirected(client: TestClient) -> None:
    response = client.get("/en/pricing", follow_redirects=False)
    assert response.status_code == 200
    assert 'lang="en"' in response.text
