"""Facebook Messenger (Meta Page) channel: webhook verification + Send API.

Inert until META_PAGE_ACCESS_TOKEN, META_APP_SECRET and MESSENGER_VERIFY_TOKEN
are set. Inbound bodies are verified with X-Hub-Signature-256 (HMAC-SHA256 of
the raw body keyed by the Meta app secret) before anything is parsed.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx

from src.config.settings import get_settings

CHANNEL = "messenger"


def is_enabled() -> bool:
    return bool(get_settings().meta_page_access_token)


def webhook_disabled_reason() -> str | None:
    s = get_settings()
    if not s.meta_app_secret:
        return "META_APP_SECRET not set"
    if not s.messenger_verify_token:
        return "MESSENGER_VERIFY_TOKEN not set"
    return None


def verify_challenge(mode: str | None, token: str | None) -> bool:
    expected = get_settings().messenger_verify_token
    return bool(expected) and mode == "subscribe" and hmac.compare_digest(str(token or ""), expected)


def verify_signature(signature: str | None, raw_body: bytes) -> bool:
    secret = get_settings().meta_app_secret
    if not secret or not signature or not signature.startswith("sha256="):
        return False
    digest = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature[7:], digest)


def extract_messages(payload: dict) -> list[dict]:
    """Text messages from a ``page`` webhook body: [{sender, text, mid}]. Echoes are skipped."""
    out: list[dict] = []
    if not isinstance(payload, dict) or payload.get("object") != "page":
        return out
    for entry in payload.get("entry") or []:
        for event in entry.get("messaging") or []:
            msg = event.get("message") or {}
            if not msg or msg.get("is_echo"):
                continue
            sender = (event.get("sender") or {}).get("id")
            text = msg.get("text") or ""
            if sender and text:
                out.append({"sender": str(sender), "text": str(text)[:4000], "mid": msg.get("mid")})
    return out


async def send_text(recipient_psid: Any, text: str) -> dict:
    s = get_settings()
    if not s.meta_page_access_token:
        return {"ok": False, "error": "not_configured", "error_code": "missing_credential"}
    url = f"https://graph.facebook.com/{s.meta_graph_version}/me/messages"
    body = {
        "recipient": {"id": str(recipient_psid)},
        "messaging_type": "RESPONSE",
        "message": {"text": str(text)[:2000]},
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, json=body, params={"access_token": s.meta_page_access_token})
    except httpx.HTTPError as e:
        return {"ok": False, "error": f"network: {type(e).__name__}"}
    if resp.status_code != 200:
        return {"ok": False, "error": f"http {resp.status_code}", "detail": resp.text[:300]}
    data = resp.json()
    return {"ok": True, "message_id": data.get("message_id")}
