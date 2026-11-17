"""Comparison pages and the 7-day build offer.

The pages must render, sit in the sitemap, and stay factual. The old denial of
a free trial must be gone. A paid subscription still has no outcome-based refund.
"""

from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services import policies, seo

ROOT = Path(__file__).resolve().parents[1]
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
ARABIC = re.compile(r"[\u0600-\u06ff]")
SLUGS = ("tidio", "manychat", "intercom-fin")

BANNED = (
    "لا توجد تجربة مجانية",
    "There is no free trial",
    "ما عندنا تجربة مجانية",
    "Free trial: none",
    "المجاني فقط التشخيص مع الرئيس التنفيذي الذكي",
)

SCAN_SUFFIXES = {".py", ".html", ".md", ".yaml", ".yml", ".txt"}
SKIP_PARTS = {".git", "__pycache__", ".venv", "node_modules", ".eggs"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("slug", SLUGS)
def test_compare_pages_return_200_in_both_languages(client: TestClient, slug: str) -> None:
    bare = client.get(f"/compare/{slug}", follow_redirects=False)
    assert bare.status_code == 301
    assert bare.headers["location"] == f"/ar/compare/{slug}"

    ar = client.get(f"/ar/compare/{slug}")
    en = client.get(f"/en/compare/{slug}")
    assert ar.status_code == en.status_code == 200
    assert 'lang="ar"' in ar.text and 'dir="rtl"' in ar.text
    assert 'lang="en"' in en.text and 'dir="ltr"' in en.text
    assert f'rel="canonical" href="https://alnarjisai.com/ar/compare/{slug}"' in ar.text
    assert 'hreflang="en"' in ar.text and 'hreflang="ar"' in ar.text
    assert policies.TRIAL_BUILD_AR in ar.text
    assert policies.TRIAL_BUILD_EN in en.text
    assert policies.REFUND_CONSENT_AR in ar.text
    assert policies.REFUND_CONSENT_EN in en.text
    for price in ("790", "1,490", "2,990"):
        assert price in ar.text and price in en.text
    assert "mailto:AlNarjisai@gmail.com" in ar.text
    assert 'href="/ar/voice"' in ar.text
    assert 'href="/en/voice"' in en.text
    assert 'id="voiceLauncher"' in ar.text
    assert 'href="/privacy"' in ar.text and 'href="/data-deletion"' in ar.text
    for needle in ("Salla", "Zid", "سلة", "زد", "VAT", "ضريبة", "قيمة مضافة"):
        assert needle not in ar.text and needle not in en.text
    for phrase in BANNED:
        assert phrase not in ar.text and phrase not in en.text

    visible = en.text.split("<body", 1)[1]
    visible = re.sub(r"(?s)<(script|style).*?</\1>", " ", visible)
    visible = re.sub(r'(?s)<a[^>]*>\s*العربية\s*</a>', " ", visible)
    visible = re.sub(r"(?s)<[^>]+>", " ", visible)
    assert not ARABIC.search(visible), slug


def test_compare_pages_are_in_the_sitemap_footer_and_llms(client: TestClient) -> None:
    xml = client.get("/sitemap.xml").text
    root = ElementTree.fromstring(xml)
    locs = [e.text for e in root.findall("s:url/s:loc", NS)]
    for slug in SLUGS:
        assert f"https://alnarjisai.com/ar/compare/{slug}" in locs
        assert f"https://alnarjisai.com/en/compare/{slug}" not in locs
        assert seo.is_public_path(f"/compare/{slug}")
        assert seo.is_public_path(f"/ar/compare/{slug}")
    assert client.get("/ar/compare/not-a-product").status_code == 404

    home = client.get("/ar/home").text
    llms = client.get("/llms.txt").text
    for slug in SLUGS:
        assert f'href="/compare/{slug}"' in home
        assert f"/ar/compare/{slug}" in llms
        assert f"/en/compare/{slug}" in llms
    about = client.get("/ar/about").text
    for slug in SLUGS:
        assert f'href="/compare/{slug}"' in about


def test_terms_state_the_build_offer_and_keep_the_refund_rule(client: TestClient) -> None:
    ar = client.get("/ar/terms").text
    en = client.get("/en/terms").text
    assert policies.TRIAL_BUILD_AR in ar
    assert policies.TRIAL_BUILD_EN in en
    assert policies.REFUND_CONSENT_AR in ar
    assert policies.REFUND_CONSENT_EN in en
    assert "10 استفسارات أو حجوزات خلال 7 أيام" in ar
    assert "10 inquiries or bookings within 7 days" in en
    assert "لا يدفع العميل شيئاً" in ar
    assert "the customer pays nothing" in en
    for phrase in BANNED:
        assert phrase not in ar and phrase not in en


def test_no_free_trial_denial_remains_in_the_tree() -> None:
    skip = Path(__file__).resolve()
    hits: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.resolve() == skip:
            continue
        if path.suffix.lower() not in SCAN_SUFFIXES:
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for phrase in BANNED:
            if phrase in text:
                hits.append(f"{path.relative_to(ROOT)}: {phrase}")
    assert hits == []
    kb = (ROOT / "data/kb/narjs_services.md").read_text(encoding="utf-8")
    assert policies.TRIAL_BUILD_AR in kb
    assert policies.TRIAL_BUILD_EN in policies.POLICY_PROMPT
    assert policies.TRIAL_BUILD_AR in policies.OWNER_FAQ_AR
    for name in ("customer_service.yaml", "sales_closer.yaml"):
        body = (ROOT / "agents/base" / name).read_text(encoding="utf-8")
        assert policies.TRIAL_BUILD_EN in body
        assert policies.REFUND_CONSENT_AR in body or policies.REFUND_CONSENT_EN in body
