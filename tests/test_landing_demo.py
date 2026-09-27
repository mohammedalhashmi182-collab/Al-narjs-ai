"""Guards for the interactive Social Media Lead demo on the landing page.

Rules enforced:
- every demo string is bilingual (Arabic first, English counterpart),
- no stray non-Latin scripts ever reach the page (a class of bug that already
  shipped CJK and Cyrillic fragments inside Arabic copy),
- the sample is labelled as illustrative and never presented as a real client,
- the demo adds no dependency and touches no backend route.
"""

from pathlib import Path
import re
import unicodedata

TEMPLATES = Path(__file__).resolve().parents[1] / "src" / "web" / "templates"
LANDING = TEMPLATES / "landing.html"

# Unicode blocks that must never appear in a Saudi/English landing page.
ALLOWED_ALPHA_BLOCKS = {"ARABIC", "LATIN"}

ARABIC = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
LATIN = re.compile(r"[A-Za-z]")

# Latin that is legitimate inside an Arabic sentence.
ALLOWED_LATIN_IN_AR = {
    "AI", "AG", "KSA", "SAR", "SEO", "FAQ", "CTA", "VR", "PM", "A", "B", "EN",
    "JavaScript", "Telegram", "Instagram", "TikTok", "Snapchat", "Meta",
    "Google", "YouTube", "Narjis", "Al", "OOTD",
}
# Latin that may only appear as a hashtag.
ALLOWED_LATIN_IN_AR_PREFIX = ("#", "@")


def _body() -> str:
    return LANDING.read_text(encoding="utf-8")


def _demo_js() -> str:
    """The demo data object and its wiring, bounded to avoid the rest of the page."""
    body = _body()
    return body[body.index("var DEMO_TABS"):body.index("var allAgents")]


def _demo_css() -> str:
    body = _body()
    return body[body.index("/* ---------- live demo"):body.index("/* ---------- trust strip")]


def test_demo_section_exists_with_wired_ids() -> None:
    body = _body()
    assert 'id="demo"' in body
    for element_id in (
        "demoBox", "demoPicker", "demoRun", "demoSteps",
        "demoTabs", "demoPanel", "demoBrief", "demoStatus", "demoAva",
    ):
        assert body.count(f'id="{element_id}"') == 1, f"{element_id} missing or duplicated"
        # the same id is read by exactly one getElementById call
        assert body.count(f"'{element_id}'") == 1, f"{element_id} is not read exactly once"


def test_no_stray_scripts_anywhere_in_landing() -> None:
    """CJK/Cyrillic fragments once shipped inside Arabic copy on this page."""
    offenders: list[str] = []
    for number, line in enumerate(_body().splitlines(), 1):
        for char in line:
            if not char.isalpha():
                continue
            try:
                block = unicodedata.name(char).split(" ")[0]
            except ValueError:  # pragma: no cover - unnamed char
                offenders.append(f"L{number}: unnamed {char!r}")
                continue
            if block not in ALLOWED_ALPHA_BLOCKS:
                offenders.append(f"L{number}: {block} {char!r} U+{ord(char):04X}")
    assert not offenders, f"stray scripts in landing.html: {offenders}"


def test_demo_copy_is_bilingual() -> None:
    """Every demo value must carry an Arabic and an English string."""
    demo = _demo_js()
    pairs = re.findall(r"\{\s*ar:\s*'((?:[^'\\]|\\.)*)'\s*,\s*en:\s*'((?:[^'\\]|\\.)*)'", demo)
    assert len(pairs) >= 40, f"expected a full bilingual demo dataset, found {len(pairs)} values"
    for ar, en in pairs:
        assert ar.strip(), "an Arabic demo value is empty"
        assert en.strip(), "an English demo value is empty"


def test_no_untranslated_latin_inside_arabic_demo_copy() -> None:
    """Latin words leaking into Arabic sentences (e.g. an English verb mid-clause)."""
    offenders: list[str] = []
    for match in re.finditer(r"\{\s*ar:\s*'((?:[^'\\]|\\.)*)'", _demo_js()):
        # JS escape sequences such as \n are not prose
        value = re.sub(r"\\[nrt]", " ", match.group(1))
        if not ARABIC.search(value):
            continue
        for token in re.findall(r"[A-Za-z][A-Za-z0-9._/-]*", value):
            if token in ALLOWED_LATIN_IN_AR:
                continue
            if token.startswith(ALLOWED_LATIN_IN_AR_PREFIX):
                continue
            offenders.append(f"{token!r} in {value[:70]!r}")
    assert not offenders, f"untranslated Latin inside Arabic demo copy: {offenders}"


def test_demo_is_labelled_illustrative_in_both_languages() -> None:
    """The sample must never read as a real client's result."""
    body = _body()
    section = body[body.index('id="demo"'):body.index("<!-- ==================== FEATURES")]
    assert "demo-note" in section
    assert "مثال توضيحي" in section, "Arabic illustrative disclaimer is missing"
    assert "illustrative sample" in section, "English illustrative disclaimer is missing"
    # the sample is not tied to a named real business
    assert "@" not in section.replace("data-lang", ""), "demo leaks a contact handle"


def test_demo_uses_no_external_dependency() -> None:
    demo = _demo_js() + _demo_css()
    for forbidden in ("import ", "require(", "fetch(", "XMLHttpRequest", "cdn.", "http", "<script src"):
        assert forbidden not in demo, f"demo must stay dependency-free, found {forbidden!r}"


def test_demo_does_not_fabricate_performance_claims() -> None:
    """No invented result badges inside the demo (the +38% class of bug)."""
    demo = _demo_js()
    assert "+38%" not in demo
    percentages = re.findall(r"\+\s*\d+\s*%", demo)
    assert not percentages, f"demo shows invented growth figures: {percentages}"
