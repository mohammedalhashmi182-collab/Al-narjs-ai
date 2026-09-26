"""Editorial + SEO guard rails for the public content surface.

These tests exist because thin, fabricated, or wrong-language content is the fastest
way to lose both rankings and customers. They are intentionally strict.

``test_no_latin_inside_arabic_copy`` was added after a real incident: a generated
article mixed stray Latin and transliterated words into Arabic sentences
(``sortez closures المتطلبات``), which shipped to a live page. Never relax it.
"""

import pathlib
import re
import unicodedata

import pytest

from src.services import blog_articles_1 as blog
from src.services import catalog, seo

FORBIDDEN_CLAIMS = [
    "ضمان المبيعات",
    "نضمن",
    "مضاعفة المبيعات",
    "أول 5 عملاء",
    "تجربة مجانية",
    "رد آلي على مدار الساعة",
    "24/7",
]

EXPECTED_ARTICLES = 10

CJK = re.compile(r"[\u3000-\u9fff\uff00-\uffef]")
ARABIC = re.compile(r"[\u0600-\u06ff]")
LATIN_WORD = re.compile(r"[A-Za-z]{2,}")
ARABIC_SENTENCE = re.compile(r"[\u0600-\u06ff][^\n]*[A-Za-z]{2,}")
REPEATED_WORD = re.compile(r"\b(\w+)\s+\1\b")


def _arabic_text(article: dict) -> str:
    parts = [article["title_ar"], article["desc_ar"], article["category_ar"]]
    for block in article["body_ar"]:
        parts.append(block.get("h", ""))
        parts.extend(block.get("p", []))
        parts.extend(block.get("ul", []))
    for item in article["faq"]:
        parts.append(item["q"])
        parts.append(item["a"])
    return "\n".join(parts)


def _english_text(article: dict) -> str:
    parts = [article["title_en"], article["desc_en"], article["category_en"]]
    for block in article["body_en"]:
        parts.append(block.get("h", ""))
        parts.extend(block.get("p", []))
        parts.extend(block.get("ul", []))
    for item in article["faq_en"]:
        parts.append(item["q"])
        parts.append(item["a"])
    return "\n".join(parts)


def test_articles_exist_and_are_unique() -> None:
    assert len(blog.ARTICLES) == EXPECTED_ARTICLES
    slugs = [a["slug"] for a in blog.ARTICLES]
    assert len(set(slugs)) == len(slugs)


@pytest.mark.parametrize("article", blog.ARTICLES, ids=lambda a: a["slug"])
def test_article_schema(article: dict) -> None:
    required = (
        "slug",
        "title_ar",
        "title_en",
        "desc_ar",
        "desc_en",
        "date",
        "body_ar",
        "body_en",
        "faq",
        "faq_en",
        "keywords",
    )
    for key in required:
        assert article.get(key), f"{article['slug']} missing {key}"
    assert re.fullmatch(r"[a-z0-9-]+", article["slug"]), article["slug"]
    assert 60 <= len(article["desc_ar"]) <= 165, f"{article['slug']} meta description length"
    assert 30 <= len(article["desc_en"]) <= 165, f"{article['slug']} en meta description length"
    assert ARABIC.search(article["title_ar"]), article["slug"]
    assert not ARABIC.search(article["title_en"]), f"{article['slug']} en title contains Arabic"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", article["date"]), article["slug"]
    assert 2 <= len(article["faq"]) <= 5, f"{article['slug']} faq count"
    assert 4 <= len(article["body_ar"]) <= 12, f"{article['slug']} block count"
    assert 4 <= len(article["body_en"]) <= 12, f"{article['slug']} en block count"


@pytest.mark.parametrize("article", blog.ARTICLES, ids=lambda a: a["slug"])
def test_article_text_is_clean(article: dict) -> None:
    text = _arabic_text(article) + "\n" + _english_text(article)
    assert not CJK.search(text), f"{article['slug']} contains CJK/fullwidth characters"
    assert "\ufffd" not in text, f"{article['slug']} contains replacement characters"
    for line in text.splitlines():
        assert line == line.rstrip(), f"{article['slug']} has trailing whitespace"
    assert not REPEATED_WORD.search(text), f"{article['slug']} has a repeated word"
    paragraphs = sum(len(block.get("p", [])) for block in article["body_ar"])
    assert paragraphs >= 4, f"{article['slug']} too thin"
    bullets = sum(len(block.get("ul", [])) for block in article["body_ar"])
    assert bullets >= 3, f"{article['slug']} has no practical list"


@pytest.mark.parametrize("article", blog.ARTICLES, ids=lambda a: a["slug"])
def test_no_latin_inside_arabic_copy(article: dict) -> None:
    """Arabic copy must be pure Arabic: no stray Latin words, no transliterations.

    This is the guard that catches corrupted generated text before it reaches a page.
    """
    offenders = ARABIC_SENTENCE.findall(_arabic_text(article))
    assert not offenders, f"{article['slug']} mixes Latin into Arabic copy: {offenders[:3]}"


@pytest.mark.parametrize("article", blog.ARTICLES, ids=lambda a: a["slug"])
def test_english_content_is_english(article: dict) -> None:
    text = _english_text(article)
    assert not ARABIC.search(text), f"{article['slug']} English body contains Arabic"
    assert len(text) > 800, f"{article['slug']} English body too thin"
    for ar_item, en_item in zip(article["faq"], article["faq_en"]):
        assert en_item["q"] != ar_item["q"], f"{article['slug']} English FAQ is a copy of the Arabic"


@pytest.mark.parametrize("article", blog.ARTICLES, ids=lambda a: a["slug"])
def test_no_unverified_claims(article: dict) -> None:
    text = _arabic_text(article) + "\n" + _english_text(article)
    for claim in FORBIDDEN_CLAIMS:
        assert claim not in text, f"{article['slug']} contains unverified claim: {claim}"


@pytest.mark.parametrize("article", blog.ARTICLES, ids=lambda a: a["slug"])
def test_no_hardcoded_prices(article: dict) -> None:
    """Prices live in catalog.PACKAGES so copy can never contradict billing."""
    text = _arabic_text(article) + "\n" + _english_text(article)
    for amount in ("800", "1000", "1200", "1500", "199", "499", "999"):
        assert amount not in text, f"{article['slug']} hard-codes price {amount}"


@pytest.mark.parametrize("article", blog.ARTICLES, ids=lambda a: a["slug"])
def test_normalised_text_roundtrips(article: dict) -> None:
    text = _arabic_text(article)
    assert unicodedata.normalize("NFC", text) == text, f"{article['slug']} not NFC"


@pytest.mark.parametrize("article", blog.ARTICLES, ids=lambda a: a["slug"])
def test_public_arabic_ratio_is_high(article: dict) -> None:
    text = _arabic_text(article)
    latin = len(LATIN_WORD.findall(text))
    arabic = len(ARABIC.findall(text))
    assert arabic > latin * 12, f"{article['slug']} looks machine-translated"


def test_articles_are_indexable_seo_paths() -> None:
    for article in blog.ARTICLES:
        assert seo.is_public_path(f"/blog/{article['slug']}")


MARKETING_DOCS = ["marketing/launch-content-ar.md", "marketing/launch-plan-ar.md"]
AGENT_COUNT_CLAIM = re.compile(r"(\d+)\s+وكيل")


@pytest.mark.parametrize("doc", MARKETING_DOCS)
def test_marketing_agent_count_matches_the_catalog(doc: str) -> None:
    """Published copy states the agent count as a literal. The site and the catalog
    already say 35; if the catalog grows, this fails instead of shipping a wrong count."""
    path = pathlib.Path(doc)
    if not path.exists():
        pytest.skip(f"{doc} not present")
    counts = {int(n) for n in AGENT_COUNT_CLAIM.findall(path.read_text(encoding="utf-8"))}
    assert counts == {len(catalog.EMPLOYEES)}, (
        f"{doc} claims {sorted(counts)} agents, the catalog has {len(catalog.EMPLOYEES)}"
    )
