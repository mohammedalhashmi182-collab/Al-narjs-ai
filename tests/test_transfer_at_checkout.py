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
    assert "!bank.iban) return;" in block, (
        "an empty copy button for an unpublished account is a dead control"
    )


def test_the_note_points_at_the_transfer_rather_than_only_at_the_missing_card(
    portal: str,
) -> None:
    start = portal.find("if (!cap.card && allowInvoice)")
    note = portal[start: start + 700]
    assert "الأسفل" in note or "below" in note, (
        "the note must direct the buyer to the working method beside it"
    )


# --------------------------------------------------------------------------
# the server contract it depends on
# --------------------------------------------------------------------------


def test_capabilities_hides_bank_transfer_unless_enabled(client: TestClient, monkeypatch) -> None:
    monkeypatch.delenv("CUSTOMER_BANK_TRANSFER_ENABLED", raising=False)
    r = client.get(CAPABILITIES)
    assert r.status_code == 200
    body = r.json()
    assert body["methods"]["invoice"] is False
    assert body["bank"] == {}
    monkeypatch.setenv("CUSTOMER_BANK_TRANSFER_ENABLED", "1")
    enabled = client.get(CAPABILITIES).json()
    assert enabled["methods"]["invoice"] is True
    assert enabled["bank"]["iban"]


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










def test_after_the_invoice_is_created_phone_is_the_handoff(portal: str) -> None:
    segment = portal[portal.find("data.gateway === 'invoice'"):][:2600]
    assert "0540799266" in segment
    assert "tel:+966540799266" in segment
    assert "xfWhatsapp" not in segment
    assert "wa.me" not in segment


def test_capabilities_publishes_the_company_phone(client: TestClient) -> None:
    contact = client.get(CAPABILITIES).json()["contact"]
    assert contact["whatsapp"] == ""
    assert contact["telegram"] == ""
    assert contact["messenger"] == ""
    assert contact["phone"] == "tel:+966540799266"
    assert contact["phone_display"] == "0540799266"


# --------------------------------------------------------------------------
# WhatsApp outranks Telegram wherever the two are offered together
# --------------------------------------------------------------------------

LANDING = REPO / "src" / "web" / "templates" / "landing.html"


@pytest.fixture(scope="module")
def landing() -> str:
    return LANDING.read_text(encoding="utf-8")










def test_the_stack_is_a_column_so_the_order_is_structural(landing: str) -> None:
    """Order must come from layout, not from a magic bottom offset."""
    from pathlib import Path

    css = (Path(__file__).resolve().parents[1] / "src/web/static/css/narjis-v2.css").read_text(encoding="utf-8")
    css = css[css.find("/* Contact stack:"):]
    assert ".contact-stack {" in css, "the stack container rule is missing"
    assert "flex-direction: column" in css, "the stack must be a column to stack the order"


# --------------------------------------------------------------------------
# Owner decision (Oct 2026): the public site's contact is the Al-Narjis
# assistant + email only. No floating WhatsApp/Telegram/Messenger buttons.
# --------------------------------------------------------------------------


def test_the_checkout_has_no_direct_channel_links(portal: str) -> None:
    assert 'id="xfWa"' not in portal
    assert "t.me/" not in portal and "wa.me/" not in portal


def test_the_landing_page_has_no_floating_channel_buttons(client: TestClient) -> None:
    body = client.get("/home").text
    for marker in ('id="waFloat"', 'id="tgFloat"', 'id="msFloat"', "wa.me/", "t.me/", "m.me/"):
        assert marker not in body, marker
    assert 'id="siteAssistant"' in body
    assert "mailto:Al-Narjis@karmaai.online" in body
