"""Guards for the v2 (CEO-advisor) landing page.

Replaces the old picker/demo/why guards: those sections no longer exist.
Rules kept: no invented proof, catalog-driven numbers and prices, a working
CTA chain into the existing payment flow, honest risk-reversal copy, and
contact links that are real or absent.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.services import catalog, payments

LANDING = Path(__file__).resolve().parents[1] / "src" / "web" / "templates" / "landing.html"


@pytest.fixture(scope="module")
def page() -> str:
    from src.main import app

    with TestClient(app) as c:
        r = c.get("/ar/home")
        assert r.status_code == 200
        return r.text


@pytest.fixture(scope="module")
def page_en() -> str:
    from src.main import app

    with TestClient(app) as c:
        return c.get("/en/home").text


def test_ceo_consultation_is_in_the_hero_and_posts_to_the_endpoint(page: str) -> None:
    hero = page[page.index('id="top"'):page.index('class="trust"')]
    assert 'id="ceo"' in hero and 'id="ceoForm"' in hero
    assert "/api/ceo/consult" in page
    assert 'id="ceoSubscribe"' in page and 'href="/portal"' in page


def test_every_tier_renders_with_vat_inclusive_total_and_a_checkout_cta(page: str) -> None:
    for key, pkg in catalog.PACKAGES.items():
        assert f'data-plan="{key}"' in page
        assert f"{int(pkg['price']):,}" in page
        total = payments.total_with_vat(pkg["amount"]) / 100
        assert f"{total:,.2f}" in page, f"{key} total incl. VAT missing"
        assert f'href="/portal?pkg={key}"' in page
    assert page.count("is-rec") >= 1


def test_the_price_anchor_uses_real_catalog_numbers(page: str) -> None:
    full = catalog.PACKAGES["company"]
    per_agent = int(full["price"]) // full["agent_count"]
    assert f"{per_agent:,}" in page


def test_no_invented_social_proof(page: str) -> None:
    low = page.lower()
    for word in ("aggregaterating", "ratingvalue", "★★★★", "testimonial-quote"):
        assert word not in low
    assert 'data-placeholder="testimonials"' in page
    # live counters start empty and are only filled from /api/pulse
    assert 'id="pulseLeads">—<' in page and 'id="pulseProjects">—<' in page


def test_risk_reversal_matches_the_refund_terms(page: str) -> None:
    assert "ضمان استرداد" not in page and "money-back" not in page.lower()
    assert "قبل التجديد" in page
    assert "لا تُسترد دفعات الفترة المنقضية" in page


def test_trust_badges_and_vision_disclaimer(page: str) -> None:
    assert "31332495263" in page and "Moyasar" in page
    assert 'id="vision"' in page
    assert "لسنا جهة حكومية" in page


def test_contact_links_are_real_or_absent(page: str) -> None:
    assert "https://wa.me/966552978753?text=" in page
    assert "https://t.me/AlNarjs7BOT" in page
    # no Facebook Page is configured in content/contact.json yet
    from src.services import transfer

    if not transfer.messenger_page():
        assert "m.me/" not in page
    assert 'href="#"' not in page


def test_json_ld_parses_and_offers_follow_the_catalog(page: str) -> None:
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)
    data = [json.loads(b) for b in blocks]
    biz = next(d for d in data if d.get("@type") == "ProfessionalService")
    prices = [o["price"] for o in biz["hasOfferCatalog"]["itemListElement"]]
    assert prices == [catalog.PACKAGES[k]["price"] for k in catalog.PACKAGE_ORDER]
    assert any(d.get("@type") == "FAQPage" for d in data)


def test_seo_and_open_graph_meta(page: str) -> None:
    for tag in ('name="description"', 'property="og:title"', 'property="og:image"', 'rel="canonical"', 'hreflang="en"'):
        assert tag in page


def test_english_page_has_no_arabic_plan_names_in_cards(page_en: str) -> None:
    for pkg in catalog.PACKAGES.values():
        assert pkg["name_en"] in page_en
    assert 'dir="ltr"' in page_en


def test_one_primary_button_per_plan_card() -> None:
    body = LANDING.read_text(encoding="utf-8")
    card = body[body.index('<article class="plan'):body.index("</article>")]
    assert card.count("btn-primary") == 1  # only the recommended tier's branch
