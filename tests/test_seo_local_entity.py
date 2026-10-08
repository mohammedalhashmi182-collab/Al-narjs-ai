"""Contract tests for the local-business entity added to the landing page.

These exist because structured data fails silently: a typo in a JSON-LD block
renders a perfectly good-looking page that search engines ignore entirely, and no
existing test would notice.
"""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services import catalog

REPO = __import__("pathlib").Path(__file__).resolve().parents[1]
LANDING = REPO / "src" / "web" / "templates" / "landing.html"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def json_ld_blocks(html: str) -> list[dict]:
    """Parse every JSON-LD block, stripping the Jinja the template still needs."""
    blocks = []
    for raw in re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S
    ):
        # strip jinja comments and any unrendered expression so the rest parses
        cleaned = re.sub(r"\{#.*?#\}", "", raw, flags=re.S)
        cleaned = re.sub(r"\{\{.*?\}\}", '"x"', cleaned, flags=re.S)
        cleaned = re.sub(r"\{%.*?%\}", "", cleaned, flags=re.S)
        cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)
        try:
            blocks.append(json.loads(cleaned))
        except json.JSONDecodeError:
            continue
    return blocks


def test_every_json_ld_block_on_the_rendered_page_parses(client: TestClient) -> None:
    r = client.get("/home")
    assert r.status_code == 200
    blocks = json_ld_blocks(r.text)
    # Organization, ProfessionalService, WebSite, FAQPage
    assert len(blocks) == 4, "the page lost a structured-data block"
    for block in blocks:
        assert "@context" in block, block
        assert "@type" in block, block


def test_a_local_business_entity_is_published(client: TestClient) -> None:
    """The gap this closes: Organization alone does not enter the local pack."""
    types = {b.get("@type") for b in json_ld_blocks(client.get("/home").text)}
    assert "ProfessionalService" in types, f"no local entity; saw {types}"
    assert "Organization" in types, "the organization node was replaced, not added to"


def test_the_local_entity_carries_the_fields_google_actually_uses(
    client: TestClient,
) -> None:
    entity = next(
        b for b in json_ld_blocks(client.get("/home").text)
        if b.get("@type") == "ProfessionalService"
    )
    for field in ("geo", "areaServed", "openingHoursSpecification", "address"):
        assert field in entity, f"missing {field}"
    assert entity["@id"] == "https://karmaai.online/#business"


def test_the_two_addresses_on_the_page_agree(client: TestClient) -> None:
    """NAP consistency.

    The real risk is two entities on the same page quoting different addresses:
    search engines read that as two businesses. The policy page is less precise
    (district only) but must name the same locality and district.
    """
    blocks = json_ld_blocks(client.get("/home").text)
    addresses = [
        b["address"]
        for b in blocks
        if isinstance(b.get("address"), dict)
    ]
    assert len(addresses) >= 2, "expected the address on both entities"
    first = addresses[0]
    for other in addresses[1:]:
        for field in ("streetAddress", "postalCode", "addressLocality", "addressCountry"):
            assert other.get(field) == first.get(field), (
                f"{field} differs between two entities on one page: "
                f"{other.get(field)!r} vs {first.get(field)!r}"
            )

    privacy = (REPO / "src" / "web" / "templates" / "privacy.html").read_text(
        encoding="utf-8"
    )
    assert "Riyadh" in privacy and "Al Rimal" in privacy
    assert "الرياض" in privacy and "الرمال" in privacy


def test_the_offer_catalog_is_rendered_from_the_real_prices(client: TestClient) -> None:
    entity = next(
        b for b in json_ld_blocks(client.get("/home").text)
        if b.get("@type") == "ProfessionalService"
    )
    offers = entity["hasOfferCatalog"]["itemListElement"]
    assert len(offers) == len(catalog.PACKAGES)
    published = {o["price"] for o in offers}
    assert published == {pkg["price"] for pkg in catalog.PACKAGES.values()}
    for offer in offers:
        assert offer["priceCurrency"] == "SAR"


def test_no_rating_is_invented(client: TestClient) -> None:
    """There is no review data, so the site must not claim one."""
    entity = next(
        b for b in json_ld_blocks(client.get("/home").text)
        if b.get("@type") == "ProfessionalService"
    )
    assert "aggregateRating" not in entity
    assert "review" not in json.dumps(entity).lower()


def test_the_faq_answer_matches_the_live_roster(client: TestClient) -> None:
    """The FAQ says a number of agents; it must not contradict the catalogue."""
    html = client.get("/home").text
    faq = next(b for b in json_ld_blocks(html) if b.get("@type") == "FAQPage")
    for question in faq["mainEntity"]:
        answer = question["acceptedAnswer"]["text"]
        if re.search(r"\b\d+\s+(?:specialized )?AI agents", answer):
            number = int(re.search(r"\b(\d+)\s+(?:specialized )?AI agents", answer).group(1))
            assert number == catalog.AGENT_COUNT, (
                f"the FAQ claims {number} agents, the catalogue has {catalog.AGENT_COUNT}"
            )