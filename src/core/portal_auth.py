"""Customer portal sessions.

Before: the project UUID kept in ``localStorage`` was the only credential for
every ``/api/portal/projects/{pid}/...`` route. Now a route needs a signed,
HttpOnly session cookie (``narjis_portal``) bound to that project, obtained by:

* creating the project (the creator gets the session),
* a 6-digit OTP sent to the project's email (or WhatsApp phone),
* a single-use magic link (``/portal/login?token=...``) the owner can issue, or
* the legacy UUID exchange, which only yields a *limited* session that is valid
  while the project is still unpaid (backwards compatibility for checkouts in
  flight; an active subscription always needs OTP / magic link).

The owner's console cookie is also accepted (support access). Bumping
``ClientProject.portal_token_version`` revokes every session of a project.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, Request, Response

from src.config.settings import settings

COOKIE_NAME = "narjis_portal"
SESSION_TTL = 30 * 24 * 3600
MAGIC_TTL = 30 * 60
OTP_TTL = 10 * 60
OTP_MAX_ATTEMPTS = 5


def _sign(payload: str, purpose: str) -> str:
    key = hashlib.sha256(f"portal:{purpose}:{settings.secret_key}".encode()).digest()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def _encode(body: dict, purpose: str) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(body, separators=(",", ":")).encode()).decode().rstrip("=")
    return f"{raw}.{_sign(raw, purpose)}"


def _decode(token: Optional[str], purpose: str) -> Optional[dict]:
    if not token or token.count(".") != 1:
        return None
    raw, sig = token.split(".")
    if not hmac.compare_digest(sig, _sign(raw, purpose)):
        return None
    try:
        body = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    except Exception:
        return None
    if not isinstance(body, dict) or float(body.get("exp", 0)) < time.time():
        return None
    return body


def hash_secret(value: str) -> str:
    return _sign(value, "otp")


def make_session_token(project, *, limited: bool = False, now: float | None = None) -> str:
    now = now or time.time()
    body = {"p": str(project.id), "v": int(getattr(project, "portal_token_version", 0) or 0),
            "exp": int(now + SESSION_TTL)}
    if limited:
        body["lg"] = 1
    return _encode(body, "session")


def make_magic_token(project_id, nonce: str, now: float | None = None) -> str:
    return _encode({"p": str(project_id), "n": nonce, "exp": int((now or time.time()) + MAGIC_TTL)}, "magic")


def read_magic_token(token: str) -> Optional[dict]:
    return _decode(token, "magic")


def new_nonce() -> str:
    return secrets.token_urlsafe(24)


def new_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def set_session_cookie(response: Response, project, *, limited: bool = False) -> Response:
    response.set_cookie(COOKIE_NAME, make_session_token(project, limited=limited), max_age=SESSION_TTL,
                        httponly=True, samesite="lax", secure=(settings.environment == "production"), path="/")
    return response


def clear_session_cookie(response: Response) -> Response:
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


def session_claims(request: Request) -> Optional[dict]:
    return _decode(request.cookies.get(COOKIE_NAME), "session")


LEGACY_STATUSES = ("pending", "draft")


def legacy_allowed(project) -> bool:
    """The UUID-only legacy exchange is for checkouts in flight: a project that
    has never been paid. Anything that was ever activated (active, expired,
    cancelled, demo, or with a recorded payment/period) must log in properly,
    because its portal exposes contacts, drafts and replies."""
    if project is None or project.status not in LEGACY_STATUSES:
        return False
    if getattr(project, "last_payment_id", None) or getattr(project, "current_period_end", None):
        return False
    return True


def session_valid_for(claims: Optional[dict], project) -> bool:
    if not claims or project is None or claims.get("p") != str(project.id):
        return False
    if int(claims.get("v", -1)) != int(getattr(project, "portal_token_version", 0) or 0):
        return False
    if claims.get("lg") and not legacy_allowed(project):
        return False  # legacy UUID session: never-paid projects only
    return True


async def require_portal_project(session, request: Request, pid: str):
    """Load ``pid`` and require a portal session (or the owner) for it. 401 otherwise."""
    from src.core.owner_auth import check_owner
    from src.models import ClientProject

    try:
        project = await session.get(ClientProject, UUID(str(pid)))
    except ValueError:
        project = None
    if check_owner(request) and project is not None:
        return project
    if project is None or not session_valid_for(session_claims(request), project):
        # Same answer for "no such project" and "not yours": no UUID probing.
        raise HTTPException(401, "Portal login required")
    return project
