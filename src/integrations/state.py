"""Signed OAuth state. Binds the callback to one project and expires in 10 minutes."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Optional
from uuid import UUID


def _key() -> bytes:
    from src.config.settings import settings

    return hashlib.sha256(f"store-oauth:{settings.secret_key}".encode()).digest()


def _sign(payload: str) -> str:
    return hmac.new(_key(), payload.encode(), hashlib.sha256).hexdigest()


def sign_state(project_id: UUID, platform: str, *, now: float | None = None) -> str:
    body = {"p": str(project_id), "pf": platform, "exp": int((now or time.time()) + 600)}
    raw = base64.urlsafe_b64encode(json.dumps(body, separators=(",", ":")).encode()).decode().rstrip("=")
    return f"{raw}.{_sign(raw)}"


def read_state(token: str, platform: str, *, now: float | None = None) -> Optional[str]:
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
    return str(project_id) if project_id else None
