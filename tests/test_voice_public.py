"""Public live voice: xAI client secrets, caps, and a contact fallback."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services import catalog, voice_live
from src.services.support import COMPANY_PHONE_DISPLAY, COMPANY_PHONE_E164, SUPPORT_EMAIL

VISIBLE = re.compile(r"(?s)<(script|style).*?</\1>")
AGENT = "va_owner_live_01"
_JS = Path(__file__).resolve().parents[1] / "src/web/static/js/voice-live-app.js"
_ANTI_GROK = "NEVER say you are Grok, Grok Voice, xAI, or ChatGPT."


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
    for page in (ar, en):
        assert 'id="voiceLauncher"' not in page.text
        assert 'id="homeWhatsapp"' not in page.text
        for button in ("heroWhatsapp", "mbarWhatsapp"):
            assert re.search(r'<a\b[^>]*id="' + button + r'"[^>]*href="https://wa.me/966552978753"', page.text)
    assert "تواصل معنا عبر واتساب" in ar.text
    assert "Chat with us on WhatsApp" in en.text
    assert 'href="/ar/voice"' in client.get('/ar/consult').text
    assert 'id="voiceLauncher"' in client.get('/ar/consult').text
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
    assert 'id="chat"' in ar.text and "دردشة" in _visible(ar.text)
    assert 'id="chatPanel" hidden' in ar.text
    assert 'id="log"' in ar.text and 'id="say"' in ar.text
    assert "رجوع للصوت" in _visible(ar.text)
    assert ar.text.index('id="chatPanel"') < ar.text.index('id="log"')
    assert "دردشة" not in _visible(en.text)
    assert "رجوع للصوت" not in _visible(en.text)
    assert "Chat" in _visible(en.text) and "Back to voice" in _visible(en.text)
    assert "تحدّث مع" in _visible(ar.text)
    assert "Start the call" in _visible(en.text)
    assert "Talk to" in _visible(en.text)
    assert "تحدّث مع" not in _visible(en.text)
    assert f"mailto:{SUPPORT_EMAIL}" in ar.text
    assert "https://wa.me/966552978753" in ar.text
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
    script = _JS.read_text(encoding="utf-8")
    assert "elevenlabs" not in script.lower()
    assert "XAI_API_KEY" not in script
    assert "wss://api.x.ai/v1/realtime" in script
    assert "voice websocket closed" in script
    assert "model=grok-voice-latest&agent_id" not in script
    assert "model=" not in script


def test_sitemap_lists_the_voice_page(client: TestClient):
    locs = client.get("/sitemap.xml").text
    assert "https://karmaai.online/ar/voice" in locs
    assert "https://karmaai.online/en/voice" in locs


def test_status_stays_quiet_until_the_owner_sets_both_values():
    body = voice_live.status_payload("203.0.113.5")
    assert body["ok"] is False and body["reason"] == "unconfigured"
    assert body["max_seconds"] == 180
    assert body["contact"]["email"] == SUPPORT_EMAIL
    assert body["instructions"] == voice_live.session_instructions()
    assert "client_secret" not in body and "websocket_url" not in body


def test_voice_instructions_name_al_narjis_and_forbid_grok():
    text = voice_live.session_instructions()
    assert "مستشار النرجس" in text
    assert "Al-Narjis advisor" in text
    assert "https://karmaai.online" in text
    assert _ANTI_GROK in text
    assert "ChatGPT" in text and "Grok Voice" in text and "xAI" in text
    assert "Saudi-friendly Arabic" in text
    assert "Switch to English only if the caller speaks English." in text
    assert "Do not open in English." in text
    assert voice_live.opening_greeting() == "حياكم الله نورتوا النرجس، كريم معكم، كيف ممكن أساعد؟"
    assert "Grok" not in voice_live.opening_greeting()
    assert "Grok" not in voice_live.opening_greeting("en")
    assert "كريم" in text
    assert SUPPORT_EMAIL in text
    assert "NEVER offer WhatsApp" in text
    assert "Do not mention a bank transfer, an IBAN" in text
    assert "bank transfer exists" not in text
    assert "bots, automation, agents, design, and content" in text
    prices = {
        "bidaya": "790",
        "numuw": "1,490",
        "sharikat": "2,990",
    }
    for key, shown in prices.items():
        assert f"{int(catalog.PACKAGES[key]['price']):,}" == shown
        assert f"{shown} SAR per month" in text
    assert "discount" in text.lower()
    assert voice_live.status_payload("203.0.113.5")["instructions"] == text


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
    assert granted["websocket_url"] == f"wss://api.x.ai/v1/realtime?agent_id={AGENT}"
    assert "model=" not in granted["websocket_url"]
    assert granted["instructions"] == voice_live.session_instructions("ar")
    assert granted["greeting"] == voice_live.opening_greeting("ar")
    assert "مستشار النرجس" in granted["instructions"]
    assert _ANTI_GROK in granted["instructions"]
    assert "session" not in seen[0]["json"] and "session" not in seen[1]["json"]
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
    assert "model=" not in first.json()["websocket_url"]
    assert "مستشار النرجس" in first.json()["instructions"]
    assert first.json()["greeting"] == voice_live.opening_greeting("ar")
    assert _ANTI_GROK in first.json()["instructions"]
    assert "xai-test-key-not-real" not in first.text
    assert second.status_code == 429
    assert second.json()["reason"] == "daily_limit"
    assert second.headers["retry-after"]


def test_session_lang_selects_the_opening_line(client: TestClient, monkeypatch):
    _enable(monkeypatch)

    async def mint(agent, key):
        return "ephemeral-token-value"

    monkeypatch.setattr(voice_live, "mint_client_secret", mint)
    arabic = client.post("/api/voice/session?lang=ar")
    english = client.post("/api/voice/session?lang=en")
    assert arabic.status_code == english.status_code == 200
    assert arabic.json()["greeting"] == "حياكم الله نورتوا النرجس، كريم معكم، كيف ممكن أساعد؟"
    assert "Grok" not in arabic.json()["greeting"]
    assert "Switch to English only if the caller speaks English." in arabic.json()["instructions"]
    assert english.json()["greeting"] == voice_live.opening_greeting("en")
    assert "Grok" not in english.json()["greeting"]
    assert "Do not open in English." not in english.json()["instructions"]
    assert "model=" not in arabic.json()["websocket_url"]


def test_configure_session_copies_server_instructions():
    """The browser session.update carries the server persona and no model field."""
    script = _JS.read_text(encoding="utf-8")
    update = script.split("function configureSession()", 1)[1].split("start.onclick", 1)[0]
    assert 'sessionInstructions = typeof payload.instructions === "string" ? payload.instructions : ""' in script
    assert 'sessionGreeting = typeof payload.greeting === "string" ? payload.greeting : ""' in script
    assert 'fetch("/api/voice/session?lang=" + (EN ? "en" : "ar")' in script
    assert "session.instructions = sessionInstructions" in update
    assert 'type: "session.update"' in update
    assert 'type: "force_message"' in update
    assert 'type: "response.cancel"' in script
    greet = script.split("function speakGreeting()", 1)[1].split("function wantsChat(", 1)[0]
    typed = script.split("function sendTyped(", 1)[1].split("function flushTyped(", 1)[0]
    assert 'type: "response.create"' not in greet
    assert 'type: "force_message"' in greet
    assert 'type: "input_text"' in typed
    assert 'type: "response.create"' in typed
    assert "function wantsChat" in script
    assert "function userText" in script
    assert "no-mic" in script
    mic_fail = script.split("await attachMic();", 1)[1].split("await ensureAudio();", 1)[0]
    assert "showMicProblem" in mic_fail
    assert "return false" not in mic_fail
    assert "finish()" not in mic_fail
    assert "if (chatOpen) return" in script
    assert "رجوع للصوت" not in script
    assert "function openChat" in script
    assert "function closeChat" in script
    assert "model" not in update
    assert _ANTI_GROK not in script

    node = shutil.which("node")
    if node is None:
        return
    payload = {
        "ok": True,
        "instructions": voice_live.session_instructions("ar"),
        "greeting": voice_live.opening_greeting("ar"),
        "client_secret": "ephemeral-token-value",
        "websocket_url": f"wss://api.x.ai/v1/realtime?agent_id={AGENT}",
    }
    harness = r"""
const fs = require("fs");
const vm = require("vm");
const payload = JSON.parse(process.argv[1]);
const messages = [];
const sockets = [];
class FakeSocket {
  static OPEN = 1;
  constructor(url, protocols) {
    this.url = url;
    this.protocols = protocols;
    this.readyState = FakeSocket.OPEN;
    sockets.push(this);
    queueMicrotask(() => { if (this.onopen) this.onopen(); });
  }
  send(data) { messages.push(JSON.parse(data)); }
  close() { this.readyState = 3; }
}
function el() {
  const node = {
    classList: { remove() {}, add() {}, toggle() {}, contains() { return false; } },
    style: { setProperty() {} },
    setAttribute() {},
    getAttribute() { return "false"; },
    append(child) { node.childNodes.push(child); },
    childNodes: [],
    hidden: false,
    disabled: false,
    textContent: "",
    value: "",
    onclick: null,
    onsubmit: null,
    focus() {},
    placeholder: "",
  };
  Object.defineProperty(node, "lastChild", { get() { return node.childNodes[node.childNodes.length - 1] || null; } });
  Object.defineProperty(node, "innerHTML", {
    get() { return node._html || ""; },
    set(value) {
      node._html = String(value);
      node.childNodes = [el()];
    },
  });
  node.querySelector = () => node.lastChild || node;
  return node;
}
const els = {};
const document = {
  documentElement: { lang: "ar" },
  title: "",
  getElementById(id) { return els[id] || (els[id] = el()); },
  createElement() { return el(); },
};
const window = {
  addEventListener() {},
  AudioContext: class {
    constructor() {
      this.state = "running";
      this.sampleRate = 24000;
      this.currentTime = 0;
      this.destination = {};
    }
    resume() { return Promise.resolve(); }
    createMediaStreamSource() { return { connect() {} }; }
    createScriptProcessor() { return { connect() {}, disconnect() {}, onaudioprocess: null }; }
    createGain() { return { gain: { value: 0 }, connect() {} }; }
  },
};
const fetched = [];
const context = {
  els,
  messages,
  sockets,
  payload,
  fetched,
  document,
  window,
  navigator: { mediaDevices: { getUserMedia() { return Promise.resolve({ getTracks() { return []; } }); } } },
  fetch: async (url) => { fetched.push(String(url)); return { ok: true, status: 200, json: async () => payload }; },
  WebSocket: FakeSocket,
  performance: { now: () => 0 },
  console,
  process,
  setInterval,
  clearInterval,
  setTimeout,
  queueMicrotask,
  JSON,
  Math,
  Promise,
  String,
  Date,
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);
vm.runInContext(`
(async () => {
  await els.start.onclick();
  await new Promise((resolve) => setTimeout(resolve, 20));
  if (!sockets.length) throw new Error("socket was not opened");
  if (!fetched.some((url) => url.indexOf("/api/voice/session?lang=ar") >= 0)) {
    throw new Error("arabic page did not ask for lang=ar: " + fetched.join(","));
  }
  if (messages.some((message) => message.type === "session.update")) {
    throw new Error("session.update ran before session.created");
  }
  const url = sockets[0].url;
  if (!url.includes("agent_id=") || url.includes("model=")) {
    throw new Error("socket url left agent_id mode: " + url);
  }
  sockets[0].onmessage({ data: JSON.stringify({ type: "session.created", session: {} }) });
  const updates = messages.filter((message) => message.type === "session.update");
  if (updates.length !== 1) throw new Error("expected one session.update, got " + updates.length);
  const instructions = updates[0].session.instructions;
  if (instructions !== payload.instructions) throw new Error("instructions were not copied");
  if (Object.prototype.hasOwnProperty.call(updates[0].session, "model")) throw new Error("model field was added");
  if (!instructions.includes("مستشار النرجس")) throw new Error("missing Al-Narjis identity");
  if (!instructions.includes("كريم")) throw new Error("missing spoken name Karim");
  if (!instructions.includes("NEVER say you are Grok, Grok Voice, xAI, or ChatGPT.")) throw new Error("missing anti-Grok rule");
  if (!instructions.includes("Switch to English only if the caller speaks English.")) throw new Error("arabic default missing");
  sockets[0].onmessage({ data: JSON.stringify({ type: "response.created", response: { id: "resp_grok" } }) });
  sockets[0].onmessage({ data: JSON.stringify({ type: "response.output_audio.delta", delta: "AAAA", response_id: "resp_grok" }) });
  sockets[0].onmessage({ data: JSON.stringify({ type: "response.output_audio_transcript.delta", delta: "Hello, I'm Grok Voice", response_id: "resp_grok" }) });
  const cancels = messages.filter((message) => message.type === "response.cancel");
  if (cancels.length !== 1 || cancels[0].response_id !== "resp_grok") {
    throw new Error("console greeting was not cancelled");
  }
  sockets[0].onmessage({ data: JSON.stringify({ type: "session.updated", session: {} }) });
  const forced = messages.filter((message) => message.item && message.item.type === "force_message");
  if (forced.length !== 1) throw new Error("expected one force_message, got " + forced.length);
  const spoken = forced[0].item.content[0].text;
  if (spoken !== payload.greeting) throw new Error("greeting was not the server line: " + spoken);
  if (/Grok|xAI|ChatGPT/.test(spoken)) throw new Error("greeting names a vendor");
  if (messages.some((message) => message.type === "response.create")) throw new Error("response.create lets the model greet");
  sockets[0].onmessage({ data: JSON.stringify({ type: "response.created", response: { id: "resp_late" } }) });
  sockets[0].onmessage({ data: JSON.stringify({ type: "response.output_audio_transcript.delta", delta: "Hello, I'm Grok Voice", response_id: "resp_late" }) });
  const late = messages.filter((message) => message.type === "response.cancel" && message.response_id === "resp_late");
  if (late.length !== 1) throw new Error("late Grok greeting was not cancelled");
  if (messages.some((message) => message.type === "response.create")) throw new Error("response.create lets the model greet");
  els.say.value = "كم السعر؟";
  await els.composer.onsubmit({ preventDefault() {} });
  if (messages.some((message) => message.type === "response.create")) {
    throw new Error("typed message was sent before the greeting finished");
  }
  sockets[0].onmessage({ data: JSON.stringify({ type: "response.done", response: { id: "resp_hi" } }) });
  const typed = messages.filter((message) => message.item && message.item.role === "user" && message.item.content && message.item.content[0].type === "input_text");
  if (typed.length !== 1 || typed[0].item.content[0].text !== "كم السعر؟") throw new Error("typed text was not delivered");
  const replies = messages.filter((message) => message.type === "response.create");
  if (replies.length !== 1) throw new Error("typed turn did not ask for a reply");
  console.log(JSON.stringify({ updates: updates.length, cancels: cancels.length, spoken, url, typed: typed.length }));
  process.exit(0);
})().catch((error) => { console.error(error && error.stack || error); process.exit(1); });
`, context);
"""
    proc = subprocess.run(
        [node, "-e", harness, json.dumps(payload), str(_JS)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    report = json.loads(proc.stdout.strip().splitlines()[-1])
    assert report["updates"] == 1
    assert report["cancels"] == 1
    assert report["spoken"] == voice_live.opening_greeting("ar")
    assert f"agent_id={AGENT}" in report["url"]
    assert "model=" not in report["url"]
