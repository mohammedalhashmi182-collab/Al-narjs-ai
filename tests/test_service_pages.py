"""Public service pages: length, schema, canonical URLs, and contact limits."""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services import public_services, seo

LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
ARABIC = re.compile(r"[\u0600-\u06ff]")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_every_service_is_in_the_sitemap_and_long_enough() -> None:
    assert [s["slug"] for s in public_services.SERVICES] == list(seo.SERVICE_SLUGS)
    for service in public_services.SERVICES:
        for lang in ("ar", "en"):
            count = public_services.visible_words(service, lang)
            assert 600 <= count <= 1000, f"{service['slug']} {lang} has {count} words"
        assert "CEO" not in service["h1_ar"]
        assert "ر.س" not in service["desc_ar"]


@pytest.mark.parametrize("slug", list(seo.SERVICE_SLUGS))
def test_service_page_is_canonical_and_marked_up(client: TestClient, slug: str) -> None:
    bare = client.get(f"/services/{slug}", follow_redirects=False)
    assert bare.status_code == 301
    assert bare.headers["location"] == f"/ar/services/{slug}"

    ar = client.get(f"/ar/services/{slug}")
    en = client.get(f"/en/services/{slug}")
    assert ar.status_code == en.status_code == 200
    service = public_services.get_service(slug)
    assert service["title_ar"] in ar.text
    assert service["h1_ar"] in ar.text
    assert f'rel="canonical" href="https://karmaai.online/ar/services/{slug}"' in ar.text
    assert 'hreflang="x-default" href="https://karmaai.online/ar/services/' in ar.text
    assert service["title_en"] in en.text
    assert "wa.me/" not in ar.text
    assert "tel:" not in ar.text and "0540799266" not in ar.text
    assert 'href="#"' not in ar.text
    assert "mailto:" not in ar.text and "data-open-assistant" in ar.text
    assert "تحدث مع بوت النرجس" in ar.text
    assert "CEO" not in ar.text.split("<footer", 1)[0]

    blocks = [json.loads(raw) for raw in LD.findall(ar.text)]
    graph = blocks[0]["@graph"]
    types = {node["@type"] for node in graph}
    assert types == {"Service", "FAQPage"}
    assert graph[0]["name"] == service["name_ar"]
    assert len(graph[1]["mainEntity"]) == len(service["faq_ar"])

    en_visible = en.text.split("<body", 1)[1]
    en_visible = re.sub(r"(?s)<(script|style).*?</\1>", " ", en_visible)
    en_visible = re.sub(r"(?s)<a[^>]*>\s*العربية\s*</a>", " ", en_visible)
    assert service["h1_en"] in en.text
    # the language switch is the only intended Arabic on the English page
    assert "تقضي فرق" not in en_visible
    assert "wa.me/" not in en.text


def test_home_links_to_services_and_uses_the_supplied_meta(client: TestClient) -> None:
    html = client.get("/ar/home").text
    assert 'id="services"' in html
    assert "خدماتنا" in html
    for slug in seo.SERVICE_SLUGS:
        assert f'href="/services/{slug}"' in html
    assert "<title>النرجس | أتمتة الأعمال وبوتات الذكاء الاصطناعي والتصميم في السعودية</title>" in html
    assert 'property="og:title" content="النرجس | أتمتة الأعمال وبوتات الذكاء الاصطناعي والتصميم في السعودية"' in html
    assert 'name="twitter:description" content="شركة سعودية من الرياض:' in html
    assert 'property="og:image:alt" content="شعار النرجس — حلول الذكاء الاصطناعي من الرياض"' in html
    assert "<h1>النرجس — حلول الذكاء الاصطناعي وأتمتة الأعمال في السعودية</h1>" in html
    assert 'hreflang="x-default" href="https://karmaai.online/ar/home"' in html


def test_blog_posts_expose_article_schema_and_a_service_link(client: TestClient) -> None:
    html = client.get("/ar/blog/ai-customer-service-saudi").text
    blocks = [json.loads(raw) for raw in LD.findall(html)]
    types = {node["@type"] for node in blocks[0]["@graph"]}
    assert "BlogPosting" in types and "FAQPage" in types
    posting = next(node for node in blocks[0]["@graph"] if node["@type"] == "BlogPosting")
    assert posting["headline"]
    assert posting["datePublished"] == "2026-09-26"
    assert posting["author"]["@type"] == "Organization"
    assert 'href="/services/chatbots"' in html
    assert "wa.me/" not in html
