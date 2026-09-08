from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Optional

from fastapi import HTTPException, Request, Response

from src.config.settings import settings

_COOKIE_NAME = "narjis_owner"


def _sign(payload: str) -> str:
    return hmac.new(
        settings.secret_key.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


def make_session_token() -> str:
    body = {"t": int(time.time()), "r": "owner"}
    raw = base64.urlsafe_b64encode(json.dumps(body).encode()).decode()
    return f"{raw}.{_sign(raw)}"


def verify_session_token(token: Optional[str]) -> bool:
    if not token:
        return False
    try:
        raw, sig = token.split(".")
        if not hmac.compare_digest(sig, _sign(raw)):
            return False
        payload = json.loads(base64.urlsafe_b64decode(raw.encode()))
        if payload.get("r") != "owner":
            return False
        # 12-hour sliding expiry
        if time.time() - payload.get("t", 0) > 12 * 3600:
            return False
        return True
    except Exception:
        return False


def check_owner(request: Request) -> bool:
    token = request.cookies.get(_COOKIE_NAME)
    return verify_session_token(token)


def require_owner(request: Request):
    if not check_owner(request):
        raise HTTPException(status_code=401, detail="Owner access required")


def set_owner_cookie(response: Response) -> Response:
    response.set_cookie(
        _COOKIE_NAME,
        make_session_token(),
        max_age=12 * 3600,
        httponly=True,
        samesite="lax",
    )
    return response


def clear_owner_cookie(response: Response) -> Response:
    response.delete_cookie(_COOKIE_NAME)
    return response