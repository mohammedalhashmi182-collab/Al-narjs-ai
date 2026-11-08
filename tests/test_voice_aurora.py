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



def test_voice_prices_always_come_from_checkout_catalog(monkeypatch):
    from src.services.catalog import PACKAGES, PACKAGE_ORDER

    script = voice_live.session_instructions("ar")
    for key in PACKAGE_ORDER:
        plan = PACKAGES[key]
        sar = f'{plan["amount"] / 100:,.2f}'.removesuffix(".00")
        assert f'{plan["name"]} ({plan["name_en"]}) {sar} SAR per month' in script
    assert "before any applicable VAT" in script

    # A future catalog update must instantly appear in the voice advisor,
    # without a developer editing a second, stale price list.
    monkeypatch.setitem(PACKAGES["bidaya"], "amount", 82500)
    revised = voice_live.session_instructions("en")
    assert "البداية (Starter) 825 SAR per month" in revised
    assert "البداية (Starter) 790 SAR per month" not in revised


def test_invalid_catalog_price_fails_closed_for_voice(monkeypatch):
    from src.services.catalog import PACKAGES

    monkeypatch.setitem(PACKAGES["bidaya"], "amount", -100)
    with pytest.raises(ValueError, match="canonical package"):
        voice_live.session_instructions("ar")


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
