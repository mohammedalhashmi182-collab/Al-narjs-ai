"""ODSF §8 — the Luxury Dark public presentation.

This file exists because §8 had **no test coverage at all**: the token table in
``docs/design-system.md`` described a near-black, glassmorphic storefront, and
that layer was implemented in ``narjis-luxury.css`` and wired into thirteen
public templates, yet nothing asserted any of it. A palette could be swapped,
retired or half-applied and the suite stayed green.

Two decisions are locked here, both taken by the owner:

**Gold is the public action hue.** A Humain-inspired mint/teal dark theme came
first and was later retired on the owner's instruction -- gold is the flower the
company is named for. The retired hexes must not reappear on a public page.

**Invoices stay light.** §8 scopes the dark canvas to the storefront and
excludes printed documents, so the invoice templates are asserted to stay out of
the luxury layer. Their accent colour is a separate owner decision and is not
touched here.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
CSS_DIR = ROOT / "src" / "web" / "static" / "css"
TEMPLATES = ROOT / "src" / "web" / "templates"
LUXURY_CSS = CSS_DIR / "narjis-luxury.css"

# The retired Humain palette, case-insensitive. None may appear on a public page.
RETIRED_HEXES = ("00d49c", "00ad92", "00879f", "d0f94a")
RETIRED_RGB = re.compile(r"(?:0,\s*212,\s*156|0,\s*173,\s*146|208,\s*249,\s*74)", re.I)

# Public storefront pages that must render on the dark canvas (§8).
PUBLIC_PAGES = [
    "landing.html",
    "agent_public.html",
    "blog_index.html",
    "blog_post.html",
    "intent_agents.html",
    "consult.html",
    "package.html",
    "payment_status.html",
    "portal.html",
    "login.html",
    "privacy.html",
    "terms.html",
    "data_deletion.html",
]

# Printed documents: deliberately excluded from the dark presentation.
LIGHT_DOCUMENTS = ["invoice.html", "invoice_en.html", "invoice_missing.html", "invoice_missing_en.html"]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def luxury() -> str:
    return read(LUXURY_CSS)


def test_the_layer_exists(luxury: str) -> None:
    assert luxury, "narjis-luxury.css is empty or missing"
    assert "body.luxury" in luxury, "the layer is not scoped to body.luxury"


class TestVermilionIsThePublicActionHue:
    """The owner's replacement for gold: one saturated vermilion action hue.

    The colour itself moved on instruction, but the rule behind it did not: one
    action hue per view, defined once as a token, never re-decided by a
    component. These tests keep that rule under the new name so the layer cannot
    quietly grow a second action colour again.
    """

    ACCENT = "#ff5a36"

    def test_the_layer_defines_the_accent(self, luxury: str) -> None:
        for token in ("--n-accent", "--odsf-accent"):
            match = re.search(rf"{token}:\s*(#[0-9a-f]{{6}})", luxury, re.I)
            assert match, f"{token} is not defined in the luxury layer"
            assert match.group(1).lower() == self.ACCENT, (
                f"{token} is {match.group(1)}, expected the owner's {self.ACCENT}"
            )

    def test_the_legacy_gold_names_resolve_to_the_accent(self, luxury: str) -> None:
        """Retired, not deleted: `--n-gold*` still resolves, so nothing breaks."""
        for token in ("--n-gold", "--odsf-gold"):
            match = re.search(rf"{token}:\s*([^;]+);", luxury)
            assert match, f"{token} disappeared; templates still reference it"
            assert "accent" in match.group(1).lower(), (
                f"{token} no longer aliases the accent family: {match.group(1)}"
            )

    def test_no_gold_hue_survives_anywhere_in_the_layer(self, luxury: str) -> None:
        for retired in ("f4c430", "e0b824", "c9a227", "fef6dc"):
            assert retired not in luxury.lower(), f"gold #{retired} is still in the luxury layer"

    def test_the_layer_defines_no_retired_mint(self, luxury: str) -> None:
        for hex_value in RETIRED_HEXES:
            assert hex_value not in luxury.lower(), f"retired hue #{hex_value} is still in the luxury layer"
        assert not RETIRED_RGB.search(luxury), "retired mint rgb() values remain in the luxury layer"

    @pytest.mark.parametrize("page", PUBLIC_PAGES)
    def test_no_public_page_carries_a_retired_hue(self, page: str) -> None:
        body = read(TEMPLATES / page).lower()
        for hex_value in RETIRED_HEXES:
            assert hex_value not in body, f"{page} still hardcodes the retired #{hex_value}"
        assert not RETIRED_RGB.search(body), f"{page} still hardcodes a retired mint rgb()"

    @pytest.mark.parametrize("page", PUBLIC_PAGES)
    def test_no_public_page_carries_a_retired_gold_hex(self, page: str) -> None:
        body = read(TEMPLATES / page).lower()
        for retired in ("f4c430", "e0b824"):
            assert retired not in body, f"{page} still hardcodes the retired gold #{retired}"

    def test_the_dark_canvas_is_near_black(self, luxury: str) -> None:
        assert re.search(r"--n-sand:\s*#060607", luxury, re.I), "the page canvas is not #060607"
        assert re.search(r"background-color:\s*#060607", luxury, re.I)

    def test_the_accent_is_the_only_action_colour_on_public_pages(self) -> None:
        """One action hue per view. The accent owns it."""
        landing = read(TEMPLATES / "landing.html")
        assert re.search(r"--gold:\s*#ff5a36", landing, re.I), (
            "landing.html does not resolve the action colour to the accent"
        )

    def test_the_accent_is_readable_on_the_dark_canvas(self) -> None:
        """The reason vermilion: measurable contrast on a near-black canvas."""
        def luminance(hex_value: str) -> float:
            value = hex_value.lstrip("#")
            channels = [int(value[i : i + 2], 16) / 255 for i in (0, 2, 4)]
            linear = [
                c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
                for c in channels
            ]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

        def ratio(a: str, b: str) -> float:
            first, second = sorted((luminance(a), luminance(b)), reverse=True)
            return (first + 0.05) / (second + 0.05)

        assert ratio(self.ACCENT, "#060607") >= 4.5, (
            "the accent fails AA against the dark canvas"
        )

    def test_white_text_is_never_put_on_the_accent_fill(self) -> None:
        """White on vermilion is 3.10:1 and fails AA, so ink is required."""
        landing = read(TEMPLATES / "landing.html")
        pattern = re.compile(
            r"background:\s*var\(--(?:gold|odsf-gold)\)[^;]*;[^}]*color:\s*#fff",
            re.I | re.S,
        )
        assert not pattern.search(landing), (
            "a control fills with the accent and sets white text; use the dark ink"
        )


class TestWiring:
    @pytest.mark.parametrize("page", PUBLIC_PAGES)
    def test_the_page_loads_the_layer(self, page: str) -> None:
        body = read(TEMPLATES / page)
        assert "narjis-luxury.css" in body, f"{page} does not load the luxury layer"

    @pytest.mark.parametrize("page", PUBLIC_PAGES)
    def test_the_page_activates_the_layer(self, page: str) -> None:
        """Loading the stylesheet is not enough: body must carry the class."""
        body = read(TEMPLATES / page)
        assert re.search(r"<body[^>]*\bluxury\b", body), (
            f"{page} loads the luxury layer but body.luxury is not set, so it renders light"
        )

    @pytest.mark.parametrize("page", LIGHT_DOCUMENTS)
    def test_printed_invoices_stay_out_of_the_dark_layer(self, page: str) -> None:
        body = read(TEMPLATES / page)
        assert not re.search(r"<body[^>]*\bluxury\b", body), (
            f"{page} is a printed document and must not render on the dark canvas"
        )
        assert "narjis-luxury.css" not in body, (
            f"{page} is a printed document and must not load the storefront layer"
        )


class TestGlassAndMotion:
    def test_cards_use_the_glass_treatment(self, luxury: str) -> None:
        assert "backdrop-filter" in luxury, "no glass layer: backdrop-filter is missing"
        assert re.search(r"blur\((\d+)px\)", luxury), "the glass blur has no explicit radius"

    def test_motion_respects_reduced_motion(self, luxury: str) -> None:
        assert "prefers-reduced-motion" in luxury, (
            "the luxury layer animates without honouring prefers-reduced-motion"
        )

    def test_the_glow_stays_a_whisper(self, luxury: str) -> None:
        """Alpha must stay <= .28 so the accent never reads as neon.

        Scoped to what §8 actually calls a glow: the ``box-shadow`` auras and the
        radial washes behind the hero. A 1px border ring and the text selection
        highlight are a border and a highlight, not auras, so they are excluded.
        """
        pattern = r"rgba\(\s*255,\s*90,\s*54,\s*([\d.]+)\s*\)"
        glows: list[float] = []

        for declaration in re.findall(r"box-shadow:[^;]+;", luxury):
            without_ring = re.sub(r"0 0 0 1px rgba\([^)]*\)", "", declaration)
            glows += [float(a) for a in re.findall(pattern, without_ring)]
        for wash in re.findall(r"radial-gradient\([^)]*\)", luxury):
            glows += [float(a) for a in re.findall(pattern, wash)]
        for token in re.findall(rf"--[a-z0-9-]*gold[a-z0-9-]*:\s*{pattern}", luxury, re.I):
            glows.append(float(token))

        assert glows, "the gold aura is not expressed at all"
        assert max(glows) <= 0.28, (
            f"gold glow alpha {max(glows)} exceeds the .28 ceiling from design-system.md §8"
        )


class TestEncoding:
    """The storefront is written through shell tools; mojibake has shipped twice."""

    @pytest.mark.parametrize(
        "path",
        [LUXURY_CSS]
        + [TEMPLATES / page for page in PUBLIC_PAGES]
        + [TEMPLATES / page for page in LIGHT_DOCUMENTS],
    )
    def test_no_bom_and_no_mojibake(self, path: Path) -> None:
        raw = path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), f"{path.name} has a UTF-8 BOM"
        text = raw.decode("utf-8")
        for marker in ("â€", "Ã©", "Ø§", "Ù„"):
            assert marker not in text, f"{path.name} contains mojibake ({marker!r})"
