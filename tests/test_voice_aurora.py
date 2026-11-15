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
def test_voice_page_centers_a_monochrome_orb_and_emblem(lang):
    with TestClient(app) as client:
        result = client.get(f"/{lang}/voice")
        css = client.get("/static/css/voice-aurora.css")
        orb = client.get("/static/js/voice-orb.js")
        emblem_js = client.get("/static/js/voice-emblem.js")
        live = client.get("/static/js/voice-live-app.js")
        old = client.get("/static/js/voice-ribbon.js")
    assert result.status_code == css.status_code == orb.status_code == live.status_code == 200
    assert old.status_code == emblem_js.status_code == 404
    assert len(result.content) < 16_000, "Do not inline multi-hundred-kilobyte legacy CSS"
    assert 'id="intro"' not in result.text
    assert 'id="ribbon"' not in result.text
    assert "voice-ribbon" not in result.text
    assert "✺" not in result.text
    assert 'id="orb"' in result.text
    assert 'id="emblem"' not in result.text
    assert 'id="emblemGl"' not in result.text
    assert 'class="logo-mark"' in result.text
    assert 'id="vid"' in result.text
    assert 'id="start"' in result.text
    assert 'id="chatPanel" hidden' in result.text
    assert 'id="wave"' in result.text
    assert "/static/js/voice-live-app.js" in result.text
    assert "/static/js/voice-orb.js" in result.text
    assert "voice-emblem.js" not in result.text
    assert "voice-aurora.css" in result.text
    assert "alnarjis-emblem.png" in result.text
    assert "alnarjis-favicon-32.png" in result.text
    assert "alnarjis-apple-touch.png" in result.text
    assert "voice-orb" in css.text
    assert "min(80vw,520px)" in css.text
    assert "logo-breathe" in css.text
    assert "prefers-reduced-motion" in css.text
    assert "ff5a36" not in orb.text.lower()
    assert "lineTo" not in orb.text
    assert "getUserMedia" not in orb.text
    assert "curl" in orb.text
    assert "snoise" in orb.text
    count = next(line for line in orb.text.splitlines() if "PARTICLE_COUNT" in line)
    assert int("".join(ch for ch in count if ch.isdigit())) >= 5000
    assert "fibonacci" in orb.text.lower()
    assert "jitter" in orb.text.lower()
    assert "orbdemo" in orb.text
    assert "createOscillator" in orb.text
    assert "createAnalyser" in orb.text
    assert "devicePixelRatio" in orb.text
    assert "prefers-reduced-motion" in orb.text
    assert "visibilitychange" in orb.text
    assert "requestAnimationFrame" in orb.text
    assert "webgl" in orb.text
    assert "window.__outLvl" in live.text
    assert "window.__inLvl" in live.text
    assert "createAnalyser" in live.text
    assert "__voiceInAnalyser" in live.text
    assert "__voiceOutAnalyser" in live.text
    assert 'XAI_API_KEY' not in result.text
    assert "xai-client-secret" not in result.text
    assert "unpkg" not in result.text and "jsdelivr" not in result.text and "cdnjs" not in result.text


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
        ctx.add_init_script("if (navigator.mediaDevices) { navigator.mediaDevices.getUserMedia = () => { window.__micAsks = (window.__micAsks || 0) + 1; return Promise.reject(new Error('mic')); }; }")
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
        assert page.locator("#ribbon").count() == 0
        page.wait_for_function("() => window.__orbMode === 'webgl' || window.__orbMode === '2d'")
        assert page.locator("#orb").is_visible()
        assert page.locator("#emblem").count() == 0
        assert page.locator(".logo-mark").is_visible()
        orb_box = page.locator("#orb").bounding_box()
        assert orb_box["height"] == pytest.approx(orb_box["width"], abs=2)
        expected = min(width * 0.8, 520)
        assert orb_box["width"] == pytest.approx(expected, abs=10)
        assert page.locator("#start").is_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        assert page.locator("#orb").evaluate("(el) => el.width > 0 && el.height > 0")
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
def test_voice_orb_is_luminous_when_motion_is_allowed():
    from playwright.sync_api import sync_playwright

    with TestClient(app) as client, sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("BROWSER_EXECUTABLE_PATH"))
        ctx = browser.new_context(viewport={"width": 1280, "height": 900}, reduced_motion="no-preference")

        def serve(route):
            url = urlsplit(route.request.url)
            r = client.request(
                route.request.method,
                url.path + ("?" + url.query if url.query else ""),
                content=route.request.post_data_buffer,
            )
            route.fulfill(
                status=r.status_code,
                body=r.content,
                headers={"content-type": r.headers.get("content-type", "text/plain")},
            )

        ctx.route("**/*", lambda route: route.abort())
        ctx.route("http://testserver/**", serve)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto("http://testserver/ar/voice")
        page.wait_for_function("() => window.__orbMode === 'webgl' || window.__orbMode === '2d'")
        assert page.evaluate("() => window.__orbMode") == "webgl"
        lit = page.evaluate(
            """() => {
              const c = document.getElementById('orb');
              const gl = c.getContext('webgl');
              const pix = new Uint8Array(4);
              gl.readPixels((c.width / 2) | 0, (c.height / 2) | 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pix);
              return pix[0] + pix[1] + pix[2];
            }"""
        )
        assert lit > 30
        assert page.locator(".logo-mark").is_visible()
        assert not errors
        ctx.close()
        browser.close()
