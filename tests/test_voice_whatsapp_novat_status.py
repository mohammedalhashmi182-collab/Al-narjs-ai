"""Voice status hides the agent prompt; WhatsApp is allowed; no VAT wording for customers."""

import httpx
from src.services import public_openapi, seo, voice_live


def test_voice_status_does_not_expose_instructions(monkeypatch):
    for configured in (False, True):
        monkeypatch.setattr(voice_live, "configured", lambda c=configured: c)
        body = voice_live.status_payload("203.0.113.9")
        assert "instructions" not in body
        assert "greeting" not in body
        assert "client_secret" not in body
        assert body["ready"] is body["ok"]
        assert "## Role" not in str(body)


async def test_voice_status_route_has_ready_field():
    from src.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://karmaai.online") as client:
        r = await client.get("/api/voice/status")
    assert r.status_code == 200
    data = r.json()
    assert "ready" in data and "ok" in data
    assert "instructions" not in data and "CRITICAL" not in r.text


def test_voice_allows_whatsapp_button_but_never_claims_to_message():
    for lang in ("ar", "en"):
        text = voice_live.session_instructions(lang)
        assert "NEVER offer WhatsApp" not in text
        assert "WhatsApp button" in text
        assert "0552978753" in text and "966552978753" in text
        assert "You cannot send WhatsApp messages" in text
        assert "NEVER say you sent" in text
        assert "NEVER offer Telegram" in text


def test_voice_prices_say_no_vat_when_vat_is_off(monkeypatch):
    from src.services import payments

    monkeypatch.setattr(payments, "vat_enabled", lambda: False)
    text = voice_live.session_instructions("ar")
    assert "before VAT" not in text and "applicable VAT" not in text
    assert "final, with no VAT added" in text


def test_public_docs_and_llms_have_no_before_vat_wording():
    spec = str(public_openapi.build_spec())
    llms = seo.build_llms([])
    for blob in (spec, llms):
        assert "before VAT" not in blob
        assert "قبل الضريبة" not in blob
    assert "no VAT" in llms
