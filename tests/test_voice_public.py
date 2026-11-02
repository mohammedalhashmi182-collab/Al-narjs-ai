"""Public live voice: xAI client secrets, caps, and a contact fallback."""

from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services import voice_live
from src.services.support import COMPANY_PHONE_DISPLAY, COMPANY_PHONE_E164, SUPPORT_EMAIL

VISIBLE = re.compile(r"(?s)<(script|style).*?</\1>")
AGENT = "va_owner_live_01"


@pytest.fixture(autouse=True)
def _fresh_voice_limits(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "")
    monkeypatch.setenv("XAI_VOICE_AGENT_ID", "")
    monkeypatch.setenv("XAI_VOICE_DAILY_CALL_LIMIT", "100")
    monkeypatch.setenv("XAI_VOICE_IP_DAILY_CALL_LIMIT", "10")
    monkeypatch.setenv("XAI_VOICE_IP_BURST_LIMIT", "8")
    voice_live.reset_limits()
    yield
    voice_live.reset_limits()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _visible(html: str) -> str:
    return VISIBLE.sub(" ", html)


def _enable(monkeypatch, **extra):
    monkeypatch.setenv("XAI_API_KEY", extra.get("key", "xai-test-key-not-real"))
    monkeypatch.setenv("XAI_VOICE_AGENT_ID", extra.get("agent", AGENT))
    for name, value in extra.items():
        if name not in ("key", "agent"):
            monkeypatch.setenv(name, value)
    voice_live.reset_limits()


def test_public_pages_link_the_voice_agent_and_not_a_text_widget(client: TestClient):
    ar = client.get("/ar/home")
    en = client.get("/en/home")
    assert ar.status_code == en.status_code == 200
    assert 'id="voiceLauncher"' in ar.text and 'href="/ar/voice"' in ar.text
    assert "تحدث مع مستشارنا" in ar.text
    assert 'id="heroVoice"' in ar.text
    assert 'id="mbarVoice"' in ar.text and 'href="/ar/voice"' in ar.text
    assert 'id="voiceLauncher"' in en.text and 'href="/en/voice"' in en.text
    assert "Talk to our agent" in en.text
    assert 'id="openAssistant"' not in ar.text and 'id="siteAssistant"' not in ar.text
    assert "tel:" not in ar.text and COMPANY_PHONE_DISPLAY not in ar.text
    contact = client.get("/ar/contact")
    assert contact.status_code == 200
    assert 'href="/ar/voice"' in contact.text and 'id="voiceLauncher"' in contact.text
    assert "tel:" not in contact.text
    login = client.get("/login")
    assert 'id="voiceLauncher"' not in login.text


def test_voice_page_is_public_in_both_languages(client: TestClient):
    bare = client.get("/voice", follow_redirects=False)
    assert bare.status_code == 301
    assert bare.headers["location"].endswith("/ar/voice")

    ar = client.get("/ar/voice")
    en = client.get("/en/voice")
    assert ar.status_code == en.status_code == 200
    assert 'name="robots" content="index,follow"' in ar.text
    assert 'rel="canonical" href="https://karmaai.online/ar/voice"' in ar.text
    assert 'rel="canonical" href="https://karmaai.online/en/voice"' in en.text
    assert 'lang="ar"' in ar.text and 'dir="rtl"' in ar.text
    assert 'lang="en"' in en.text and 'dir="ltr"' in en.text
    assert "ابدأ المكالمة" in _visible(ar.text)
    assert "تحدّث مع" in _visible(ar.text)
    assert "Start the call" in _visible(en.text)
    assert "Talk to" in _visible(en.text)
    assert "تحدّث مع" not in _visible(en.text)
    assert f"mailto:{SUPPORT_EMAIL}" in ar.text
    assert f"tel:{COMPANY_PHONE_E164}" in ar.text
    assert COMPANY_PHONE_DISPLAY in ar.text
    assert "elevenlabs" not in ar.text.lower()
    assert "XAI_API_KEY" not in ar.text
    assert 'href="#"' not in ar.text
    assert ar.headers["permissions-policy"] == "microphone=(self)"
    assert "wss://api.x.ai" in ar.headers["content-security-policy"]
    assert "elevenlabs" not in ar.headers["content-security-policy"]

    hidden = client.get("/static/voice-live.html")
    assert hidden.status_code == 200
    assert "noindex" in hidden.text
    assert "elevenlabs" not in hidden.text.lower()
    script = (Path(__file__).resolve().parents[1] / "src/web/static/js/voice-live-app.js").read_text(encoding="utf-8")
    assert "elevenlabs" not in script.lower()
    assert "XAI_API_KEY" not in script
    assert "wss://api.x.ai/v1/realtime" in script


def test_sitemap_lists_the_voice_page(client: TestClient):
    locs = client.get("/sitemap.xml").text
    assert "https://karmaai.online/ar/voice" in locs
    assert "https://karmaai.online/en/voice" in locs


def test_status_stays_quiet_until_the_owner_sets_both_values():
    body = voice_live.status_payload("203.0.113.5")
    assert body["ok"] is False and body["reason"] == "unconfigured"
    assert body["max_seconds"] == 180
    assert body["contact"]["email"] == SUPPORT_EMAIL
    assert "client_secret" not in body and "websocket_url" not in body


@pytest.mark.asyncio
async def test_session_mints_a_client_secret_for_the_published_agent(monkeypatch):
    _enable(monkeypatch, key="xai-test-key-not-real")
    seen = []

    class _Response:
        def __init__(self, status, payload):
            self.status_code = status
            self._payload = payload

        def json(self):
            return self._payload

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def post(self, url, headers=None, json=None):
            seen.append({"url": url, "headers": headers, "json": json})
            if json and "agent_id" in json:
                return _Response(400, {"error": "unknown field"})
            return _Response(200, {"value": "ephemeral-token-value", "expires_at": 1})

    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: _Client())
    granted = await voice_live.open_session("203.0.113.8")
    assert granted["ok"] is True
    assert granted["client_secret"] == "ephemeral-token-value"
    assert granted["websocket_url"].startswith("wss://api.x.ai/v1/realtime?")
    assert f"agent_id={AGENT}" in granted["websocket_url"]
    assert "xai-test-key-not-real" not in str(granted)
    assert seen[0]["json"]["agent_id"] == AGENT
    assert seen[0]["headers"]["Authorization"] == "Bearer xai-test-key-not-real"
    assert seen[1]["json"] == {"expires_after": {"seconds": 300}}


@pytest.mark.asyncio
async def test_daily_and_per_visitor_caps(monkeypatch):
    _enable(
        monkeypatch,
        XAI_VOICE_DAILY_CALL_LIMIT="2",
        XAI_VOICE_IP_DAILY_CALL_LIMIT="10",
        XAI_VOICE_IP_BURST_LIMIT="10",
    )

    async def mint(agent, key):
        assert agent == AGENT
        return "ephemeral-token-value"

    monkeypatch.setattr(voice_live, "mint_client_secret", mint)
    first = await voice_live.open_session("203.0.113.8")
    second = await voice_live.open_session("203.0.113.8")
    third = await voice_live.open_session("203.0.113.9")
    assert first["ok"] and second["ok"]
    assert third["reason"] == "daily_limit"
    assert third["contact"]["phone_href"] == f"tel:{COMPANY_PHONE_E164}"

    voice_live.reset_limits()
    monkeypatch.setenv("XAI_VOICE_DAILY_CALL_LIMIT", "100")
    monkeypatch.setenv("XAI_VOICE_IP_DAILY_CALL_LIMIT", "1")
    voice_live.reset_limits()
    assert (await voice_live.open_session("203.0.113.20"))["ok"]
    assert (await voice_live.open_session("203.0.113.20"))["reason"] == "ip_limit"
    assert (await voice_live.open_session("203.0.113.21"))["ok"]


@pytest.mark.asyncio
async def test_a_failed_mint_does_not_spend_a_slot(monkeypatch):
    _enable(monkeypatch, XAI_VOICE_DAILY_CALL_LIMIT="1")

    async def boom(agent, key):
        raise voice_live.VoiceError("unconfigured")

    monkeypatch.setattr(voice_live, "mint_client_secret", boom)
    failed = await voice_live.open_session("203.0.113.31")
    assert failed["ok"] is False and failed["reason"] == "unconfigured"
    assert "xai-test-key-not-real" not in str(failed)

    async def mint(agent, key):
        return "ephemeral-token-value"

    monkeypatch.setattr(voice_live, "mint_client_secret", mint)
    assert (await voice_live.open_session("203.0.113.31"))["ok"] is True


def test_session_route_reports_the_daily_limit(client: TestClient, monkeypatch):
    _enable(
        monkeypatch,
        XAI_VOICE_DAILY_CALL_LIMIT="1",
        XAI_VOICE_IP_DAILY_CALL_LIMIT="10",
        XAI_VOICE_IP_BURST_LIMIT="10",
    )

    async def mint(agent, key):
        return "ephemeral-token-value"

    monkeypatch.setattr(voice_live, "mint_client_secret", mint)
    first = client.post("/api/voice/session")
    second = client.post("/api/voice/session")
    assert first.status_code == 200
    assert first.json()["websocket_url"].startswith("wss://api.x.ai/")
    assert "xai-test-key-not-real" not in first.text
    assert second.status_code == 429
    assert second.json()["reason"] == "daily_limit"
    assert second.headers["retry-after"]
