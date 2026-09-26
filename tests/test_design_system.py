"""Design-system guards — ODSF v0.2 (see docs/design-system.md).

The visual identity is gold (#F4C430) for action, green (#4F7942) for
structure and Telegram, on ivory (#FAFAF9) with Cairo type. These tests fail
loudly if a template or stylesheet reintroduces the previous blue identity,
regresses to a retired font, or drops the Telegram mark.
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
DESIGN_DOC = ROOT / "docs" / "design-system.md"

# Public pages render the light ivory theme. The owner console is exempt:
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

# ODSF v0.2 palette
GOLD = "#f4c430"
GREEN = "#4f7942"
BG = "#fafaf9"
INK = "#292524"

# the previous Telegram-blue identity, now retired
RETIRED_HEXES = {
    "#2481cc": "retired Telegram blue accent",
    "#1b6fb3": "retired Telegram blue press",
    "#175e97": "retired Telegram blue deep",
    "#6ab3f3": "retired Telegram blue light",
    "#8cb9ef": "retired Telegram blue light",
    "#ddeefb": "retired Telegram blue tint",
    "#eef6fd": "retired Telegram blue tint",
    "#f4f4f5": "retired page grey",
    "#0f0f0f": "retired near-black ink",
    "#707579": "retired secondary grey",
}

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
# the previous type pairing
RETIRED_FONT_LINK = "IBM+Plex+Sans+Arabic"


def read(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def css() -> str:
    return DESIGN_CSS.read_text(encoding="utf-8")


def test_every_listed_template_exists() -> None:
    missing = [n for n in ALL_TEMPLATES if not (TEMPLATES / n).exists()]
    assert not missing, f"templates listed in the design contract are gone: {missing}"


def test_design_doc_exists_and_is_the_source_of_truth() -> None:
    assert DESIGN_DOC.exists(), "docs/design-system.md is the design contract"
    body = DESIGN_DOC.read_text(encoding="utf-8").lower()
    for token in (GOLD, GREEN, BG, INK):
        assert token in body, f"{token} is missing from the design doc"
    assert "cairo" in body, "the design doc does not name Cairo as the type family"


def test_design_css_defines_the_odsf_tokens() -> None:
    body = css()
    for token in (
        f"--odsf-gold: {GOLD}",
        f"--odsf-gold-deep: #c9a227",
        f"--tg-blue: {GREEN}",
        f"--n-sand: {BG}",
        f"--n-brown: {INK}",
        "--r-bubble: 20px",
        "--r-pill: 999px",
    ):
        assert token in body, f"missing design token {token!r}"


def test_design_css_uses_cairo() -> None:
    body = css()
    assert "--font-ar:" in body and "Cairo" in body
    for banned in ("IBM Plex Sans Arabic", "family=Inter"):
        assert banned not in body, f"the design css still references {banned}"


def test_design_css_carries_no_retired_palette() -> None:
    body = css().lower()
    found = [hexv for hexv in RETIRED_HEXES if hexv in body]
    assert not found, f"narjis.css still carries the retired palette: {sorted(found)}"


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
    banned = BANNED_HEXES | RETIRED_HEXES
    found = [why for hexv, why in banned.items() if hexv in body]
    assert not found, f"{name} still carries the old identity: {sorted(set(found))}"


@pytest.mark.parametrize("name", ALL_TEMPLATES)
def test_no_template_loads_a_retired_font(name: str) -> None:
    body = read(name)
    used = [f for f in RETIRED_FONTS if re.search(rf"\b{f}\b", body)]
    assert not used, f"{name} still loads {used}"


@pytest.mark.parametrize("name", ALL_TEMPLATES)
def test_no_template_loads_the_retired_font_pairing(name: str) -> None:
    body = read(name)
    assert RETIRED_FONT_LINK not in body, f"{name} still loads the previous font pairing"
    assert "family=Inter" not in body, f"{name} still loads Inter"


@pytest.mark.parametrize("name", PUBLIC_TEMPLATES)
def test_public_templates_load_cairo(name: str) -> None:
    body = read(name)
    if "fonts.googleapis.com/css2" not in body:
        pytest.skip(f"{name} does not load web fonts at all")
    assert "family=Cairo" in body, f"{name} does not load Cairo"


def test_landing_declares_the_odsf_theme_colour() -> None:
    body = read("landing.html")
    assert f'<meta name="theme-color" content="{BG.upper()}">' in body


def test_owner_console_keeps_dark_surfaces_on_green() -> None:
    body = ADMIN_CSS.read_text(encoding="utf-8").lower()
    assert f"--ad-gold: {GREEN}" in body, "admin accent is not the ODSF green"
    assert f"--ad-action: {GOLD}" in body, "admin has no gold primary action"
    for hexv in ("#c8a45e", "#e6c98a", "#a5803c", "#3dbd7d", "#2481cc", "#1b6fb3"):
        assert hexv not in body, f"admin css still carries {hexv}"


def test_telegram_mark_partial_exists_and_is_reusable() -> None:
    partial = TEMPLATES / "partials" / "_telegram_mark.html"
    assert partial.exists(), "the shared Telegram mark partial is missing"
    body = partial.read_text(encoding="utf-8")
    assert "macro tg_plane" in body
    assert "macro tg_badge" in body
    assert "M9.78 15.6" in body, "the paper-plane path changed"
    assert f"var(--green, {GREEN.upper()})" in body, (
        "the brand disc must take its colour from a design token, not a hard-coded hex"
    )


def test_no_template_hard_codes_the_telegram_brand_colour() -> None:
    """Templates must not reintroduce a literal Telegram blue."""
    for name in ALL_TEMPLATES:
        body = read(name)
        assert "#2481CC" not in body and "#2481cc" not in body, (
            f"{name} hard-codes the retired Telegram blue"
        )


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


# --------------------------------------------------------------------------
# Role icons: one per department, and the SSR and client maps must agree.
# --------------------------------------------------------------------------
ROLE_PARTIAL = TEMPLATES / "partials" / "_role_icon.html"
ROLE_CSS = CSS_DIR / "narjis-role-icons.css"


def test_role_icon_partial_exists_and_is_reusable() -> None:
    assert ROLE_PARTIAL.exists(), "the shared role-icon partial is missing"
    body = ROLE_PARTIAL.read_text(encoding="utf-8")
    assert "macro role_icon" in body
    assert "macro role_svg" in body
    # one draw-on animation only works because every path normalises its length
    assert 'pathLength="1"' in body, "role icon paths must carry pathLength=\"1\""
    assert body.count('class="role-ico"') >= 9, "expected at least nine department glyphs"


def test_role_icon_stylesheet_is_linked_where_the_partial_is_used() -> None:
    assert ROLE_CSS.exists(), "narjis-role-icons.css is missing"
    css_body = ROLE_CSS.read_text(encoding="utf-8")
    assert "@keyframes role-draw" in css_body
    assert "prefers-reduced-motion" in css_body, "role icons must respect reduced motion"
    for name in ALL_TEMPLATES:
        body = read(name)
        if "role_icon(" not in body and "roleIcon(" not in body:
            continue
        assert "narjis-role-icons.css" in body, (
            f"{name} renders role icons but does not load narjis-role-icons.css"
        )


def _catalog_departments() -> set[str]:
    from src.services.catalog import EMPLOYEES

    return {e["dept"] for e in EMPLOYEES.values()}


def _jinja_role_keys() -> set[str]:
    body = ROLE_PARTIAL.read_text(encoding="utf-8")
    block = re.search(r"ROLE_ICONS = \{(.*?)\}", body, re.S)
    assert block, "ROLE_ICONS map is missing from the role-icon partial"
    return set(re.findall(r"'([^']+)':\s*'\w+'", block.group(1)))


def _js_role_keys() -> set[str]:
    body = read("landing.html")
    block = re.search(r"var ROLE_ICONS = \{(.*?)\};", body, re.S)
    assert block, "ROLE_ICONS map is missing from the landing client script"
    return set(re.findall(r"'([^']+)':\s*'\w+'", block.group(1)))


def _js_dept_en_keys() -> set[str]:
    body = read("landing.html")
    block = re.search(r"var DEPT_EN = \{(.*?)\};", body, re.S)
    assert block, "DEPT_EN map is missing from the landing client script"
    return set(re.findall(r"'([^']+)':\s*'[^']+'", block.group(1)))


def test_every_catalog_department_has_a_role_icon() -> None:
    depts = _catalog_departments()
    assert depts, "the catalog exposes no departments"
    assert depts <= _jinja_role_keys(), (
        f"departments with no icon: {sorted(depts - _jinja_role_keys())}"
    )


def test_role_icon_and_english_label_maps_agree() -> None:
    assert _jinja_role_keys() == _js_role_keys(), (
        "the SSR role-icon map and the client role-icon map have drifted"
    )
    assert _js_dept_en_keys() == _catalog_departments(), (
        f"DEPT_EN is out of date: {sorted(_catalog_departments() ^ _js_dept_en_keys())}"
    )


def test_unknown_department_falls_back_to_the_same_glyph_on_both_sides() -> None:
    """An unmapped department must not render differently after hydration."""
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(TEMPLATES)))
    mod = env.get_template("partials/_role_icon.html").module
    server = mod.role_icon("قسم غير معروف")
    assert "role-ico" in server and 'class="g"' in server

    # both sides must land on the same geometry for an unmapped department
    clock = "M12 7.6v4.6l3 1.8"
    assert clock in server, "the server fallback is not the clock glyph"

    body = read("landing.html")
    default = re.search(r"default: return s \+ (.*?); \}", body, re.S)
    assert default, "the client roleIcon has no default branch"
    assert clock in default.group(1), (
        "the client fallback glyph differs from the server fallback glyph"
    )


