"""Voice interface contracts exercised with local routes and simulated providers."""

from __future__ import annotations

import os
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.services import voice_live

browser_required = pytest.mark.skipif(
    os.environ.get("RUN_BROWSER_TESTS") != "1", reason="requires Chromium CI"
)


@pytest.mark.parametrize("lang,name", [("ar", "مستشار النرجس الذكي"), ("en", "Al Narjis AI advisor")])
def test_voice_page_renders_the_advisor_and_waveform(lang, name):
    with TestClient(app) as client:
        page = client.get(f"/{lang}/voice")
        css = client.get("/static/css/voice-aurora.css")
    assert page.status_code == css.status_code == 200
    assert name in page.text
    assert 'id="wave" aria-hidden="true"' in page.text
    assert 'aria-controls="chatPanel" aria-expanded="false"' in page.text
    assert 'id="chatPanel" hidden' in page.text
    assert 'id="orb"' not in page.text
    assert "/static/js/voice-orb.js" not in page.text
    assert "/static/brand/vnext/tokens.css" in page.text
    assert "prefers-reduced-motion" in css.text
    assert "/static/logo.svg" in page.text


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
    from src.services.catalog import PACKAGE_ORDER, PACKAGES

    script = voice_live.session_instructions("ar")
    for key in PACKAGE_ORDER:
        plan = PACKAGES[key]
        sar = f'{plan["amount"] / 100:,.2f}'.removesuffix(".00")
        assert f'{plan["name"]} ({plan["name_en"]}) {sar} SAR per month' in script
    assert "before any applicable VAT" in script
    monkeypatch.setitem(PACKAGES["bidaya"], "amount", 82500)
    revised = voice_live.session_instructions("en")
    assert "البداية (Starter) 825 SAR per month" in revised
    assert "البداية (Starter) 790 SAR per month" not in revised


def test_invalid_catalog_price_fails_closed_for_voice(monkeypatch):
    from src.services.catalog import PACKAGES

    monkeypatch.setitem(PACKAGES["bidaya"], "amount", -100)
    with pytest.raises(ValueError, match="canonical package"):
        voice_live.session_instructions("ar")


def _local_routes(context, client):
    def serve(route):
        url = urlsplit(route.request.url)
        response = client.request(
            route.request.method,
            url.path + ("?" + url.query if url.query else ""),
            content=route.request.post_data_buffer,
        )
        route.fulfill(
            status=response.status_code,
            body=response.content,
            headers=dict(response.headers),
        )

    context.route("**/*", lambda route: route.abort())
    context.route("http://testserver/**", serve)


@browser_required
@pytest.mark.parametrize("lang,width,direction", [("ar", 320, "rtl"), ("en", 1280, "ltr")])
def test_voice_denied_microphone_opens_silent_text_fallback(lang, width, direction):
    from playwright.sync_api import expect, sync_playwright

    with TestClient(app) as client, sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.environ.get("BROWSER_EXECUTABLE_PATH"))
        context = browser.new_context(viewport={"width": width, "height": 844}, reduced_motion="reduce")
        _local_routes(context, client)
        context.route("**/api/voice/status", lambda route: route.fulfill(json={"mode": "speech", "ok": False}))
        context.route("**/api/voice/reply", lambda route: route.fulfill(json={"ok": True, "reply": "Test reply"}))
        context.add_init_script("""
          window.voiceStarts = 0;
          window.voiceOutputs = 0;
          window.SpeechRecognition = window.webkitSpeechRecognition = class {
            start() {
              window.voiceStarts++;
              queueMicrotask(() => this.onerror?.({error: 'not-allowed'}));
            }
            abort() {}
          };
          window.SpeechSynthesisUtterance = class {};
          Object.defineProperty(window, 'speechSynthesis', { value: {
            getVoices: () => [],
            cancel() {},
            speak(utterance) { window.voiceOutputs++; queueMicrotask(() => utterance.onend?.()); }
          }});
        """)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(error))
        page.goto(f"http://testserver/{lang}/voice")
        expect(page.locator("html")).to_have_attribute("dir", direction)
        expect(page.locator("#wave i")).to_have_count(23)
        expect(page.locator("#wave i").first).to_have_css("transform", "none")
        assert page.evaluate("window.voiceStarts === 0 && window.voiceOutputs === 0")
        assert page.evaluate("document.documentElement.scrollWidth === window.innerWidth")

        page.locator("#start").click()
        expect(page.locator("#chatPanel")).to_be_visible()
        expect(page.locator("#micNote")).to_be_visible()
        expect(page.locator("#say")).to_be_focused()
        assert page.evaluate("window.voiceStarts === 1 && window.voiceOutputs === 1")

        page.locator("#say").fill("What are the packages?")
        with page.expect_request("**/api/voice/reply") as request:
            page.locator("#send").click()
        assert request.value.post_data_json["lang"] == lang
        expect(page.get_by_text("Test reply")).to_be_visible()
        assert page.evaluate("window.voiceOutputs") == 1
        page.locator("#voiceBack").click()
        expect(page.locator("#start")).to_be_focused()
        assert page.evaluate("window.voiceStarts") == 1
        assert not errors
        browser.close()


@browser_required
def test_voice_wave_measures_webaudio_and_releases_capture_when_switching_to_chat():
    from playwright.sync_api import expect, sync_playwright

    with TestClient(app) as client, sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.environ.get("BROWSER_EXECUTABLE_PATH"))
        context = browser.new_context(reduced_motion="no-preference")
        _local_routes(context, client)
        context.route("**/api/voice/status", lambda route: route.fulfill(json={"mode": "xai", "ok": True}))
        context.route("**/api/voice/session?*", lambda route: route.fulfill(json={
            "ok": True,
            "websocket_url": "wss://api.x.ai/v1/realtime?agent_id=mock",
            "client_secret": "mock-session-value",
        }))
        context.add_init_script("""
          window.micRequests = 0;
          Object.defineProperty(navigator, 'mediaDevices', {value: {getUserMedia: async () => {
            window.micRequests++;
            const audio = new AudioContext();
            await audio.resume();
            const sink = audio.createMediaStreamDestination();
            const tone = audio.createOscillator();
            tone.frequency.value = 240;
            tone.connect(sink);
            tone.start();
            window.testMicTrack = sink.stream.getAudioTracks()[0];
            window.testMicAudio = audio;
            return sink.stream;
          }}});
          window.WebSocket = class {
            static OPEN = 1;
            readyState = 1;
            constructor() {
              queueMicrotask(() => this.emit('session.created'));
            }
            emit(type) { this.onmessage?.({data: JSON.stringify({type})}); }
            send(message) {
              if (JSON.parse(message).type === 'session.update') this.emit('session.updated');
            }
            close() { this.readyState = 3; }
          };
        """)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(error))
        page.goto("http://testserver/en/voice")
        assert page.evaluate("window.micRequests") == 0
        page.locator("#start").click()
        expect(page.locator("#s")).to_have_text("Listening…")
        page.wait_for_function("""() => [...document.querySelectorAll('#wave i')].some(
          bar => parseFloat(bar.style.getPropertyValue('--amplitude')) > 1.2
        )""")

        page.locator("#mute").click()
        expect(page.locator("#s")).to_have_text("Microphone muted")
        assert not page.evaluate("window.testMicTrack.enabled")
        page.locator("#mute").click()
        assert page.evaluate("window.testMicTrack.enabled")

        page.locator("#chat").click()
        expect(page.locator("#chatPanel")).to_be_visible()
        assert page.evaluate("window.testMicTrack.readyState") == "ended"
        assert page.evaluate("""() => [...document.querySelectorAll('#wave i')].every(
          bar => parseFloat(bar.style.getPropertyValue('--amplitude')) === 1
        )""")
        page.evaluate("window.testMicAudio.close()")
        assert not errors
        browser.close()


def test_voice_logo_files_are_real_images():
    with TestClient(app) as client:
        emblem = client.get("/static/brand/alnarjis-emblem.png")
        emblem_webp = client.get("/static/brand/alnarjis-emblem.webp")
        icon = client.get("/static/brand/alnarjis-favicon-32.png")
    for response in (emblem, emblem_webp, icon):
        assert response.status_code == 200
        assert len(response.content) > 400
    assert emblem.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert emblem_webp.content[8:12] == b"WEBP"
    assert icon.content[:8] == b"\x89PNG\r\n\x1a\n"
