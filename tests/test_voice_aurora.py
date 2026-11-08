"""Voice UI release acceptance, no vendor keys and no customer data."""
from pathlib import Path
import os
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services import voice_live


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src/web/static"


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_voice_page_is_small_and_has_no_fullscreen_intro_or_sphere(lang):
    with TestClient(app) as client:
        result = client.get(f"/{lang}/voice")
        css = client.get("/static/css/voice-aurora.css")
        js = client.get("/static/js/voice-ribbon.js")
    assert result.status_code == css.status_code == js.status_code == 200
    assert len(result.content) < 12_000, "Do not inline multi-hundred-kilobyte legacy CSS"
    assert 'id="intro"' not in result.text
    assert 'id="orb"' not in result.text
    assert 'id="ribbon"' in result.text
    assert 'id="vid"' in result.text
    assert 'id="start"' in result.text
    assert 'id="chatPanel" hidden' in result.text
    assert 'id="wave"' in result.text
    assert "/static/js/voice-live-app.js" in result.text
    assert "/static/js/voice-ribbon.js" in result.text
    assert "voice-aurora.css" in result.text
    assert "voice-ribbon" in css.text
    assert "prefers-reduced-motion" in css.text
    assert "window.__outLvl" in js.text
    assert "window.__inLvl" in js.text
    assert "requestAnimationFrame" in js.text
    assert 'XAI_API_KEY' not in result.text
    assert "xai-client-secret" not in result.text


def test_voice_published_agent_override_is_honest_and_intake_oriented():
    script = voice_live.session_instructions()
    assert "Al-Narjis AI chief executive" in script
    assert "Ask one useful follow-up question at a time" in script
    assert "never claim an agent" in script
    assert "have verified system evidence" in script
    assert "must be provided voluntarily" in script
    assert "NEVER say you are Grok" in script
    assert "Do not request passwords" in script


@pytest.mark.skipif(os.environ.get("RUN_BROWSER_TESTS") != "1", reason="requires Chromium CI")
@pytest.mark.parametrize("lang,width", [("ar", 390), ("en", 1280)])
def test_voice_aurora_browser_works_before_call_without_overlay(lang, width):
    from playwright.sync_api import sync_playwright

    with TestClient(app) as client, sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("BROWSER_EXECUTABLE_PATH"))
        ctx = browser.new_context(viewport={"width": width, "height": 844}, reduced_motion="reduce")
        def serve(route):
            url = urlsplit(route.request.url)
            r = client.request(route.request.method, url.path + ("?" + url.query if url.query else ""),
                               content=route.request.post_data_buffer)
            route.fulfill(status=r.status_code, body=r.content,
                          headers={"content-type": r.headers.get("content-type", "text/plain")})
        ctx.route("**/*", lambda route: route.abort())
        ctx.route("http://testserver/**", serve)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://testserver/{lang}/voice")
        assert page.locator("#intro").count() == 0
        assert page.locator("#orb").count() == 0
        assert page.locator("#ribbon").is_visible()
        assert page.locator("#start").is_visible()
        assert page.locator("#start").is_enabled() or page.locator("#start").is_disabled()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        assert page.locator("#ribbon").evaluate("(el) => el.width > 0 && el.height > 0")
        assert not errors
        ctx.close()
        browser.close()
