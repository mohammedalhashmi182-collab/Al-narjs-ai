"""Public live voice calls through the owner's xAI Voice Agent.

Docs: https://docs.x.ai/developers/model-capabilities/audio/ephemeral-tokens
and https://docs.x.ai/developers/model-capabilities/audio/speech-to-speech

The browser never receives ``XAI_API_KEY``. The server mints a short-lived
client secret (``POST /v1/realtime/client_secrets``) and the page opens
``wss://api.x.ai/v1/realtime?agent_id=...`` with the ``xai-client-secret.``
subprotocol. Do not also pass ``model=``; that mode is for an unnamed session.
``XAI_VOICE_AGENT_ID`` is the published agent from console.x.ai → Voice Agents.
Both values must be set. Either one empty turns the call off and the page
shows the company email and phone.

Caps (rolling windows, per process):
* 3 minutes per call, enforced in the page
* ``XAI_VOICE_DAILY_CALL_LIMIT`` (default 100) for the whole site
* ``XAI_VOICE_IP_DAILY_CALL_LIMIT`` (default 10) per visitor
* ``XAI_VOICE_IP_BURST_LIMIT`` (default 8) session grants per 10 minutes per IP
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx

from src.services.support import (
    COMPANY_PHONE_DISPLAY,
    COMPANY_PHONE_E164,
    SUPPORT_EMAIL,
)
from src.utils.rate_limit import SlidingWindowLimiter

MAX_SECONDS = 180
_CLIENT_SECRETS = "https://api.x.ai/v1/realtime/client_secrets"
_REALTIME = "wss://api.x.ai/v1/realtime"
_AGENT_ID = re.compile(r"^[A-Za-z0-9_.:-]{4,128}$")
_PAGE = Path(__file__).resolve().parents[1] / "web" / "static" / "voice-live.html"

_limiters: dict[str, SlidingWindowLimiter] = {}


class VoiceError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _build_limiters() -> None:
    daily = _int_env("XAI_VOICE_DAILY_CALL_LIMIT", 100)
    per_ip = _int_env("XAI_VOICE_IP_DAILY_CALL_LIMIT", 10)
    burst = _int_env("XAI_VOICE_IP_BURST_LIMIT", 8)
    _limiters["global"] = SlidingWindowLimiter(max(daily, 0), 86400)
    _limiters["ip"] = SlidingWindowLimiter(max(per_ip, 1), 86400)
    _limiters["burst"] = SlidingWindowLimiter(max(burst, 1), 600)


def reset_limits() -> None:
    """Recreate the windows from the current settings. Tests call this."""
    _limiters.clear()
    _build_limiters()


def _lim() -> dict[str, SlidingWindowLimiter]:
    if not _limiters:
        _build_limiters()
    return _limiters


def agent_id() -> str:
    return os.getenv("XAI_VOICE_AGENT_ID", "").strip()


def api_key() -> str:
    return os.getenv("XAI_API_KEY", "").strip()


def configured() -> bool:
    if _int_env("XAI_VOICE_DAILY_CALL_LIMIT", 100) <= 0:
        return False
    return bool(api_key()) and bool(_AGENT_ID.fullmatch(agent_id()))


def public_contact() -> dict[str, str]:
    return {
        "email": SUPPORT_EMAIL,
        "email_href": f"mailto:{SUPPORT_EMAIL}",
        "phone": COMPANY_PHONE_DISPLAY,
        "phone_href": f"tel:{COMPANY_PHONE_E164}",
    }


def websocket_url(agent: str) -> str:
    """Socket for a console Voice Agent.

    ``agent_id`` and ``model`` are different modes. A published agent is
    opened with only ``?agent_id=``. Adding ``model=`` as well makes xAI
    reject the handshake and the browser hangs up at once.
    """
    return f"{_REALTIME}?agent_id={quote(agent, safe='')}"


def _valid_websocket_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme == "wss" and parts.hostname == "api.x.ai" and parts.path == "/v1/realtime"


def _gate(ip: str, *, commit: bool) -> tuple[str | None, int]:
    who = ip or "unknown"
    lim = _lim()
    # A zero global cap means "off", handled by configured(). Skip a broken limiter.
    checks = (("burst", f"voice-burst:{who}"), ("ip", f"voice-ip:{who}"))
    if _int_env("XAI_VOICE_DAILY_CALL_LIMIT", 100) > 0:
        checks = (*checks, ("global", "voice-all"))
    for name, key in checks:
        limiter = lim[name]
        if limiter.max_requests <= 0:
            return "daily_limit", 86400
        ok, retry = limiter.check(key, commit=commit)
        if not ok:
            reason = "daily_limit" if name == "global" else "ip_limit" if name == "ip" else "busy"
            return reason, retry
    return None, 0


def _base() -> dict:
    return {"max_seconds": MAX_SECONDS, "contact": public_contact()}


def status_payload(ip: str = "") -> dict:
    body = _base()
    if not configured():
        return {**body, "ok": False, "reason": "unconfigured"}
    reason, retry = _gate(ip or "status", commit=False)
    if reason:
        return {**body, "ok": False, "reason": reason, "retry_after": retry}
    return {**body, "ok": True, "reason": None}


async def mint_client_secret(agent: str, key: str) -> str:
    """Ask xAI for an ephemeral client secret. ``key`` stays on the server.

    The published agent id is sent with the request. If that field is rejected,
    the documented body is tried once. The socket URL still names the agent.
    """
    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.post(
            _CLIENT_SECRETS,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"expires_after": {"seconds": 300}, "agent_id": agent},
        )
        if response.status_code == 400:
            response = await client.post(
                _CLIENT_SECRETS,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"expires_after": {"seconds": 300}},
            )
    if response.status_code in (401, 403):
        raise VoiceError("unconfigured")
    if response.status_code >= 400:
        raise VoiceError("upstream")
    try:
        value = str((response.json() or {}).get("value") or "").strip()
    except ValueError as exc:
        raise VoiceError("upstream") from exc
    if not value or value == key or key in value:
        raise VoiceError("upstream")
    return value


async def open_session(ip: str) -> dict:
    body = _base()
    if not configured():
        return {**body, "ok": False, "reason": "unconfigured"}
    reason, retry = _gate(ip, commit=False)
    if reason:
        return {**body, "ok": False, "reason": reason, "retry_after": retry}
    agent = agent_id()
    key = api_key()
    try:
        secret = await mint_client_secret(agent, key)
    except VoiceError as exc:
        return {**body, "ok": False, "reason": exc.reason}
    url = websocket_url(agent)
    if not _valid_websocket_url(url):
        return {**body, "ok": False, "reason": "upstream"}
    _gate(ip, commit=True)
    return {**body, "ok": True, "client_secret": secret, "websocket_url": url}


@lru_cache(maxsize=1)
def _raw_page() -> str:
    return _PAGE.read_text(encoding="utf-8")


def _strip_lang(html: str, drop: str) -> str:
    """Remove elements whose class list contains ``ar-only`` or ``en-only``."""
    token = f"{drop}-only"
    pattern = re.compile(
        rf"<([a-zA-Z0-9]+)\b[^>]*\bclass=\"[^\"]*\b{re.escape(token)}\b[^\"]*\"[^>]*>"
    )
    pieces: list[str] = []
    cursor = 0
    for match in pattern.finditer(html):
        tag = match.group(1)
        start = match.start()
        if start < cursor:
            continue
        depth = 1
        pos = match.end()
        open_token = f"<{tag}"
        close_token = f"</{tag}>"
        end = None
        while depth and pos < len(html):
            next_open = html.find(open_token, pos)
            next_close = html.find(close_token, pos)
            if next_close < 0:
                break
            if next_open != -1 and next_open < next_close:
                depth += 1
                pos = next_open + len(open_token)
            else:
                depth -= 1
                pos = next_close + len(close_token)
                if depth == 0:
                    end = pos
        if end is None:
            continue
        pieces.append(html[cursor:start])
        cursor = end
    pieces.append(html[cursor:])
    return "".join(pieces)


def render_page(lang: str) -> str:
    """The voice page, in one language, indexable at /ar/voice and /en/voice."""
    html = _raw_page()
    if lang == "en":
        html = html.replace('<html lang="ar" dir="rtl">', '<html lang="en" dir="ltr">', 1)
        html = html.replace(
            "<title>تحدّث مع مستشار النرجس</title>",
            "<title>Talk to the Al-Narjis agent</title>",
            1,
        )
        html = html.replace(
            'content="مكالمة صوتية حية مع مستشار النرجس. ثلاث دقائق كحد أقصى."',
            'content="A live voice call with the Al-Narjis agent. Three minutes at most."',
            1,
        )
        html = html.replace(
            '<link rel="canonical" href="https://karmaai.online/ar/voice">',
            '<link rel="canonical" href="https://karmaai.online/en/voice">',
            1,
        )
        html = _strip_lang(html, "ar")
    else:
        html = _strip_lang(html, "en")
    return html.replace('content="noindex,nofollow"', 'content="index,follow"', 1)
