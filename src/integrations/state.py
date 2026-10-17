"""Signed OAuth state. Binds the callback to one project, one nonce, and 10 minutes.

The nonce is single-use and stored server-side (see ``oauth_nonce``). The
signature only stops the browser from editing the project id.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from typing import Optional
from uuid import UUID

_NONCE = re.compile(r"[A-Za-z0-9_-]{16,64}")


def _key() -> bytes:
    from src.config.settings import settings

    return hashlib.sha256(f"store-oauth:{settings.secret_key}".encode()).digest()


def _sign(payload: str) -> str:
    return hmac.new(_key(), payload.encode(), hashlib.sha256).hexdigest()


def sign_state(project_id: UUID, platform: str, nonce: str, *, now: float | None = None) -> str:
    body = {
        "p": str(project_id),
        "pf": platform,
        "n": nonce,
        "exp": int((now or time.time()) + 600),
    }
    raw = base64.urlsafe_b64encode(json.dumps(body, separators=(",", ":")).encode()).decode().rstrip("=")
    return f"{raw}.{_sign(raw)}"


def read_state(token: str, platform: str, *, now: float | None = None) -> Optional[dict]:
    if not token or token.count(".") != 1:
        return None
    raw, sig = token.split(".")
    if not hmac.compare_digest(sig, _sign(raw)):
        return None
    try:
        body = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    except Exception:
        return None
    if not isinstance(body, dict) or body.get("pf") != platform:
        return None
    if float(body.get("exp", 0)) < (now or time.time()):
        return None
    project_id = body.get("p")
    nonce = body.get("n")
    if not project_id or not isinstance(nonce, str) or not _NONCE.fullmatch(nonce):
        return None
    return {"project_id": str(project_id), "nonce": nonce}
