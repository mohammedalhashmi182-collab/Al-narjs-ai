"""CSS <-> JavaScript contract guards.

Both bugs this file exists to prevent shipped as a 200 response with a healthy
status code, a correct DOM, and a completely unusable page. Neither was caught
by content tests, because the failure is visual: an element covers the page, or
an interaction silently does nothing.

The cause in every case was the same. A stylesheet was rewritten and a class
name was renamed on one side of the contract only:

- the preloader CSS was renamed ``.preloader.hide`` -> ``.preloader.done``
  while the JavaScript still added ``hide``, so the splash never left and the
  whole page stayed covered;
- ``.nav.stuck`` and ``.emp.awake`` were defined in CSS while the JavaScript
  toggled ``scrolled`` and ``woke``, so the nav never gained its scrolled state
  and waking an agent had no visual effect.

So the invariant enforced here is mechanical: every class the scripts toggle by
name must be defined by CSS the page actually loads. A rename on one side can no
longer land silently.
"""

from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / "src" / "web" / "templates"
CSS_DIR = ROOT / "src" / "web" / "static" / "css"

TAILWIND_MARKER = "cdn.tailwindcss.com"
EXTENDS_RE = re.compile(r"{%-?\s*extends\s+[\"']([^\"']+)[\"']")
STYLE_BLOCK_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.S | re.I)
CLASSLIST_RE = re.compile(r"classList\s*\.\s*(?:add|remove|toggle)\s*\(([^)]*)\)")
STRING_ARG_RE = re.compile(r"['\"]([A-Za-z_][A-Za-z0-9_-]*)['\"]")
DEFINES_RE = re.compile(r"\.(?P<cls>[A-Za-z_][A-Za-z0-9_-]*)(?![A-Za-z0-9_-])")

# Utilities that are not declared anywhere in this repo because the Tailwind
# CDN compiles them at runtime. They are only listed to document that their
# absence is understood, not accidental.
TAILWIND_UTILITIES = {
    "hidden", "flex", "opacity-40", "block", "grid", "inline", "none",
    "w-full", "h-full", "text-center", "font-bold", "rounded", "truncate",
}


def _tpl(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _template_css(path: Path) -> str:
    """Only the CSS the page can actually apply: its own <style> blocks."""
    return "\n".join(STYLE_BLOCK_RE.findall(_tpl(path)))


def _static_css() -> str:
    return "\n".join(
        f.read_text(encoding="utf-8", errors="ignore") for f in sorted(CSS_DIR.glob("*.css"))
    )


def _uses_tailwind(path: Path, _seen: frozenset = frozenset()) -> bool:
    """True when the page, or any template it extends, loads the Tailwind CDN."""
    if path.name in _seen:
        return False
    seen = _seen | {path.name}
    text = _tpl(path)
    if TAILWIND_MARKER in text:
        return True
    for parent in EXTENDS_RE.findall(text):
        parent_path = TEMPLATES_DIR / Path(parent).name
        if parent_path.is_file() and _uses_tailwind(parent_path, seen):
            return True
    return False


def _toggled_classes(text: str) -> set[str]:
    found: set[str] = set()
    for args in CLASSLIST_RE.findall(text):
        found.update(STRING_ARG_RE.findall(args))
    return found


def _defines(css: str, cls: str) -> bool:
    return any(m.group("cls") == cls for m in DEFINES_RE.finditer(css))


def _self_contained_templates() -> list[Path]:
    """Templates with no Tailwind in scope: every name they toggle must exist."""
    return sorted(
        p
        for p in TEMPLATES_DIR.rglob("*.html")
        if not _uses_tailwind(p) and _toggled_classes(_tpl(p))
    )


SELF_CONTAINED = _self_contained_templates()


def test_the_guard_actually_covers_the_landing_page() -> None:
    """If this file silently stopped scanning landing.html it would be useless."""
    names = {p.name for p in SELF_CONTAINED}
    assert "landing.html" in names, (
        "landing.html is no longer scanned by the contract test; the preloader "
        "regression it guards against would go unnoticed"
    )


@pytest.mark.parametrize("path", SELF_CONTAINED, ids=lambda p: p.name)
def test_js_toggled_classes_are_defined_in_css(path: Path) -> None:
    """Every class named in classList.add/remove/toggle must exist in CSS.

    A class defined only on one side of the contract is a silent no-op: the
    preloader that never leaves, the nav that never changes, the wake button
    that does nothing.
    """
    css = _template_css(path) + "\n" + _static_css()
    toggled = _toggled_classes(_tpl(path))
    missing = sorted(
        cls
        for cls in toggled
        if cls not in TAILWIND_UTILITIES and not _defines(css, cls)
    )
    assert not missing, (
        f"{path.name} toggles {missing} in JavaScript but never defines them in "
        "CSS, so those state changes are no-ops. Define the class, or use the "
        "name the CSS already declares."
    )


# ---------------------------------------------------------------------------
# The preloader: an opaque full-screen cover must always be escapable
# ---------------------------------------------------------------------------

PRELOADER_CLEAR_CLASS_RE = re.compile(
    r"\.preloader\.(?P<cls>[A-Za-z0-9_-]+)\s*\{[^}]*visibility\s*:\s*hidden"
)


def test_preloader_is_dismissible() -> None:
    """The class the scripts add to #preloader must be one the CSS honours."""
    path = TEMPLATES_DIR / "landing.html"
    text = _tpl(path)
    css = _template_css(path)

    holder = re.search(r"(\w+)\s*=\s*document\.getElementById\('preloader'\)", text)
    assert holder, "the template no longer looks up #preloader from JavaScript"
    added: set[str] = set()
    for call in re.findall(rf"{holder.group(1)}\.classList\.add\(([^)]*)\)", text):
        added.update(STRING_ARG_RE.findall(call))

    assert added, "could not find the code that dismisses the preloader"
    honoured = {
        cls
        for cls in added
        if re.search(
            rf"\.preloader\.{re.escape(cls)}\s*\{{[^}}]*visibility\s*:\s*hidden", css
        )
    }
    assert added & honoured, (
        f"the scripts dismiss the preloader with {sorted(added)} but the CSS "
        f"honours none of them; the splash screen then covers the page forever"
    )


def test_preloader_has_pure_css_failsafe() -> None:
    """Even with JavaScript broken the preloader must not trap the page.

    The previous version relied on a `load` listener and a timeout. Both are
    JavaScript: if the script fails to parse, is blocked, or never runs, nothing
    ever cleared the splash. A zero-duration animation with a delay forces the
    hidden state from CSS alone.
    """
    css = _template_css(TEMPLATES_DIR / "landing.html")
    base = re.search(r"(?m)^\.preloader\s*\{(.*?)\}", css, re.S)
    assert base, "no .preloader rule found"
    declarations = base.group(1)
    assert "animation:" in declarations, (
        ".preloader needs a CSS animation that forces the hidden state, so a "
        "JavaScript failure cannot leave the splash covering the page"
    )
    assert "forwards" in declarations, (
        "the failsafe animation must use fill-mode `forwards`, otherwise the "
        "preloader returns to its visible state"
    )
    failsafe = re.search(
        r"@keyframes\s+[A-Za-z0-9_-]*[Ff]ail[A-Za-z0-9_-]*\s*\{.*?visibility\s*:\s*hidden",
        css,
        re.S,
    )
    assert failsafe, (
        "the failsafe keyframes must set visibility:hidden; without it the "
        "preloader is still painted over the page once the animation ends"
    )
    assert "pointer-events:none" in declarations or "pointer-events:none" in css, (
        "a hidden preloader must stop intercepting clicks, otherwise the page "
        "looks fine but nothing is clickable"
    )


def test_launch_bar_dismissal_persists() -> None:
    """Closing the offer must survive a reload.

    The dismissal was stored in localStorage but nothing in CSS read it, so the
    bar came back on every visit and the close button was the only state that
    existed for a few milliseconds.
    """
    css = _template_css(TEMPLATES_DIR / "landing.html")
    assert re.search(r"body:not\(\.launch-on\)\s+\.launch-bar\s*\{[^}]*display\s*:\s*none", css), (
        "the launch bar must be hidden until the script confirms it, so a "
        "dismissal in localStorage actually holds across reloads"
    )
    text = _tpl(TEMPLATES_DIR / "landing.html")
    assert "narjis-promo-dismissed" in text
    assert re.search(r"classList\.remove\('launch-on'\)", text), (
        "dismissing must remove the state that reveals the bar"
    )


# ---------------------------------------------------------------------------
# Nothing may cover the viewport without a way out
# ---------------------------------------------------------------------------

RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}")
FULL_BLEED_RE = re.compile(r"inset\s*:\s*0|top\s*:\s*0[^;]*;?\s*(right|bottom|left)\s*:\s*0")
OPAQUE_BG_RE = re.compile(
    r"background(?:-color)?\s*:\s*(?!none\b|transparent\b)[^;}]+"
)


def _rules(css: str) -> list[tuple[str, str]]:
    return [(m.group(1).strip(), m.group(2)) for m in RULE_RE.finditer(css)]


def test_no_opaque_full_viewport_cover_without_a_way_out() -> None:
    """A fixed, opaque, full-viewport layer must always be escapable.

    This is the shape of the outage that shipped: `.preloader` covered the
    viewport with an opaque background, the only way to clear it was a
    JavaScript class the stylesheet no longer honoured, and the site answered
    200 with a blank page. Any such layer has to carry its own escape in CSS.
    """
    for path in SELF_CONTAINED:
        css = _template_css(path)
        rules = _rules(css)
        for selector, declarations in rules:
            flat = declarations.replace(" ", "")
            if "position:fixed" not in flat:
                continue
            if not FULL_BLEED_RE.search(declarations):
                continue
            if not OPAQUE_BG_RE.search(declarations):
                continue
            if re.search(r"z-index:-", flat):
                # painted behind the content: decoration, not a cover
                continue

            classes = set(DEFINES_RE.findall(selector))
            assert classes, f"{path.name}: full-viewport layer on an element selector"
            escaped = False
            for other_selector, other_declarations in rules:
                if other_selector == selector:
                    continue
                if not (classes & set(DEFINES_RE.findall(other_selector))):
                    continue
                flat = other_declarations.replace(" ", "")
                if "visibility:hidden" in flat or "opacity:0" in flat:
                    escaped = True
                    break
            assert escaped, (
                f"{path.name}: {selector} is a fixed opaque full-viewport cover "
                f"(classes {sorted(classes)}) with no CSS rule that can hide it. "
                "A visitor with a broken script can never see the page."
            )
