"""The free voice advisor answers through the same model chain as site chat."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.services import voice_live
from src.utils.rate_limit import voice_reply_limiter


@pytest.fixture
def client():
    voice_reply_limiter.reset()
    with TestClient(app) as test_client:
        yield test_client
    voice_reply_limiter.reset()


def test_spoken_prompt_keeps_prices_and_drops_vat_and_store_claims() -> None:
    prompt = voice_live.spoken_system_prompt("ar")
    assert "مستشار النرجس الذكي" in prompt
    assert "The initial diagnosis is free" in prompt
    assert "Do not present private trials as public offers" in prompt
    assert "790 SAR per month" in prompt
    assert "1,490 SAR per month" in prompt
    assert "2,990 SAR per month" in prompt
    assert "before any applicable VAT" not in prompt
    assert "Do not mention VAT" in prompt
    assert "Do not say Salla or Zid" in prompt
    assert "Do not invent clients" in prompt
    assert "Saudi-friendly Arabic" in prompt
    assert "with digits (790, 1,490, 2,990), never spelled out in words" in prompt


def test_store_claim_is_not_spoken() -> None:
    blocked = voice_live.spoken_reply_text("ربط سلة متاح اليوم لحسابك.", "ar")
    assert "متاح" not in blocked
    assert "AlNarjisai@gmail.com" in blocked


def test_voice_reply_endpoint_uses_the_chat_model(client: TestClient, monkeypatch) -> None:
    seen = {}

    class Provider:
        async def complete_with_fallback(self, chain, request):
            seen["chain"] = chain
            seen["prompt"] = request.prompt
            seen["system"] = request.system_prompt
            return SimpleNamespace(content="باقة البداية 790 ريال شهرياً.")

    monkeypatch.setattr(app.state, "model_provider", Provider())
    response = client.post(
        "/api/voice/reply",
        json={
            "text": "كم سعر البداية؟",
            "lang": "ar",
            "history": [{"role": "user", "content": "مرحبا"}, {"role": "assistant", "content": "حياك"}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "790" in body["reply"]
    assert seen["chain"] == "gemini"
    assert "كم سعر البداية؟" in seen["prompt"]
    assert "مرحبا" in seen["prompt"]
    assert "790 SAR per month" in seen["system"]
    assert "sk-" not in response.text
    assert "OPENROUTER" not in response.text


def test_voice_reply_hides_provider_failures(client: TestClient, monkeypatch) -> None:
    class Provider:
        async def complete_with_fallback(self, chain, request):
            raise RuntimeError("provider down")

    monkeypatch.setattr(app.state, "model_provider", Provider())
    response = client.post("/api/voice/reply", json={"text": "مرحبا", "lang": "ar"})
    assert response.status_code == 503
    assert response.json()["ok"] is False
    assert "provider down" not in response.text


def test_voice_page_defaults_to_browser_speech() -> None:
    script = (voice_live._PAGE.parent / "js" / "voice-live-app.js").read_text(encoding="utf-8")
    assert 'voiceMode = "speech"' in script
    assert "SpeechRecognition" in script
    assert "webkitSpeechRecognition" in script
    assert 'rec.lang = EN ? "en-US" : "ar-SA"' in script
    assert "/api/voice/reply" in script
    assert "يفكر" in script
    assert "هذا المتصفح لا يدعم الاستماع" in script
    assert voice_live.voice_mode() == "speech"
    assert voice_live.status_payload("203.0.113.9")["mode"] == "speech"
