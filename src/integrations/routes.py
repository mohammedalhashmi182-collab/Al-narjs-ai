"""Portal install/policy and platform webhooks.

* GET  /api/portal/projects/{pid}/store
* PUT  /api/portal/projects/{pid}/store/policy
* GET  /api/portal/projects/{pid}/stores/{platform}/install
* DELETE /api/portal/projects/{pid}/stores/{platform}
* GET  /webhooks/stores/{platform}/callback
* POST /webhooks/stores/{platform}

Hidden while STORE_INTEGRATIONS_ENABLED is off (404), except a verified
uninstall webhook, which still clears tokens.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.core.portal_auth import require_portal_project
from src.integrations import limits
from src.integrations.config import enabled, env
from src.integrations.net import client_ip
from src.integrations.provider import StoreApiError
from src.integrations.replay import salla_fresh, zid_fresh
from src.integrations.service import (
    apply_webhook,
    claim_event,
    connections,
    disconnect,
    policy_public,
    policy_row,
    save_install,
    save_policy,
)
from src.integrations.state import read_state, sign_state

log = logging.getLogger(__name__)

router = APIRouter()

_SALLA_OAUTH = ("SALLA_CLIENT_ID", "SALLA_CLIENT_SECRET", "SALLA_REDIRECT_URI")
_ZID_OAUTH = ("ZID_CLIENT_ID", "ZID_CLIENT_SECRET", "ZID_REDIRECT_URI")
_MAX_BODY = 256 * 1024


def _factory(request: Request):
    return request.app.state.session_factory


def _require_enabled() -> None:
    if not enabled():
        raise HTTPException(404, "Not found")


def _limit(limiter, key: str) -> None:
    ok, retry = limiter.check(key)
    if not ok:
        raise HTTPException(429, detail={"error": "Too many requests", "retry_after_seconds": retry},
                            headers={"Retry-After": str(retry)})


async def _active(session, pid: str, request: Request):
    project = await require_portal_project(session, request, pid)
    if project.status != "active":
        raise HTTPException(402, "Subscription not active — activate your plan first")
    return project


def _page(ok: bool) -> HTMLResponse:
    if ok:
        title, body = "تم ربط المتجر", "تم ربط المتجر. يمكنك إغلاق هذه الصفحة والعودة إلى البوابة."
    else:
        title, body = "تعذّر الربط", "تعذّر إكمال الربط. أعد المحاولة من البوابة."
    html = (
        "<!doctype html><html lang=\"ar\" dir=\"rtl\"><meta charset=\"utf-8\">"
        f"<title>{title}</title><body style=\"font-family:Cairo,sans-serif;padding:2rem\">"
        f"<p>{body}</p><p><a href=\"/portal\">العودة إلى البوابة</a></p></body></html>"
    )
    return HTMLResponse(html, status_code=200 if ok else 400)


def _public_connection(row) -> dict:
    return {"platform": row.platform, "status": row.status, "store_name": row.store_name or ""}


@router.get("/api/portal/projects/{pid}/store")
async def store_summary(pid: str, request: Request):
    _require_enabled()
    async with _factory(request)() as session:
        project = await _active(session, pid, request)
        rows = await connections(session, project.id, active_only=False)
        policy = policy_public(await policy_row(session, project.id))
        return {"connections": [_public_connection(row) for row in rows], "policy": policy}


@router.put("/api/portal/projects/{pid}/store/policy")
async def update_policy(pid: str, request: Request):
    _require_enabled()
    _limit(limits.installs, f"policy:{pid}:{client_ip(request)}")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    if not isinstance(body, dict):
        raise HTTPException(400, "Invalid JSON")
    async with _factory(request)() as session:
        project = await _active(session, pid, request)
        try:
            saved = await save_policy(session, project.id, body)
        except ValueError:
            raise HTTPException(422, "نص السياسة أطول من الحد المسموح")
        return {"policy": saved}


@router.get("/api/portal/projects/{pid}/stores/{platform}/install")
async def install(pid: str, platform: str, request: Request):
    _require_enabled()
    if platform not in ("salla", "zid"):
        raise HTTPException(404, "Unknown platform")
    async with _factory(request)() as session:
        project = await _active(session, pid, request)
        _limit(limits.installs, f"{project.id}:{client_ip(request)}")
        from src.integrations.oauth_nonce import issue_nonce

        nonce = await issue_nonce(session, request, project, platform)
        await session.commit()
        state = sign_state(project.id, platform, nonce)
    if platform == "salla":
        from src.integrations.salla.client import authorize_url

        missing = [name for name in _SALLA_OAUTH if not env(name)]
    else:
        from src.integrations.zid.client import authorize_url

        missing = [name for name in _ZID_OAUTH if not env(name)]
    url = authorize_url(state) if not missing else None
    if not url:
        raise HTTPException(503, detail={"missing": missing})
    return RedirectResponse(url, status_code=302)


@router.delete("/api/portal/projects/{pid}/stores/{platform}")
async def uninstall_local(pid: str, platform: str, request: Request):
    _require_enabled()
    if platform not in ("salla", "zid"):
        raise HTTPException(404, "Unknown platform")
    async with _factory(request)() as session:
        project = await _active(session, pid, request)
        removed = await disconnect(session, project.id, platform)
        return {"disconnected": removed}


@router.get("/webhooks/stores/{platform}/callback", response_class=HTMLResponse)
async def oauth_callback(platform: str, request: Request):
    _require_enabled()
    if platform not in ("salla", "zid"):
        raise HTTPException(404, "Unknown platform")
    _limit(limits.installs, f"callback:{client_ip(request)}")
    if request.query_params.get("error"):
        log.info("store oauth denied platform=%s", platform)
        return _page(False)
    code = (request.query_params.get("code") or "").strip()
    parsed = read_state(request.query_params.get("state") or "", platform)
    if not code or not parsed:
        log.info("store oauth callback rejected platform=%s", platform)
        return _page(False)
    from uuid import UUID

    from src.integrations.oauth_nonce import claim_nonce
    from src.models import ClientProject

    try:
        pid = UUID(parsed["project_id"])
    except ValueError:
        return _page(False)
    async with _factory(request)() as session:
        project = await session.get(ClientProject, pid)
        if project is None or project.status != "active":
            log.info("store oauth callback rejected platform=%s", platform)
            return _page(False)
        if not await claim_nonce(session, request, project, parsed["nonce"], platform):
            log.info("store oauth callback rejected platform=%s", platform)
            return _page(False)
        # Burn the nonce before the code is exchanged. A failed exchange must
        # not make the same state usable again.
        await session.commit()
        try:
            token_body, info = await _exchange(platform, code)
            await save_install(session, project.id, platform, token_body, info)
        except StoreApiError as exc:
            await session.rollback()
            log.warning("store oauth failed platform=%s status=%s", platform, exc.status)
            return _page(False)
    return _page(True)


async def _exchange(platform: str, code: str):
    if platform == "salla":
        from src.integrations.salla.client import SallaClient, exchange_code

        body = await exchange_code(code)
        access = str(body.get("access_token") or "")
        if not access:
            raise StoreApiError("token_response", 200)
        return body, await SallaClient(access).fetch_store()
    from src.integrations.zid.client import ZidClient, exchange_code

    body = await exchange_code(code)
    access = str(body.get("access_token") or "")
    authorization = str(body.get("authorization") or body.get("Authorization") or "")
    if not access or not authorization:
        raise StoreApiError("token_response", 200)
    return body, await ZidClient(access, authorization).fetch_store()


def _uninstall(platform: str, payload: dict) -> bool:
    if platform == "salla":
        from src.integrations.salla.webhooks import UNINSTALL, event_name

        return event_name(payload) == UNINSTALL
    from src.integrations.zid.webhooks import UNINSTALL, event_name

    return event_name(payload) == UNINSTALL or str(payload.get("status") or "") == "uninstall"


@router.post("/webhooks/stores/{platform}")
async def webhook(platform: str, request: Request):
    if platform not in ("salla", "zid"):
        raise HTTPException(404, "Unknown platform")
    _limit(limits.webhooks, f"{platform}:{client_ip(request)}")
    raw = await request.body()
    if len(raw) > _MAX_BODY:
        raise HTTPException(413, "Payload too large")
    if platform == "salla":
        from src.integrations.salla.webhooks import signature_ok

        if not signature_ok(raw, request.headers.get("x-salla-signature")):
            raise HTTPException(401, "Invalid signature")
    else:
        from src.integrations.zid.webhooks import signature_ok

        if not signature_ok(raw, request.headers):
            raise HTTPException(401, "Invalid signature")
    try:
        payload = json.loads(raw.decode() or "{}")
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    if not isinstance(payload, dict):
        raise HTTPException(400, "Invalid JSON")
    fresh = salla_fresh(payload) if platform == "salla" else zid_fresh(request.headers, payload)
    if not fresh:
        raise HTTPException(401, "Stale webhook")
    uninstall = _uninstall(platform, payload)
    if not enabled() and not uninstall:
        return {"ok": True, "ignored": True}
    async with _factory(request)() as session:
        if not await claim_event(session, platform, raw, payload):
            return {"ok": True, "duplicate": True}
        action = await apply_webhook(session, platform, payload) if (enabled() or uninstall) else "ignored"
        await session.commit()
    log.info("store webhook platform=%s action=%s", platform, action)
    return {"ok": True, "action": action}
