"""Dark-canvas theme corrections found by reading the live storefront.

Every rule here was a defect that was visible on the production page while the
suite stayed green, which is the whole reason this file exists:

* the comparison table highlighted its own winning column with the *light*
  palette tokens, so on the dark canvas that column was a pale grey block with
  unreadable text -- in the one section whose only job is to be read;
* plan names carry the English label in `class="en-nm"` with **no** `data-lang`
  attribute, so the page-wide language switch could never hide it and each card
  rendered as "نمو الأعمالBusiness Growth";
* the hero headline ran to an 80px line, breaking one sentence into six lines and
  pushing the call to action under the fold;
* the gradient keyword in the headline relied on `color: transparent` alone,
  which double-drew the glyph in Chromium and clipped its descenders.

The floating-metric-card experiment is asserted *absent* on purpose. The
reference boards float glass cards around the hero visual, but a full-width
two-column hero has no free margin: the cards clipped off-screen and crossed the
console. The same glass language now lives in flow on the hero stat row, so this
test fails if someone re-adds an absolute overlay.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services import catalog

REPO_ROOT = Path(__file__).resolve().parents[1]
LUXURY_CSS = REPO_ROOT / "src" / "web" / "static" / "css" / "narjis-luxury.css"
LANDING = REPO_ROOT / "src" / "web" / "templates" / "landing.html"


@pytest.fixture(scope="module")
def css() -> str:
    return LUXURY_CSS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def rule_body(css: str, selector: str, occurrence: int = 0) -> str:
    """Return the declarations of a rule matching ``selector``.

    ``selector`` is a plain CSS selector, e.g. ``"body.luxury .why .us"``.
    It is escaped here, once, and whitespace is normalised so the call sites do
    not have to hand-write regular expressions.

    ``occurrence`` matters because a component is often styled twice: once for
    the component and again inside a ``prefers-reduced-motion`` block. Asking for
    the last match would return the override, not the styling under test.
    """
    pattern = r"\s+".join(re.escape(part) for part in selector.split())
    matches = re.findall(rf"[^{{}}]*{pattern}\s*\{{([^}}]*)\}}", css)
    assert matches, f"no rule found for {selector}"
    return matches[occurrence]


# --------------------------------------------------------------------------
# the comparison table must be readable on the canvas it is drawn on
# --------------------------------------------------------------------------


def test_winning_column_is_not_painted_with_light_tokens(css: str) -> None:
    body = rule_body(css, "body.luxury .why .us")
    assert "background" in body
    # a light-palette wash (the old --green-wash) is what made it unreadable
    assert "green-wash" not in body


def test_winning_column_text_is_high_contrast_on_dark(css: str) -> None:
    """The winning *cell* text must be light enough to read on the dark canvas.

    The column *header* is deliberately the accent, not light text, so it is not
    checked here; `test_luxury_dark` owns the accent's contrast instead.
    """
    cell = rule_body(css, "body.luxury .why .us", occurrence=0)
    colour = re.search(r"color:\s*(#[0-9a-fA-F]{3,6})", cell)
    assert colour, f"no explicit hex colour in: {cell}"
    value = colour.group(1).lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    red, green, blue = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    assert luminance > 180, f"text too dark for a dark canvas: #{value}"


def test_winning_column_header_is_the_accent(css: str) -> None:
    head = rule_body(css, "body.luxury .why thead th.us", occurrence=0)
    assert re.search(r"color:\s*#ff5a36", head, re.I), (
        "the winning header lost the action accent"
    )


# --------------------------------------------------------------------------
# one language at a time
# --------------------------------------------------------------------------


def test_plan_english_name_is_language_aware(css: str) -> None:
    arabic_mode = rule_body(css, 'body[data-lang="ar"] .pc .en-nm')
    english_mode = rule_body(css, 'body[data-lang="en"] .pc .en-nm')
    assert "display: none" in arabic_mode
    assert "display: inline" in english_mode


# Text that is intentionally never translated. Each entry earns its place: the
# brand wordmark, the console status pills, and machine identifiers are the same
# in both languages, so demanding a data-lang on them would be wrong.
NEVER_TRANSLATED = {
    "AL-NARJIS AI",
    "LIVE",
    "IDLE",
    "النرجس",  # the brand is written in Arabic in both locales
}
JINJA = re.compile(r"[{%}]")
EMPLOYEE_NO = re.compile(r"^[A-Z]{1,3}-\d{3,4}$")


class _LangSpanScanner(HTMLParser):
    """Collect spans that carry prose but declare no language, and sit outside
    any element that already declares one.

    A regex cannot tell "Arabic text nested inside an Arabic span" from "Arabic
    text sitting at the top level", and the first kind is correct. This walks the
    document instead.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._open: list[tuple[str, bool, bool]] = []  # tag, has_lang, in_lang
        self._capture: list[tuple[str, bool, bool]] = []
        self._buffer: list[str] = []
        self.offenders: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        has_lang = any(k == "data-lang" for k, _ in attrs)
        in_lang = has_lang or any(entry[2] for entry in self._open)
        self._open.append((tag, has_lang, in_lang))
        if tag == "span" and not in_lang:
            self._capture.append((tag, has_lang, in_lang))
            self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        if self._capture and tag == "span":
            text = "".join(self._buffer).strip()
            if text and not JINJA.search(text) and not EMPLOYEE_NO.match(text):
                self.offenders.append(text)
            self._capture = []
            self._buffer = []
        for index in range(len(self._open) - 1, -1, -1):
            if self._open[index][0] == tag:
                del self._open[index:]
                break

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buffer.append(data)


def test_no_translated_copy_lacks_a_data_lang() -> None:
    """`en-nm` was the only one; this catches the next one being added.

    A span carrying prose must declare its language, otherwise the page-wide
    language switch cannot hide it and both languages render at once. Spans
    nested inside an element that already declares a language are fine, which is
    why this walks the document instead of matching markup with a pattern.
    """
    scanner = _LangSpanScanner()
    scanner.feed(LANDING.read_text(encoding="utf-8"))
    offenders = [t for t in scanner.offenders if t not in NEVER_TRANSLATED]
    assert not offenders, f"copy without a language declared: {offenders[:8]}"


# --------------------------------------------------------------------------
# hero scale
# --------------------------------------------------------------------------


def test_hero_headline_is_not_oversized(css: str) -> None:
    body = rule_body(css, "body.luxury .lux-hero h1")
    clamp = re.search(r"font-size:\s*clamp\([^)]*\)", body)
    assert clamp, "the luxury layer no longer caps the hero headline"
    sizes = [float(x) for x in re.findall(r"([\d.]+)rem", clamp.group(0))]
    assert sizes, clamp.group(0)
    # the retired 5rem ceiling wrapped one sentence into six lines
    assert max(sizes) <= 4.0, f"hero ceiling regressed to {max(sizes)}rem"


def test_gradient_keyword_cannot_double_draw(css: str) -> None:
    body = rule_body(css, "body.luxury .grad")
    assert "-webkit-text-fill-color" in body, "Chromium needs the prefixed fill"
    assert "background-clip" in body
    # inline-block plus inline padding keeps ascenders and descenders whole
    assert "display: inline-block" in body
    assert "padding-inline" in body


# --------------------------------------------------------------------------
# glass metric cards, in flow
# --------------------------------------------------------------------------


def test_hero_stat_cards_use_the_glass_treatment(css: str) -> None:
    # occurrence 0: the component itself, not its reduced-motion override
    body = rule_body(css, "body.luxury .lux-hero .stat", occurrence=0)
    assert "backdrop-filter" in body
    assert "border-radius" in body
    assert "box-shadow" in body


def test_hero_stat_numbers_are_bound_to_the_catalogue(client: TestClient) -> None:
    r = client.get("/home")
    assert r.status_code == 200
    assert f'data-target="{catalog.DIVISION_COUNT}"' in r.text
    assert f'data-target="{catalog.AGENT_COUNT}"' in r.text


def test_absolutely_positioned_hero_overlay_does_not_return() -> None:
    """The rejected floating-card variant clipped off-screen; keep it out."""
    landing = LANDING.read_text(encoding="utf-8")
    assert "lux-floater" not in landing
    assert "lux-floaters" not in landing


def test_motion_is_reduced_when_asked(css: str) -> None:
    reduced = css.split("prefers-reduced-motion: reduce")
    assert len(reduced) > 1, "the luxury layer has no reduced-motion block"
    assert ".lux-hero .stat" in reduced[-1]