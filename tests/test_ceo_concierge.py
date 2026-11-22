"""CEO concierge: the AI CEO greets in the hero and shows an initial offer in place.

Static and server-rendered guards; no model or paid provider is called.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "web"
JS = WEB / "static" / "js" / "narjis-ceo-concierge.js"
CSS = WEB / "static" / "css" / "narjis-concierge.css"


@pytest.mark.parametrize("url,greeting", [
    ("/ar/home", "أنا الرئيس التنفيذي الذكي"),
    ("/en/home", "I am the AI CEO"),
])
def test_hero_renders_the_concierge(url, greeting):
    from src.main import app

    with TestClient(app) as client:
        html = client.get(url).text
    assert 'id="ngConcierge"' in html and 'id="ngcThread"' in html and 'id="ngcQuick"' in html
    assert greeting in html
    assert 'data-wa-href="https://wa.me/966552978753"' in html
    assert "/static/js/narjis-ceo-concierge.js" in html
    assert "/static/css/narjis-concierge.css" in html
    assert 'id="openAssistant"' not in html and 'id="siteAssistant"' not in html
    # the CEO desk is still a real, non-JS form posting to the consult API
    assert 'id="ngHeroForm"' in html and 'action="/api/ceo/consult"' in html


def test_concierge_script_is_safe_and_never_invents_prices():
    js = JS.read_text(encoding="utf-8")
    assert "innerHTML" not in js
    assert "/api/ceo/consult" in js
    assert "api_key" not in js.lower()
    # prices only ever come from the API response
    for literal in ("790", "1490", "1,490", "2990", "2,990"):
        assert literal not in js
    assert "monthly_price" in js and "total_sar" in js
    assert "sessionStorage" in js  # stays with the visitor across reloads
    assert "window.NarjisCEO" in js


def test_landing_exposes_render_for_the_concierge():
    landing = (WEB / "templates" / "landing.html").read_text(encoding="utf-8")
    assert "window.NarjisCEO = { render: render };" in landing
    assert "opts && opts.quiet" in landing


def test_concierge_css_respects_identity_and_motion():
    css = CSS.read_text(encoding="utf-8").lower()
    assert "#ff5a36" in css
    for banned in ("purple", "violet", "lavender", "#7a5cb8", "#f4c430", "#4f7942"):
        assert banned not in css
    assert "prefers-reduced-motion" in css
    assert "border-radius:20px" in css and "8px" in css


def test_concierge_script_parses_in_node():
    if not shutil.which("node"):
        pytest.skip("Node.js is not installed")
    check = subprocess.run(["node", "--check", str(JS)], capture_output=True, text=True, timeout=12, check=False)
    assert check.returncode == 0, check.stderr
