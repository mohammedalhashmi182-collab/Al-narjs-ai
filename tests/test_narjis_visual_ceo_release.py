"""NARJIS premium release: browser-entry and zero-cost visual preview guards.

Focused tests intentionally do not call Gemini or paid API providers.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "web"


@pytest.mark.parametrize("url", ["/ar/home", "/en/home"])
def test_ceo_hero_is_real_interactive_form(url):
    from src.main import app

    with TestClient(app) as client:
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
    assert "window.NarjisPreview.render(" in landing
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


@pytest.mark.skipif(
    __import__("os").environ.get("RUN_BROWSER_TESTS") != "1",
    reason="requires Chromium in GitHub Actions",
)
@pytest.mark.parametrize(
    "lang,width,problem",
    [
        ("ar", 390, "عندي عيادة وأحتاج تنظيم مواعيد المرضى واستفساراتهم اليومية"),
        ("en", 1280, "I run an online store and want to follow up customer carts and orders"),
    ],
)
def test_ceo_visual_blueprint_in_real_browser(lang, width, problem):
    """End-to-end diagnosis display with deterministic, no-cost mock CEO response."""
    import json
    import os
    from urllib.parse import urlsplit

    from fastapi.testclient import TestClient
    from playwright.sync_api import sync_playwright

    from src.main import app

    response = {
        "diagnosis_ar": "نحتاج ترتيب الاستفسارات والمتابعة وتوزيع مهام الفريق.",
        "diagnosis_en": "The business needs enquiry triage and reliable follow-up.",
        "agent_count": 1,
        "agents": [{
            "no": "02", "slug": "sales", "title_ar": "وكيل المبيعات",
            "title_en": "Sales agent", "why_ar": "تأهيل الاستفسارات",
            "why_en": "Qualify enquiries",
        }],
        "plan": {
            "key": "bidaya", "name": "البداية", "name_en": "Starter",
            "monthly_price": 790, "price": 790,
            "total_halalas": 79000, "addons": 0,
        },
        "cta": {"subscribe": "/portal"},
        "offer": True,
    }
    with TestClient(app) as client, sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("BROWSER_EXECUTABLE_PATH"))
        ctx = browser.new_context(
            viewport={"width": width, "height": 844},
            reduced_motion="reduce",
            accept_downloads=True,
        )

        def serve(route):
            parsed = urlsplit(route.request.url)
            if parsed.path == "/api/ceo/consult":
                route.fulfill(status=200, content_type="application/json", body=json.dumps(response))
                return
            r = client.request(
                route.request.method,
                parsed.path + ("?" + parsed.query if parsed.query else ""),
                content=route.request.post_data_buffer,
            )
            route.fulfill(status=r.status_code, body=r.content,
                          headers={"content-type": r.headers.get("content-type", "text/plain")})

        ctx.route("**/*", lambda route: route.abort())
        ctx.route("http://testserver/**", serve)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.goto(f"http://testserver/{lang}/home")
        assert page.locator("#ngHeroForm").is_visible()
        page.locator("#ngHeroProblem").fill(problem)
        page.locator("#ngHeroForm button[type=submit]").click()
        page.locator("#ceoWorkspace svg").wait_for(timeout=12000)
        assert page.locator("#ceoWorkspace .ng-preview-card").count() == 3
        assert page.locator("#ceoWorkspace .ng-agent-chips").inner_text()
        assert page.locator("#ceoWorkspace .ng-preview-disclaimer").is_visible()
        assert page.locator("#ceoWorkspace svg").evaluate(
            "(el) => el.getAttribute('role') === 'img'"
        )
        with page.expect_download() as download_info:
            page.locator("#ceoWorkspace .ng-download-blueprint").click()
        assert download_info.value.suggested_filename.endswith(".svg")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        assert not errors, errors
        ctx.close()
        browser.close()
