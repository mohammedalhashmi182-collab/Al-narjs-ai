"""Regression: content must never be left invisible by decorative CSS/JS."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFRESH = ROOT / "src/web/static/css/narjis-refresh.css"
LANDING = ROOT / "src/web/templates/landing.html"


def _rules(css: str):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return re.findall(r"([^{}]+)\{([^{}]*)\}", css)


def test_refresh_css_does_not_dim_tailwind_grid_utility():
    # .grid is a Tailwind layout utility (#pkg-grid in /portal); a bare .grid
    # selector carrying opacity dims the plan cards.
    for sel, body in _rules(REFRESH.read_text(encoding="utf-8")):
        sels = [s.strip() for s in sel.split(",")]
        if ".grid" in sels:
            assert "opacity" not in body, f"bare .grid sets opacity: {body}"


def test_landing_reveal_has_failsafe_and_initial_viewport_reveal():
    js = LANDING.read_text(encoding="utf-8")
    assert "revealAll" in js and "setTimeout(revealAll" in js
    assert "beforeprint" in js
    assert "getBoundingClientRect().top < window.innerHeight" in js
