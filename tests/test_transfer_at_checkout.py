"""Customer checkout offers bank transfer when a Saudi account is published.

The checkout has no IBAN block. Bank details stay on the invoice page.
Card checkout stays closed.
"""

from __future__ import annotations

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


def test_the_checkout_screen_has_no_iban_block(portal: str) -> None:
    assert 'id="coXfer"' not in portal
    assert "xfIban" not in portal
    assert "bank_transfer_enabled" in portal


# --------------------------------------------------------------------------
# it is filled from capabilities, and stays hidden when there is no account
# --------------------------------------------------------------------------


def test_a_down_card_checkout_asks_the_buyer_to_contact_us(portal: str) -> None:
    assert "استخدم التحويل البنكي" not in portal
    assert "Payment is temporarily unavailable" in portal
    assert "الدفع غير متاح مؤقتاً" in portal
    assert "AlNarjisai@gmail.com" in portal and "0540799266" not in portal


# --------------------------------------------------------------------------
# the server contract it depends on
# --------------------------------------------------------------------------


def test_capabilities_offer_bank_transfer_when_the_account_is_published(client: TestClient, monkeypatch) -> None:
    for key in ("PAYMENT_IBAN", "PAYMENT_ACCOUNT_NAME", "PAYMENT_BANK_NAME"):
        monkeypatch.delenv(key, raising=False)
    live = client.get(CAPABILITIES).json()
    assert live["methods"]["invoice"] is True
    assert live["card"] is False
    assert live["bank"]["iban"] == "SA5880000126608016363961"
    assert live["bank"]["swift"] == "RJHISARI"


def test_capabilities_never_leaks_a_secret(client: TestClient) -> None:
    body = client.get(CAPABILITIES).text
    for secret in ("sk_live", "sk_test", "pk_live", "PAYPAL_CLIENT_SECRET"):
        assert secret not in body, f"{secret} reached the public capabilities payload"


def test_checkout_methods_are_paypal_and_bank_transfer(portal: str) -> None:
    assert "m: 'mada'" not in portal and "m: 'applepay'" not in portal
    assert "m: 'paypal'" in portal and "m: 'invoice'" in portal


# --------------------------------------------------------------------------
# WhatsApp: the escape hatch for anyone who cannot do a bank transfer
# --------------------------------------------------------------------------










def test_an_invoice_response_opens_the_invoice_page(portal: str) -> None:
    segment = portal[portal.find("data.gateway === 'invoice'"):][:800]
    assert "invoice_url" in segment
    assert "0540799266" not in segment


def test_capabilities_does_not_publish_contact_details(client: TestClient) -> None:
    caps = client.get(CAPABILITIES).json()
    assert "contact" not in caps
    assert "0540799266" not in str(caps)


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
    assert 'id="siteAssistant"' not in body
    assert "tel:" not in body
    assert "mailto:AlNarjisai@gmail.com" in body
    assert "mailto:" not in body.replace("mailto:AlNarjisai@gmail.com", "")
