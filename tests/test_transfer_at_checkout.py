"""The bank transfer must be reachable before the buyer starts paying.

The defect this file exists to prevent: bank transfer is the only method that
actually takes money, and the invoice page renders the IBAN for it. But the buyer
only ever reaches that page *after* choosing a method, and the note next to the
method list said only "card checkout is not live yet". So at the moment of
decision -- before the buyer has committed to anything -- the one working method
was invisible.

These tests assert the transfer details are on the checkout screen, come from the
same capabilities payload the invoice uses, and are never shown when no account
is published.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.main import app

REPO = Path(__file__).resolve().parents[1]
PORTAL = REPO / "src" / "web" / "templates" / "portal.html"
CAPABILITIES = "/api/payments/capabilities"


@pytest.fixture(scope="module")
def portal() -> str:
    return PORTAL.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# --------------------------------------------------------------------------
# the markup exists on the checkout screen, not only on the invoice
# --------------------------------------------------------------------------


def test_the_checkout_screen_carries_the_transfer_block(portal: str) -> None:
    checkout_at = portal.find('id="step-checkout"')
    assert checkout_at > 0
    block_at = portal.find('id="coXfer"')
    assert block_at > checkout_at, "the transfer block must live in the checkout step"


def test_the_block_is_hidden_until_the_account_is_known(portal: str) -> None:
    block = portal[portal.find('id="coXfer"'): portal.find('id="coXfer"') + 120]
    assert "hidden" in block, "the block must not flash an empty IBAN on load"


def test_iban_account_and_bank_are_all_shown(portal: str) -> None:
    for element in ("xfIban", "xfName", "xfBank"):
        assert f'id="{element}"' in portal, f"{element} is missing"


def test_the_copy_button_targets_the_iban(portal: str) -> None:
    assert 'data-xf-copy="xfIban"' in portal


def test_the_copy_fallback_exists_for_browsers_without_the_clipboard_api(
    portal: str,
) -> None:
    assert "navigator.clipboard" in portal
    assert "execCommand('copy')" in portal, "Safari and older browsers would get nothing"


# --------------------------------------------------------------------------
# it is filled from capabilities, and stays hidden when there is no account
# --------------------------------------------------------------------------


def test_the_values_come_from_the_capabilities_payload(portal: str) -> None:
    """Not a second hard-coded copy of the IBAN.

    The invoice reads the same endpoint. If the account number ever changes, a
    second literal here would silently become the wrong account on the checkout
    screen while the invoice printed the right one.
    """
    block = portal[portal.find("const live = all.filter"): portal.find("if (hidden) {")]
    assert "cap.bank" in block
    assert "$('xfIban').textContent = bank.iban" in block
    if re.search(r"xfIban[^\n]*SA\d{2}", portal):
        raise AssertionError("the IBAN is hard-coded in the template")


def test_it_stays_hidden_when_no_account_is_published(portal: str) -> None:
    block = portal[portal.find("const live = all.filter"): portal.find("if (hidden) {")]
    assert "if (!box || !bank.iban) return;" in block, (
        "an empty copy button for an unpublished account is a dead control"
    )


def test_the_note_points_at_the_transfer_rather_than_only_at_the_missing_card(
    portal: str,
) -> None:
    note = portal[portal.find("if (!cap.card)"): portal.find("if (!cap.card)") + 700]
    assert "الأسفل" in note or "below" in note, (
        "the note must direct the buyer to the working method beside it"
    )


# --------------------------------------------------------------------------
# the server contract it depends on
# --------------------------------------------------------------------------


def test_capabilities_still_publishes_the_account(client: TestClient) -> None:
    r = client.get(CAPABILITIES)
    assert r.status_code == 200
    body = r.json()
    assert body["methods"]["invoice"] is True, "the working method must stay on"
    assert body["bank"]["iban"], "no IBAN is published, so the block cannot show"
    assert body["bank"]["account_name"]
    assert body["bank"]["bank_name"]


def test_capabilities_never_leaks_a_secret(client: TestClient) -> None:
    body = client.get(CAPABILITIES).text
    for secret in ("sk_live", "sk_test", "pk_live", "moyasar_api_secret", "PAYPAL_CLIENT_SECRET"):
        assert secret not in body, f"{secret} reached the public capabilities payload"


def test_the_copy_target_has_no_dead_hash_placeholder(portal: str) -> None:
    """The IBAN cell must not ship a value that overwrites the real one."""
    cell = portal[portal.find('id="xfIban"'): portal.find('id="xfIban"') + 80]
    assert "—" in cell, "the cell should start empty and be filled from capabilities"


# --------------------------------------------------------------------------
# WhatsApp: the escape hatch for anyone who cannot do a bank transfer
# --------------------------------------------------------------------------


def test_the_checkout_offers_a_whatsapp_way_out(portal: str) -> None:
    assert 'id="xfWa"' in portal, "no WhatsApp route out of the checkout"
    assert "fab fa-whatsapp" in portal


def test_the_whatsapp_button_is_conditional_on_a_published_number(portal: str) -> None:
    """No number, no button -- otherwise it renders as a dead link."""
    block = portal[portal.find('id="coXfer"'): portal.find('id="coXfer"') + 4200]
    assert "{% if contact.whatsapp %}" in block
    assert "fa-whatsapp" in block


def test_the_whatsapp_number_is_not_hard_coded(portal: str) -> None:
    """It must come from the published contact source, like the IBAN does."""
    assert 'href="{{ contact.whatsapp }}"' in portal
    if re.search(r'href="https://wa\.me/[0-9]{9,}"', portal):
        raise AssertionError("the WhatsApp number is hard-coded in the template")


def test_the_server_passes_the_contact_to_the_portal(client: TestClient) -> None:
    r = client.get("/portal")
    assert r.status_code == 200
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
    if isinstance(body, str) and "xfWa" in body:
        assert "wa.me" in body, "the WhatsApp block rendered without a usable link"


def test_after_the_invoice_is_created_whatsapp_carries_the_reference(portal: str) -> None:
    """The buyer who already pressed the button must not have to retype the number."""
    segment = portal[portal.find("data.gateway === 'invoice'"):][:2600]
    assert "xfWhatsapp" in segment, "the invoice success message has no WhatsApp help"
    assert "encodeURIComponent" in segment
    assert "payment_id" in segment, "the WhatsApp message must carry the invoice reference"


def test_capabilities_publishes_the_whatsapp_route(client: TestClient) -> None:
    contact = client.get(CAPABILITIES).json()["contact"]
    assert contact["whatsapp"].startswith("https://wa.me/"), contact


# --------------------------------------------------------------------------
# WhatsApp outranks Telegram wherever the two are offered together
# --------------------------------------------------------------------------

LANDING = REPO / "src" / "web" / "templates" / "landing.html"


@pytest.fixture(scope="module")
def landing() -> str:
    return LANDING.read_text(encoding="utf-8")


def test_whatsapp_renders_above_telegram_in_the_floating_stack(landing: str) -> None:
    """The owner's explicit instruction: WhatsApp sits above Telegram."""
    stack = landing[landing.find('<div class="contact-stack">'):]
    stack = stack[: stack.find("</div>") + 10]
    wa = stack.find('id="waFloat"')
    tg = stack.find('id="tgFloat"')
    assert wa > 0, "no WhatsApp floating button"
    assert tg > 0, "no Telegram floating button"
    assert wa < tg, "WhatsApp must come before Telegram in the stack"


def test_whatsapp_renders_above_telegram_in_the_footer(landing: str) -> None:
    socials = landing[landing.find('<div class="socials">'):]
    socials = socials[: socials.find("</div>")]
    wa = socials.find('aria-label="WhatsApp"')
    tg = socials.find('aria-label="Telegram"')
    assert wa > 0 and tg > 0, "both channels must be present in the footer"
    assert wa < tg, "WhatsApp must come before Telegram in the footer"


def test_the_stack_hides_a_button_when_no_number_is_published(landing: str) -> None:
    stack = landing[landing.find('<div class="contact-stack">'):][:1200]
    assert "{% if contact.whatsapp %}" in stack, "an empty WhatsApp link would be dead"
    assert "{% if contact.whatsapp %}" in landing[landing.find('<div class="socials">'):][:900]


def test_the_number_is_not_hard_coded_in_either_place(landing: str) -> None:
    assert 'href="{{ contact.whatsapp }}"' in landing
    for match in re.finditer(r'class="wa-float"[^>]*href="([^"]+)"', landing):
        assert "{{" in match.group(1) or match.group(1).startswith("#"), (
            "the floating WhatsApp button has a literal URL"
        )
    if re.search(r'class="wa-float"[^>]*href="https://wa\.me/[0-9]', landing):
        raise AssertionError("the WhatsApp number is hard-coded")


def test_the_stack_is_a_column_so_the_order_is_structural(landing: str) -> None:
    """Order must come from layout, not from a magic bottom offset."""
    css = landing[landing.find("/* Contact stack:"):]
    css = css[: css.find("@media (max-width:768px)")] if "@media (max-width:768px)" in css else css[:2000]
    assert ".contact-stack{" in css, "the stack container rule is missing"
    assert "flex-direction:column" in css, "the stack must be a column to stack the order"
    assert "position:static" in css, (
        "the children re-anchor themselves, so their order is a magic offset "
        "instead of layout"
    )


def test_the_landing_page_receives_the_contact_channels(client: TestClient) -> None:
    body = client.get("/home").text
    assert 'id="waFloat"' in body, "the WhatsApp button did not render"
    assert 'id="tgFloat"' in body
    assert body.index('id="waFloat"') < body.index('id="tgFloat"'), (
        "WhatsApp must render above Telegram on the live page"
    )
    assert "wa.me" in body, "the WhatsApp link is empty"