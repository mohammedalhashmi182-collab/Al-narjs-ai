"""Regression: content must never be left invisible by decorative CSS/JS."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REFRESH = ROOT / "src/web/static/css/narjis-refresh.css"
LANDING = ROOT / "src/web/templates/landing.html"
MAX_FALLBACK_MS = 3000


def _rules(css: str):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"@media[^{]*\{", "", css)  # flatten one level of @media
    return re.findall(r"([^{}]+)\{([^{}]*)\}", css)


def _targets_grid(selector: str) -> bool:
    # last compound of the selector carries the .grid class: `.grid`, `main .grid`,
    # `.x > .grid`, `div.grid` all style Tailwind's .grid utility elements.
    last = re.split(r"[\s>+~]+", selector.strip())[-1]
    return re.search(r"\.grid(?![\w-])", last) is not None


@pytest.mark.parametrize("sel,hit", [
    (".grid", True), ("main .grid", True), (".x .grid", True), (".x>.grid", True),
    ("div.grid", True), (".grid-cols-2", False), (".grid .card", False), (".mesh", False),
])
def test_grid_selector_matcher(sel, hit):
    assert _targets_grid(sel) is hit


def test_refresh_css_does_not_dim_tailwind_grid_utility():
    for sel, body in _rules(REFRESH.read_text(encoding="utf-8")):
        for s in sel.split(","):
            if _targets_grid(s):
                assert not re.search(r"(^|;|\s)opacity\s*:", body), f"{s.strip()} sets opacity: {body}"


def _reveal_js() -> str:
    html = LANDING.read_text(encoding="utf-8")
    m = re.search(r"var rvs = .*?setTimeout\(revealAll,\s*\d+\);", html, flags=re.S)
    assert m, "reveal block not found in landing.html"
    return m.group(0)


def test_fallback_delay_is_at_most_3s():
    m = re.search(r"setTimeout\(revealAll,\s*(\d+)\)", _reveal_js())
    assert m and 0 < int(m.group(1)) <= MAX_FALLBACK_MS


NODE_HARNESS = r"""
const els = [0, 1, 2, 3].map(i => ({ top: i === 0 ? 100 : 5000 + i * 900, cls: new Set(['rv']),
  classList: null, getBoundingClientRect() { return { top: this.top }; } }));
els.forEach(e => e.classList = { add: c => e.cls.add(c), contains: c => e.cls.has(c) });
const listeners = {}, timers = [];
const document = { querySelectorAll: () => els };
const window = { innerHeight: 844, addEventListener: (n, f) => (listeners[n] = f) };
class IntersectionObserver { observe() {} unobserve() {} }
window.IntersectionObserver = IntersectionObserver;
const setTimeout = (f, ms) => timers.push([f, ms]);
(function () { %s
  const vis = () => els.filter(e => e.cls.has('in')).length;
  const out = { afterInit: vis(), hasLoad: !!listeners.load, hasPrint: !!listeners.beforeprint };
  timers.forEach(([f]) => f());
  out.afterFallback = vis(); out.total = els.length; out.delays = timers.map(t => t[1]);
  console.log(JSON.stringify(out));
})();
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_reveal_all_actually_reveals_every_rv():
    js = NODE_HARNESS % _reveal_js()
    res = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True,
                                    check=True, timeout=20).stdout)
    assert res["afterInit"] == 1          # only the on-screen element at first
    assert res["hasLoad"] and res["hasPrint"]
    assert res["afterFallback"] == res["total"] == 4
    assert all(d <= MAX_FALLBACK_MS for d in res["delays"])
