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
def test_voice_page_has_original_wave_and_keeps_speech_engine(lang):
    with TestClient(app) as client:
        page = client.get(f"/{lang}/voice")
        css = client.get("/static/css/voice-narjis-wave.css")
        existing_css = client.get("/static/css/voice-aurora.css")
        app_js = client.get("/static/js/voice-live-app.js")
    assert page.status_code == css.status_code == existing_css.status_code == app_js.status_code == 200
    assert len(page.content) < 16_000
    assert 'id="intro"' not in page.text
    assert 'id="orb"' not in page.text
    assert "voice-orb.js" not in page.text
    assert "voice-narjis-wave.css" in page.text
    assert 'class="voice-stage-ribbon"' in page.text
    assert page.text.count("--ng-wave-index:") >= 24
    assert 'id="vid"' in page.text
    assert 'id="start"' in page.text
    assert 'id="chatPanel" hidden' in page.text
    assert 'id="wave"' in page.text
    assert "/static/js/voice-live-app.js" in page.text
    assert "brand-narjis-gate.svg" in page.text
    assert "ng-voice-flow" in css.text
    assert "#vid.talk" in css.text
    assert "#vid.listen" in css.text
    assert "prefers-reduced-motion" in css.text
    assert "window.__outLvl" in app_js.text
    assert "window.__inLvl" in app_js.text
    assert "__voiceInAnalyser" in app_js.text
    assert "__voiceOutAnalyser" in app_js.text
    assert 'XAI_API_KEY' not in page.text
    assert "xai-client-secret" not in page.text
    assert "unpkg" not in page.text and "jsdelivr" not in page.text and "cdnjs" not in page.text


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
def test_voice_wave_browser_works_without_mic_permission_or_overlay(lang, width):
    from playwright.sync_api import sync_playwright

    with TestClient(app) as client, sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("BROWSER_EXECUTABLE_PATH"))
        ctx = browser.new_context(viewport={"width": width, "height": 844}, reduced_motion="reduce")
        ctx.add_init_script(
            "if (navigator.mediaDevices) { navigator.mediaDevices.getUserMedia = () => { "
            "window.__micAsks = (window.__micAsks || 0) + 1; return Promise.reject(new Error('mic')); }; }"
        )
        def serve(route):
            url = urlsplit(route.request.url)
            r = client.request(
                route.request.method,
                url.path + ("?" + url.query if url.query else ""),
                content=route.request.post_data_buffer,
            )
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
        assert page.locator(".voice-stage-wordmark").is_visible()
        assert page.locator(".voice-stage-ribbon i").count() >= 24
        assert page.locator("#start").is_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        assert page.evaluate("() => window.__micAsks || 0") == 0
        assert not errors
        ctx.close()
        browser.close()


def test_voice_logo_files_are_real_images():
    with TestClient(app) as client:
        emblem = client.get("/static/brand/alnarjis-emblem.png")
        emblem_webp = client.get("/static/brand/alnarjis-emblem.webp")
        lockup = client.get("/static/brand/alnarjis-logo.png")
        lockup_webp = client.get("/static/brand/alnarjis-logo.webp")
        icon = client.get("/static/brand/alnarjis-favicon-32.png")
        apple = client.get("/static/brand/alnarjis-apple-touch.png")
        home = client.get("/ar/home")
    for response in (emblem, emblem_webp, lockup, lockup_webp, icon, apple):
        assert response.status_code == 200
        assert len(response.content) > 400
    assert emblem.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert emblem.content[25] == 6
    assert lockup.content[25] == 6
    assert emblem_webp.content[:4] == b"RIFF" and emblem_webp.content[8:12] == b"WEBP"
    assert lockup_webp.content[8:12] == b"WEBP"
    assert "voice-emblem.js" not in home.text
    assert "alnarjis-emblem" not in home.text


@pytest.mark.skipif(os.environ.get("RUN_BROWSER_TESTS") != "1", reason="requires Chromium CI")
def test_voice_wave_reacts_to_call_state_without_3d_rendering():
    from playwright.sync_api import sync_playwright

    with TestClient(app) as client, sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("BROWSER_EXECUTABLE_PATH"))
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        def serve(route):
            url = urlsplit(route.request.url)
            r = client.request(route.request.method, url.path,
                               content=route.request.post_data_buffer)
            route.fulfill(status=r.status_code, body=r.content,
                          headers={"content-type": r.headers.get("content-type", "text/plain")})
        ctx.route("**/*", lambda route: route.abort())
        ctx.route("http://testserver/**", serve)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto("http://testserver/ar/voice")
        assert page.locator(".voice-stage-ribbon i").count() == 36
        before = page.locator(".voice-stage-ribbon i").first.evaluate(
            "(node) => getComputedStyle(node).animationDuration"
        )
        page.locator("#vid").evaluate("(el) => el.classList.add('talk')")
        after = page.locator(".voice-stage-ribbon i").first.evaluate(
            "(node) => getComputedStyle(node).animationDuration"
        )
        assert before == "2.6s" and after == "0.45s"
        assert not errors
        ctx.close()
        browser.close()
