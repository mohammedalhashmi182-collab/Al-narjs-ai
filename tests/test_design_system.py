"""Design-system guards.

The visual identity is Telegram (blue + white). These tests fail loudly if a
template or stylesheet reintroduces the old black/gold/WhatsApp-green identity,
hard-codes a colour instead of using a token, or drops the Telegram mark.
"""
from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "src" / "web" / "templates"
CSS_DIR = ROOT / "src" / "web" / "static" / "css"
DESIGN_CSS = CSS_DIR / "narjis.css"
ADMIN_CSS = CSS_DIR / "narjis-dark-admin.css"

# Public pages render the light Telegram theme. The owner console is exempt:
# it is intentionally dark (see narjis-dark-admin.css).
PUBLIC_TEMPLATES = [
    "landing.html",
    "agent_public.html",
    "blog_index.html",
    "blog_post.html",
    "intent_agents.html",
    "guide.html",
    "consult.html",
    "package.html",
    "payment_status.html",
    "portal.html",
    "login.html",
    "privacy.html",
    "terms.html",
    "data_deletion.html",
    "invoice.html",
    "invoice_en.html",
    "company.html",
]
ALL_TEMPLATES = PUBLIC_TEMPLATES + [
    "base.html",
    "dashboard.html",
    "agents.html",
    "sales_dashboard.html",
    "sales_demo.html",
    "sales_lead.html",
    "sales_proposal.html",
]

# the pre-Telegram identity
BANNED_HEXES = {
    "#c8a45e": "old gold",
    "#e6c98a": "old gold",
    "#a5803c": "old gold",
    "#d4a85e": "old gold",
    "#c59f55": "old gold",
    "#b89a5e": "old gold",
    "#3dbd7d": "WhatsApp green",
    "#0b3d2e": "WhatsApp green",
    "#0f5132": "WhatsApp green",
    "#0a0b0e": "old near-black background",
    "#0e1015": "old near-black background",
    "#12151c": "old near-black background",
    "#1a1d25": "old near-black background",
    "#98a1b0": "old grey-on-dark text",
    "#eef1f6": "old light-on-dark text",
    "#d7dce5": "old light-on-dark text",
}
RETIRED_FONTS = ["Tajawal", "Almarai", "Manrope"]


def read(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def css() -> str:
    return DESIGN_CSS.read_text(encoding="utf-8")


def test_every_listed_template_exists() -> None:
    missing = [n for n in ALL_TEMPLATES if not (TEMPLATES / n).exists()]
    assert not missing, f"templates listed in the design contract are gone: {missing}"


def test_design_css_defines_the_telegram_tokens() -> None:
    body = css()
    for token in (
        "--tg-blue: #2481cc",
        "--tg-blue-press: #1b6fb3",
        "--tg-blue-deep: #175e97",
        "--n-sand: #f4f4f5",
        "--n-brown: #0f0f0f",
        "--n-brown-2: #707579",
        "--r-bubble: 20px",
        "--r-pill: 999px",
    ):
        assert token in body, f"missing design token {token!r}"


def test_design_css_uses_the_new_fonts() -> None:
    body = css()
    assert "IBM Plex Sans Arabic" in body
    assert "Inter" in body


def test_conversation_surfaces_are_rounder_than_a_web_default() -> None:
    """Telegram bubbles: a generous radius with one tight corner."""
    body = css()
    assert "--r-bubble: 20px" in body
    bubble_block = re.search(r"\.cmsg,.*?\.bubble-tail \{.*?\}", body, re.DOTALL)
    assert bubble_block, "conversation surface rules are missing from the design css"
    assert "var(--r-bubble)" in bubble_block.group(0)
    assert re.search(r"border-start-start-radius: 8px", bubble_block.group(0))


@pytest.mark.parametrize("name", PUBLIC_TEMPLATES)
def test_public_templates_have_no_legacy_identity(name: str) -> None:
    body = read(name).lower()
    found = [why for hexv, why in BANNED_HEXES.items() if hexv in body]
    assert not found, f"{name} still carries the old identity: {sorted(set(found))}"


@pytest.mark.parametrize("name", ALL_TEMPLATES)
def test_no_template_loads_a_retired_font(name: str) -> None:
    body = read(name)
    used = [f for f in RETIRED_FONTS if re.search(rf"\b{f}\b", body)]
    assert not used, f"{name} still loads {used}"


@pytest.mark.parametrize("name", PUBLIC_TEMPLATES)
def test_public_templates_load_the_telegram_font_pair(name: str) -> None:
    body = read(name)
    if "fonts.googleapis.com/css2" not in body:
        pytest.skip(f"{name} does not load web fonts at all")
    assert "IBM+Plex+Sans+Arabic" in body, f"{name} does not load IBM Plex Sans Arabic"
    assert "family=Inter" in body, f"{name} does not load Inter"


def test_owner_console_keeps_dark_surfaces_but_loses_the_gold() -> None:
    body = ADMIN_CSS.read_text(encoding="utf-8").lower()
    assert "--ad-gold: #2481cc" in body, "admin accent is not the Telegram blue"
    for hexv in ("#c8a45e", "#e6c98a", "#a5803c", "#3dbd7d"):
        assert hexv not in body, f"admin css still carries {hexv}"


def test_telegram_mark_partial_exists_and_is_reusable() -> None:
    partial = TEMPLATES / "partials" / "_telegram_mark.html"
    assert partial.exists(), "the shared Telegram mark partial is missing"
    body = partial.read_text(encoding="utf-8")
    assert "macro tg_plane" in body
    assert "macro tg_badge" in body
    assert "M9.78 15.6" in body, "the paper-plane path changed"
    assert 'fill="#2481CC"' in body, "the brand disc is not the Telegram blue"


def test_public_telegram_ctas_use_the_shared_mark() -> None:
    for name in PUBLIC_TEMPLATES:
        body = read(name)
        if "t.me/AlNarjs7BOT" not in body:
            continue
        assert (
            "tg_plane(" in body or "tg_plane_cls(" in body
        ), f"{name} links to Telegram without the shared paper-plane mark"
        assert "fa-telegram" not in body, f"{name} still uses the icon font for Telegram"


def test_templates_rendering_the_mark_import_the_partial() -> None:
    for name in ALL_TEMPLATES:
        body = read(name)
        if "tg_plane(" not in body and "tg_badge(" not in body:
            continue
        assert (
            "partials/_telegram_mark.html" in body
        ), f"{name} calls the Telegram mark without importing the partial"
