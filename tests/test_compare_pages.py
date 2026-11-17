"""Comparison pages stay factual, and public copy does not mention a trial.

Neither a denial of a free trial nor a 7-day build offer belongs on the site
text these pages and policies use. A paid subscription still has no
outcome-based refund.
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
    "free trial",
    "تجربة مجانية",
    "المجاني فقط التشخيص مع الرئيس التنفيذي الذكي",
    "10 inquiries or bookings",
    "10 استفسارات أو حجوزات",
    "لا يدفع العميل شيئاً",
    "the customer pays nothing",
    "التجربة قبل الدفع",
    "The build before payment",
)
SCAN_ROOTS = (
    ROOT / "src",
    ROOT / "data" / "kb",
    ROOT / "agents" / "base",
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


def test_terms_keep_the_refund_rule_and_omit_any_trial(client: TestClient) -> None:
    ar = client.get("/ar/terms").text
    en = client.get("/en/terms").text
    assert policies.REFUND_CONSENT_AR in ar
    assert policies.REFUND_CONSENT_EN in en
    assert not hasattr(policies, "TRIAL_BUILD_AR")
    assert not hasattr(policies, "TRIAL_BUILD_EN")
    for phrase in BANNED:
        assert phrase not in ar and phrase not in en
        assert phrase not in policies.POLICY_PROMPT
        assert phrase not in policies.OWNER_FAQ_AR


def test_changed_site_text_does_not_mention_a_trial() -> None:
    hits: list[str] = []
    for base in SCAN_ROOTS:
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SCAN_SUFFIXES:
                continue
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for phrase in BANNED:
                if phrase in text:
                    hits.append(f"{path.relative_to(ROOT)}: {phrase}")
    assert hits == []
    for name in ("customer_service.yaml", "sales_closer.yaml"):
        body = (ROOT / "agents/base" / name).read_text(encoding="utf-8")
        assert policies.REFUND_CONSENT_AR in body or policies.REFUND_CONSENT_EN in body
