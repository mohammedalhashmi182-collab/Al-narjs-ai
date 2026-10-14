"""WhatsApp voice notes / images on a customer's number feed the tenant RAG reply.

All provider and Meta HTTP calls are mocked (``media_understanding._http_get`` /
``_http_post``); no network, no real keys."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models import ClientProject, InboundMessage
from src.models.automation import ReplyDraft
from src.models.tenant import TenantContact
from src.models.usage import UsageEvent
from src.services import media_understanding as mu
from src.services import tenant_reply, usage
from src.services.agent_tools import knowledge_base

NOW = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)
FAQ = "ساعات العمل: نفتح يوميًا من الساعة 9 صباحًا حتى 11 مساءً. التوصيل داخل الرياض مجاني للطلبات فوق 200 ريال."


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture(autouse=True)
def env(monkeypatch):
    for k in ("MEDIA_STT_PROVIDER", "MEDIA_VISION_PROVIDER", "MEDIA_STT_MODEL", "MEDIA_VISION_MODEL", "MEDIA_MAX_BYTES"):
        monkeypatch.delenv(k, raising=False)
    keys: dict = {}
    monkeypatch.setattr(mu, "_key", lambda name: keys.get(name))

    async def _quiet(*a, **k):
        return {"ok": True}

    from src.services import telegram_sender

    monkeypatch.setattr(telegram_sender, "send_owner_alert", _quiet)
    return keys


class FakeHTTP:
    """Records every call; answers Meta media lookup/download and provider APIs."""

    def __init__(self, monkeypatch, *, mime="audio/ogg", size=1200, data=b"OggS-fake-voice", stt="متى ساعات العمل؟",
                 vision="صورة لافتة مكتوب عليها النص: ساعات العمل", provider_status=200):
        self.gets: list[tuple] = []
        self.posts: list[tuple] = []
        self.mime, self.size, self.data = mime, size, data
        self.stt, self.vision, self.provider_status = stt, vision, provider_status
        monkeypatch.setattr(mu, "_http_get", self.get)
        monkeypatch.setattr(mu, "_http_post", self.post)

    async def get(self, url, headers):
        self.gets.append((url, headers))
        if "lookaside" in url:
            return 200, self.data, {"content-type": self.mime}
        return 200, json.dumps({"url": "https://lookaside.fbsbx.com/m/1", "mime_type": self.mime,
                                "file_size": self.size}).encode(), {}

    async def post(self, url, *, headers, json=None, data=None, files=None):
        self.posts.append((url, headers, json, data, files))
        if self.provider_status != 200:
            return self.provider_status, {"error": {"message": "boom"}}
        if "audio/transcriptions" in url:
            return 200, {"text": self.stt, "duration": 7.4}
        if "generativelanguage" in url:
            text = self.stt if any("فرّغ" in (p.get("text") or "") for p in json["contents"][0]["parts"]) else self.vision
            return 200, {"candidates": [{"content": {"parts": [{"text": text}]}}]}
        return 200, {"choices": [{"message": {"content": self.vision}}]}


async def _project(s, token=True, mode="review"):
    p = ClientProject(client_name="متجر الورد", phone="0555000001", package="radd", status="active",
                      wa_phone_number_id="111", reply_mode=mode)
    if token:
        p.wa_access_token_enc = tenant_reply.encrypt_token("customer-token-x")
    s.add(p)
    await s.flush()
    await knowledge_base.add_doc(s, "FAQ", FAQ, project_id=p.id)
    await s.commit()
    return p


def _voice(mid="wamid.v1"):
    return {"id": mid, "from": "966511111111", "type": "audio", "audio": {"id": "MEDIA1", "mime_type": "audio/ogg; codecs=opus", "voice": True}}


def _image(mid="wamid.i1", caption=""):
    return {"id": mid, "from": "966511111111", "type": "image", "image": {"id": "MEDIA2", "mime_type": "image/jpeg", "caption": caption}}


def test_media_of_parses_voice_and_image_only():
    assert mu.media_of(_voice())["kind"] == "voice" and mu.media_of(_voice())["mime"] == "audio/ogg"
    assert mu.media_of(_image(caption="بكم هذا؟"))["caption"] == "بكم هذا؟"
    assert mu.media_of({"type": "text", "text": {"body": "x"}}) is None
    assert mu.media_of({"type": "audio", "audio": {}}) is None


def test_provider_selection_auto_explicit_and_none(env, monkeypatch):
    assert mu.stt_provider() is None and mu.vision_provider() is None
    env["GROQ_API_KEY"] = "g"
    assert mu.stt_provider() == "groq" and mu.vision_provider() is None  # Groq has no vision here
    env["GEMINI_API_KEY"] = "k"
    assert mu.vision_provider() == "gemini"
    env["OPENAI_API_KEY"] = "o"
    assert mu.stt_provider() == "openai" and mu.vision_provider() == "openai"
    monkeypatch.setenv("MEDIA_STT_PROVIDER", "gemini")
    assert mu.stt_provider() == "gemini"
    monkeypatch.setenv("MEDIA_STT_PROVIDER", "none")
    assert mu.stt_provider() is None
    monkeypatch.setenv("MEDIA_VISION_PROVIDER", "openai")
    env.pop("OPENAI_API_KEY")
    assert mu.vision_provider() is None  # explicit provider without its key = missing, not a silent switch


@pytest.mark.parametrize("provider,key,url_part", [
    ("openai", "OPENAI_API_KEY", "api.openai.com/v1/audio/transcriptions"),
    ("groq", "GROQ_API_KEY", "api.groq.com/openai/v1/audio/transcriptions"),
    ("gemini", "GEMINI_API_KEY", "generativelanguage.googleapis.com"),
])
async def test_voice_note_is_transcribed_in_arabic_and_answered_from_the_tenant_kb(maker, env, monkeypatch, provider, key, url_part):
    env[key] = "provider-key-x"
    monkeypatch.setenv("MEDIA_STT_PROVIDER", provider)
    http = FakeHTTP(monkeypatch)
    async with maker() as s:
        p = await _project(s)
        d = await tenant_reply.handle_media_inbound(s, project=p, contact="966511111111", message=_voice())
        # media fetched from Meta with the CUSTOMER's token, never Al-Narjis's
        assert http.gets[0][0].endswith("/MEDIA1") and http.gets[0][1]["Authorization"] == "Bearer customer-token-x"
        assert url_part in http.posts[0][0]
        if provider != "gemini":
            assert http.posts[0][3]["language"] == "ar"
        assert d.kind == "reply" and "9 صباحًا" in d.draft_text and d.status == "pending"
        assert d.meta["media"] == "voice" and d.meta["media_provider"] == provider
        assert d.inbound_text == "متى ساعات العمل؟"
        ev = (await s.execute(select(UsageEvent).where(UsageEvent.kind == "media_voice"))).scalar_one()
        assert ev.project_id == p.id and ev.ref == "wamid.v1"
        assert ev.quantity == (7 if provider != "gemini" else 1)
        # the key never ends up in stored data
        assert "provider-key-x" not in json.dumps(d.meta, ensure_ascii=False)


async def test_image_is_described_with_ocr_and_caption_kept(maker, env, monkeypatch):
    env["OPENAI_API_KEY"] = "o"
    http = FakeHTTP(monkeypatch, mime="image/jpeg")
    async with maker() as s:
        p = await _project(s)
        d = await tenant_reply.handle_media_inbound(s, project=p, contact="966511111111",
                                                    message=_image(caption="متى ساعات العمل؟"))
        body = http.posts[0][2]
        assert body["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
        assert "النص" in body["messages"][0]["content"][0]["text"]  # OCR requested
        assert d.inbound_text.startswith("متى ساعات العمل؟") and "صورة من العميل" in d.inbound_text
        assert d.meta["media"] == "image"
        assert (await usage.media_usage(s, p, now=datetime.now(timezone.utc)))["images"] == 1


@pytest.mark.parametrize("setup,reason", [
    ("no_provider", "media_no_provider"),
    ("no_token", "media_no_project_token"),
    ("provider_error", "media_provider_error"),
    ("too_large", "media_too_large"),
    ("unsupported", "media_unsupported_type"),
    ("empty", "media_empty"),
])
async def test_graceful_handoff_when_media_cannot_be_understood(maker, env, monkeypatch, setup, reason):
    if setup != "no_provider":
        env["OPENAI_API_KEY"] = "o"
    kw = {}
    if setup == "provider_error":
        kw["provider_status"] = 500
    if setup == "too_large":
        kw["size"] = 50 * 1024 * 1024
    if setup == "unsupported":
        kw["mime"] = "application/pdf"
    if setup == "empty":
        kw["stt"] = "  "
    http = FakeHTTP(monkeypatch, **kw)
    async with maker() as s:
        p = await _project(s, token=setup != "no_token")
        d = await tenant_reply.handle_media_inbound(s, project=p, contact="966511111111", message=_voice())
        assert d.kind == "handoff" and d.meta["handoff"] == reason and "متجر الورد" in d.draft_text
        c = (await s.execute(select(TenantContact))).scalar_one()
        assert c.handoff_at is not None and c.handoff_reason == reason
        assert (await s.execute(select(UsageEvent).where(UsageEvent.kind.like("media_%")))).scalars().all() == []
        if setup in ("no_provider", "no_token"):
            assert http.gets == [] and http.posts == []


async def test_over_limit_makes_no_paid_media_call(maker, env, monkeypatch):
    env["OPENAI_API_KEY"] = "o"
    http = FakeHTTP(monkeypatch)

    async def _over(session, project):
        return True

    monkeypatch.setattr(tenant_reply, "over_ai_limit", _over)
    async with maker() as s:
        p = await _project(s)
        d = await tenant_reply.handle_media_inbound(s, project=p, contact="966511111111", message=_voice())
        assert d.meta["handoff"] == "media_over_limit" and http.posts == [] and http.gets == []


async def test_review_mode_default_never_sends_and_auto_sends_handoff_from_customer_number(maker, env, monkeypatch):
    FakeHTTP(monkeypatch)
    sent = []

    async def _post(pnid, token, body):
        sent.append((pnid, token, body))
        return {"ok": True, "provider_message_id": "wamid.out1"}

    monkeypatch.setattr(tenant_reply, "_post_tenant", _post)
    async with maker() as s:
        p = await _project(s)
        d = await tenant_reply.handle_media_inbound(s, project=p, contact="966511111111", message=_voice())
        assert d.status == "pending" and sent == []
        p.reply_mode = "auto"
        d = await tenant_reply.handle_media_inbound(s, project=p, contact="966522222222", message=_voice("wamid.v2"))
        assert d.status == "sent" and sent[0][0] == "111" and sent[0][1] == "customer-token-x"


async def test_usage_is_per_tenant_and_counted_once_per_message(maker, env, monkeypatch):
    env["OPENAI_API_KEY"] = "o"
    FakeHTTP(monkeypatch)
    async with maker() as s:
        a = await _project(s)
        b = ClientProject(client_name="مخبز", phone="0555000002", package="radd", status="active", wa_phone_number_id="222")
        s.add(b)
        await s.flush()
        assert (await usage.record_media(s, a, "voice", seconds=7, ref="wamid.x"))["counted"]
        assert not (await usage.record_media(s, a, "voice", seconds=7, ref="wamid.x"))["counted"]
        await usage.record_media(s, a, "image", ref="wamid.y")
        ma = await usage.media_usage(s, a)
        mb = await usage.media_usage(s, b)
        assert ma == {"voice_notes": 1, "voice_seconds": 7, "images": 1}
        assert mb == {"voice_notes": 0, "voice_seconds": 0, "images": 0}
        # media does not eat the plan's voice-agent minutes (owner pricing decision)
        row = await usage.current_usage(s, a)
        assert int(row.voice_seconds or 0) == 0 and not row.over_limit


async def test_webhook_routes_voice_note_to_tenant_and_never_to_al_narjis_sales(maker, env, monkeypatch):
    """End to end through POST /webhooks/whatsapp with a valid signature (app secret mocked)."""
    import hashlib
    import hmac

    from src.config.settings import settings
    from src.main import app
    from src.services import smart_reply

    env["GROQ_API_KEY"] = "g"
    FakeHTTP(monkeypatch)
    monkeypatch.setattr(settings, "whatsapp_app_secret", "app-secret-test")
    monkeypatch.setattr(settings, "whatsapp_webhook_verify_token", "verify-test")
    called = []

    async def _sales(*a, **k):
        called.append(k)

    monkeypatch.setattr(smart_reply, "safe_handle_inbound", _sales)
    async with maker() as s:
        p = await _project(s)
    app.state.session_factory = maker
    payload = {"entry": [{"changes": [{"value": {
        "metadata": {"phone_number_id": "111"},
        "contacts": [{"wa_id": "966511111111", "profile": {"name": "سارة"}}],
        "messages": [{**_voice("wamid.web1"), "timestamp": str(int(NOW.timestamp()))}],
    }}]}]}
    raw = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(b"app-secret-test", raw, hashlib.sha256).hexdigest()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/webhooks/whatsapp", content=raw,
                         headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"})
    assert r.status_code == 200, r.text
    assert called == []
    async with maker() as s:
        d = (await s.execute(select(ReplyDraft))).scalar_one()
        assert d.project_id == p.id and d.meta["media"] == "voice" and d.lead_id is None
        rec = (await s.execute(select(InboundMessage))).scalar_one()
        assert rec.project_id == p.id and rec.text == "متى ساعات العمل؟"
