"""NARJIS premium release: browser-entry and zero-cost visual preview guards.

Focused tests intentionally do not call Gemini or paid API providers.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "web"


@pytest.mark.parametrize("url", ["/ar/home", "/en/home"])
def test_ceo_hero_is_real_interactive_form(client, url):
    page = client.get(url)
    assert page.status_code == 200
    html = page.text
    assert 'id="ngHeroForm"' in html
    assert 'id="ngHeroProblem"' in html
    assert 'id="ceoForm"' in html
    assert 'id="ceoWorkspace"' in html
    assert "/static/js/narjis-client-workspace.js" in html
    assert "data-ng-example=" in html
    assert 'action="/api/ceo/consult"' in html


def test_workspace_svg_is_generated_from_real_ceo_result():
    landing = (WEB / "templates" / "landing.html").read_text(encoding="utf-8")
    js = (WEB / "static" / "js" / "narjis-client-workspace.js").read_text(encoding="utf-8")
    assert "window.NarjisPreview.render(" in landing
    assert "renderWorkspacePreview(r, box.value)" in landing
    assert "response.agents" in js
    assert "response.diagnosis_ar" in js
    assert "response.diagnosis_en" in js
    assert "createBlueprint(" in js
    assert "new XMLSerializer()" in js
    assert "replaceChildren(" in js
    assert "innerHTML" not in js
    assert "api_key" not in js.lower()
    assert "fetch(" not in js
    assert "mailto:" not in landing


def test_owner_console_retains_real_metrics_and_links():
    owner = (WEB / "templates" / "company.html").read_text(encoding="utf-8")
    assert 'class="ng-owner-hero"' in owner
    assert 'id="kpi-revenue"' in owner
    assert 'id="kpi-leads"' in owner
    assert 'id="rev-verified"' in owner
    assert 'href="/acquisition"' in owner
    assert 'href="/executions"' in owner
    assert "narjis-owner-next" in owner


def test_new_client_script_parses_in_node():
    if not shutil.which("node"):
        pytest.skip("Node.js is not installed")
    script = WEB / "static" / "js" / "narjis-client-workspace.js"
    check = subprocess.run(
        ["node", "--check", str(script)],
        capture_output=True,
        text=True,
        timeout=12,
        check=False,
    )
    assert check.returncode == 0, check.stderr
