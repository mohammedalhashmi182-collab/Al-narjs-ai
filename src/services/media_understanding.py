"""WhatsApp voice notes and images for the Tenant Reply Agent.

A customer's end-customer may send a voice note or a photo instead of text.
This module turns that media into text the RAG reply can use:

  WhatsApp message (type ``audio`` / ``image``)
    -> media id -> Cloud API ``GET /{media-id}`` (URL) -> download with the
       *customer's own* token (never Al-Narjis's)
    -> voice: speech-to-text (Arabic) with the configured provider
       image: vision description + OCR of any visible text
    -> text that feeds ``tenant_reply.handle_inbound`` like a typed message

Providers (env, never logged):

``MEDIA_STT_PROVIDER``    auto (default) | openai | groq | gemini | none
                          auto = OPENAI_API_KEY -> GROQ_API_KEY -> GEMINI_API_KEY
``MEDIA_STT_MODEL``       optional override (whisper-1 / whisper-large-v3 /
                          gemini-2.0-flash)
``MEDIA_VISION_PROVIDER`` auto (default) | openai | gemini | none
                          auto = OPENAI_API_KEY -> GEMINI_API_KEY
``MEDIA_VISION_MODEL``    optional override (gpt-4o-mini / gemini-2.0-flash)
``MEDIA_MAX_BYTES``       download cap, default 16 MB (WhatsApp audio limit)

No provider, a provider error, an oversized/unsupported file or an empty
transcript -> ``MediaText(text="", error=...)``; the caller hands the chat to
the customer's human team (graceful handoff, never a guess). Media bytes are
never stored; only the resulting text and a usage event are kept.
"""

from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

log = logging.getLogger(__name__)

AUDIO_MIMES = ("audio/ogg", "audio/opus", "audio/mpeg", "audio/mp4", "audio/aac", "audio/amr", "audio/wav",
               "audio/webm", "audio/x-m4a")
IMAGE_MIMES = ("image/jpeg", "image/png", "image/webp")
TIMEOUT = 60.0

VISION_PROMPT = (
    "صف هذه الصورة بإيجاز بالعربية كما لو أن عميلاً أرسلها لمتجر يسأل عنها. "
    "اكتب أي نص ظاهر فيها حرفياً (أسماء منتجات، أرقام طلبات، أسعار مكتوبة) بعد كلمة «النص:». "
    "لا تخترع شيئاً غير ظاهر في الصورة."
)


@dataclass
class MediaText:
    kind: str  # voice | image
    text: str = ""
    provider: Optional[str] = None
    seconds: int = 0
    error: Optional[str] = None
    meta: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return bool(self.text.strip()) and not self.error


def media_of(message: dict) -> Optional[dict]:
    """``{"kind", "id", "mime", "caption"}`` for a voice/image message, else None."""
    mtype = (message or {}).get("type")
    if mtype not in ("audio", "voice", "image"):
        return None
    body = message.get(mtype) or {}
    if not isinstance(body, dict) or not body.get("id"):
        return None
    mime = str(body.get("mime_type") or "").split(";")[0].strip().lower()
    return {"kind": "image" if mtype == "image" else "voice", "id": str(body["id"]), "mime": mime,
            "caption": str(body.get("caption") or "").strip()}


def _key(name: str) -> Optional[str]:
    v = os.getenv(name)
    if v:
        return v
    try:
        from src.config.settings import settings

        return getattr(settings, name.lower(), None) or None
    except Exception:  # noqa: BLE001
        return None


def stt_provider() -> Optional[str]:
    p = (os.getenv("MEDIA_STT_PROVIDER") or "auto").strip().lower()
    keys = {"openai": "OPENAI_API_KEY", "groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY"}
    if p == "none":
        return None
    if p in keys:
        return p if _key(keys[p]) else None
    for name, env in keys.items():
        if _key(env):
            return name
    return None


def vision_provider() -> Optional[str]:
    p = (os.getenv("MEDIA_VISION_PROVIDER") or "auto").strip().lower()
    keys = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}
    if p == "none":
        return None
    if p in keys:
        return p if _key(keys[p]) else None
    for name, env in keys.items():
        if _key(env):
            return name
    return None


def max_bytes() -> int:
    try:
        return int(os.getenv("MEDIA_MAX_BYTES") or 16 * 1024 * 1024)
    except ValueError:
        return 16 * 1024 * 1024


# --------------------------------------------------------------------------- HTTP seams (mocked in tests)

async def _http_get(url: str, headers: dict) -> tuple[int, bytes, dict]:
    import httpx

    async with httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT), follow_redirects=True) as c:
        r = await c.get(url, headers=headers)
    return r.status_code, r.content, dict(r.headers)


async def _http_post(url: str, *, headers: dict, json: Any = None, data: Any = None, files: Any = None) -> tuple[int, Any]:
    import httpx

    async with httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT)) as c:
        r = await c.post(url, headers=headers, json=json, data=data, files=files)
    try:
        body = r.json()
    except Exception:  # noqa: BLE001
        body = None
    return r.status_code, body


# --------------------------------------------------------------------------- download

async def download_media(media_id: str, token: str) -> tuple[bytes, str]:
    """Bytes + mime of a WhatsApp media id, fetched with the given (customer) token."""
    import json as _json

    from .whatsapp_sender import API_URL

    auth = {"Authorization": f"Bearer {token}"}
    status, body, _ = await _http_get(f"{API_URL}/{media_id}", auth)
    if status != 200:
        raise RuntimeError(f"media lookup http {status}")
    info = _json.loads(body or b"{}")
    url, size = info.get("url"), int(info.get("file_size") or 0)
    if not url:
        raise RuntimeError("media lookup returned no url")
    if size and size > max_bytes():
        raise ValueError("media too large")
    status, data, headers = await _http_get(url, auth)
    if status != 200:
        raise RuntimeError(f"media download http {status}")
    if len(data) > max_bytes():
        raise ValueError("media too large")
    mime = str(info.get("mime_type") or headers.get("content-type") or "").split(";")[0].strip().lower()
    return data, mime


# --------------------------------------------------------------------------- providers

_STT_DEFAULT = {"openai": "whisper-1", "groq": "whisper-large-v3", "gemini": "gemini-2.0-flash"}
_STT_URL = {"openai": "https://api.openai.com/v1/audio/transcriptions",
            "groq": "https://api.groq.com/openai/v1/audio/transcriptions"}
_VISION_DEFAULT = {"openai": "gpt-4o-mini", "gemini": "gemini-2.0-flash"}


def _ext(mime: str) -> str:
    return {"audio/ogg": "ogg", "audio/opus": "ogg", "audio/mpeg": "mp3", "audio/mp4": "m4a", "audio/x-m4a": "m4a",
            "audio/aac": "aac", "audio/amr": "amr", "audio/wav": "wav", "audio/webm": "webm"}.get(mime, "ogg")


async def _gemini(model: str, parts: list[dict]) -> str:
    key = _key("GEMINI_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    status, body = await _http_post(url, headers={"x-goog-api-key": key or ""},
                                    json={"contents": [{"parts": parts}]})
    if status != 200 or not isinstance(body, dict):
        raise RuntimeError(f"gemini http {status}")
    cands = body.get("candidates") or [{}]
    return "".join(p.get("text", "") for p in ((cands[0].get("content") or {}).get("parts") or [])).strip()


async def transcribe(audio: bytes, mime: str, provider: str) -> tuple[str, int]:
    """(Arabic transcript, duration seconds if the provider reports it, else 0)."""
    model = os.getenv("MEDIA_STT_MODEL") or _STT_DEFAULT[provider]
    if provider == "gemini":
        text = await _gemini(model, [
            {"text": "فرّغ هذا التسجيل الصوتي نصاً حرفياً بلغته الأصلية (غالباً عربي سعودي). اكتب النص فقط."},
            {"inline_data": {"mime_type": mime or "audio/ogg", "data": base64.b64encode(audio).decode()}},
        ])
        return text, 0
    key = _key("OPENAI_API_KEY" if provider == "openai" else "GROQ_API_KEY")
    status, body = await _http_post(
        _STT_URL[provider], headers={"Authorization": f"Bearer {key}"},
        data={"model": model, "language": "ar", "response_format": "verbose_json", "temperature": "0"},
        files={"file": (f"voice.{_ext(mime)}", audio, mime or "audio/ogg")},
    )
    if status != 200 or not isinstance(body, dict):
        raise RuntimeError(f"{provider} stt http {status}")
    secs = body.get("duration")
    return str(body.get("text") or "").strip(), int(round(float(secs))) if isinstance(secs, (int, float)) else 0


async def describe_image(image: bytes, mime: str, provider: str) -> str:
    model = os.getenv("MEDIA_VISION_MODEL") or _VISION_DEFAULT[provider]
    b64 = base64.b64encode(image).decode()
    if provider == "gemini":
        return await _gemini(model, [{"text": VISION_PROMPT}, {"inline_data": {"mime_type": mime, "data": b64}}])
    key = _key("OPENAI_API_KEY")
    status, body = await _http_post(
        "https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "temperature": 0, "max_tokens": 400, "messages": [{"role": "user", "content": [
            {"type": "text", "text": VISION_PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ]}]},
    )
    if status != 200 or not isinstance(body, dict):
        raise RuntimeError(f"openai vision http {status}")
    return str((((body.get("choices") or [{}])[0].get("message") or {}).get("content")) or "").strip()


# --------------------------------------------------------------------------- entry point

async def understand(media: dict, token: Optional[str]) -> MediaText:
    """Turn one voice note / image into text. Never raises; ``error`` explains a miss."""
    kind = media["kind"]
    out = MediaText(kind=kind, meta={"media_id": media["id"]})
    provider = stt_provider() if kind == "voice" else vision_provider()
    out.provider = provider
    if not provider:
        out.error = "no_provider"
        return out
    if not token:
        out.error = "no_project_token"
        return out
    try:
        data, mime = await download_media(media["id"], token)
        mime = mime or media.get("mime") or ""
        allowed = AUDIO_MIMES if kind == "voice" else IMAGE_MIMES
        if mime not in allowed:
            out.error = "unsupported_type"
            return out
        if kind == "voice":
            out.text, out.seconds = await transcribe(data, mime, provider)
        else:
            desc = await describe_image(data, mime, provider)
            out.text = desc
        if not out.text.strip():
            out.error = "empty"
    except ValueError:
        out.error = "too_large"
    except Exception as e:  # noqa: BLE001 - never leak tokens; class name only
        log.warning("media understanding failed (%s, %s)", kind, type(e).__name__)
        out.error = "provider_error"
    return out


def compose_text(media: dict, result: MediaText) -> str:
    """Text handed to the RAG reply: what the customer said / showed, plus any caption."""
    caption = media.get("caption") or ""
    if media["kind"] == "voice":
        return result.text.strip()
    parts = []
    if caption:
        parts.append(caption)
    parts.append(f"(صورة من العميل: {result.text.strip()})")
    return "\n".join(parts)
