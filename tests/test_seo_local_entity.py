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
    # Organization, ProfessionalService, WebSite, Person, FAQPage
    assert len(blocks) == 5, "the page lost a structured-data block"
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


def test_the_offer_catalog_lists_the_six_services_without_invented_prices(
    client: TestClient,
) -> None:
    entity = next(
        b for b in json_ld_blocks(client.get("/home").text)
        if b.get("@type") == "ProfessionalService"
    )
    offers = entity["hasOfferCatalog"]["itemListElement"]
    assert len(offers) == 6
    names = {o["itemOffered"]["name"] for o in offers}
    assert "أتمتة الأعمال" in names
    for offer in offers:
        assert "price" not in offer
        assert "price" not in offer["itemOffered"]
        assert offer["itemOffered"]["url"].startswith("https://karmaai.online/ar/services/")


def test_no_rating_is_invented(client: TestClient) -> None:
    """There is no review data, so the site must not claim one."""
    entity = next(
        b for b in json_ld_blocks(client.get("/home").text)
        if b.get("@type") == "ProfessionalService"
    )
    assert "aggregateRating" not in entity
    assert "review" not in json.dumps(entity).lower()


def test_a_named_person_is_published(client: TestClient) -> None:
    """E-E-A-T needs a human, not a "Team" node.

    Google's 2026 guidance treats skill/experience as a content attribute and
    names fabricated bios as a low-quality signal, so the founder is published
    as a Person tied to the business entity.
    """
    types = {b.get("@type") for b in json_ld_blocks(client.get("/home").text)}
    assert "Person" in types, f"no accountable person published; saw {types}"

    person = next(
        b for b in json_ld_blocks(client.get("/home").text)
        if b.get("@type") == "Person"
    )
    assert person["name"].strip(), "the person entity has no name"
    assert person["@id"] == "https://karmaai.online/#founder"
    # the person must point at the business entity that exists on the page
    assert person["worksFor"]["@id"] == "https://karmaai.online/#business"
    assert person["knowsAbout"], "a person entity with no subject matter says nothing"


def test_the_person_carries_no_invented_credentials(client: TestClient) -> None:
    """Guard against the failure this entity could introduce.

    A plausible-sounding fabricated credential is worse than an omission, so the
    fields that would be invented are asserted absent until the owner supplies
    them.
    """
    person = next(
        b for b in json_ld_blocks(client.get("/home").text)
        if b.get("@type") == "Person"
    )
    for fabricated in ("alumniOf", "worksFor_employer", "award", "hasCredential"):
        assert fabricated not in person
    # no invented years, titles or employers smuggled into the free-text fields
    blob = json.dumps(person, ensure_ascii=False)
    for pattern in (r"\b(19|20)\d{2}\b", r"PhD", r"CEO", r"CTO", r"years of experience"):
        assert not re.search(pattern, blob, re.I), (
            f"the person entity asserts something the owner never stated: {pattern}"
        )


def test_the_origin_story_is_visible_on_the_page(client: TestClient) -> None:
    """The person must be visible to a reader, not only to a crawler."""
    # Each language page carries its own language only (no hidden mixed SEO text).
    ar_html = client.get("/ar/home").text
    en_html = client.get("/en/home").text
    assert "كريم" in ar_html
    assert "Karim" in en_html
    assert "سيرفر محلي" in ar_html, "the local-server origin is not stated in Arabic"
    assert "single local server" in en_html, "the local-server origin is not stated in English"


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

def test_every_founder_class_in_markup_has_a_style_rule() -> None:
    """The founder block once shipped with no CSS at all: the markup rendered,
    the entity was valid, and the section still looked broken. A class that no
    stylesheet mentions is invisible to the design-system tests, so assert it
    here."""
    html = LANDING.read_text(encoding="utf-8")
    styles = html + (LANDING.parents[1] / "static/css/narjis-v2.css").read_text(encoding="utf-8")

    used = set()
    for attr in re.findall(r'class="([^"]*founder[^"]*)"', html):
        used.update(c for c in attr.split() if c.startswith("founder"))

    assert used, "the founder markup disappeared - is the block still on the page?"

    for cls in sorted(used):
        assert re.search(r"\." + re.escape(cls) + r"\s*[,{]", styles), (
            f".{cls} is used in the markup but has no style rule"
        )
