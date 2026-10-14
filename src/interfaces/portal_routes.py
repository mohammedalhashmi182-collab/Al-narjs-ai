"""Customer portal: login (OTP / magic link / legacy exchange) and the Tenant
Reply Agent review queue, contacts and human handoff.

  POST /api/portal/login/request              {identifier: email|phone}  -> OTP (always 200)
  POST /api/portal/login/verify               {identifier, code}         -> session cookie
  GET  /portal/login?token=...                single-use magic link      -> cookie + redirect
  POST /api/portal/session/legacy             {project_id} (never-paid projects only, limited session)
  GET  /api/portal/session | POST /api/portal/logout
  GET  /api/portal/projects/{pid}/replies?status=pending
  POST /api/portal/projects/{pid}/replies/{draft_id}/approve|reject
  GET  /api/portal/projects/{pid}/contacts
  POST /api/portal/projects/{pid}/contacts/{contact}/reply|release
  GET/POST /api/portal/projects/{pid}/reply-settings   (customer: off|review)
Owner (cookie auth):
  POST /api/owner/projects/{pid}/reply-settings   {mode: off|review|auto}
  POST /api/owner/projects/{pid}/whatsapp-token   {token}  (stored encrypted, never returned)
  POST /api/owner/projects/{pid}/portal-link      -> single-use magic link for the customer
  POST /api/owner/projects/{pid}/portal-revoke    -> ends every portal session
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import func, select

from src.core import portal_auth
from src.core.owner_auth import require_owner
from src.models import ClientProject
from src.models.tenant import PortalLoginCode
from src.services import tenant_reply
from src.services.lead_normalize import normalize_phone

log = logging.getLogger(__name__)
router = APIRouter()

OTP_PER_15MIN = 3


def _factory(request: Request):
    return request.app.state.session_factory


def _uuid(value: str) -> UUID:
    try:
        return UUID(str(value))
    except ValueError:
        raise HTTPException(404, "Not found")


def _aware(dt):
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=UTC)


def _base_url(request: Request) -> str:
    from src.config.settings import settings

    return (settings.public_base_url or str(request.base_url)).rstrip("/")


# ---------------------------------------------------------------- login: OTP
class IdentBody(BaseModel):
    identifier: str
    code: Optional[str] = None
    project_id: Optional[str] = None


def _ident(value: str) -> tuple[str, str]:
    v = (value or "").strip()
    if "@" in v:
        return "email", v.lower()[:255]
    return "phone", (normalize_phone(v) or re.sub(r"\D", "", v))[:64]


async def _projects_for(session, kind: str, ident: str) -> list[ClientProject]:
    if not ident:
        return []
    if kind == "email":
        q = select(ClientProject).where(func.lower(ClientProject.email) == ident)
        return list((await session.execute(q.order_by(ClientProject.created_at.desc()))).scalars())
    tail = re.sub(r"\D", "", ident)[-9:]
    if len(tail) < 9:
        return []
    rows = (await session.execute(select(ClientProject).where(ClientProject.phone.like(f"%{tail[-4:]}%"))
                                  .order_by(ClientProject.created_at.desc()))).scalars()
    return [p for p in rows if re.sub(r"\D", "", normalize_phone(p.phone) or p.phone or "").endswith(tail)]


async def _deliver_otp(factory, project: ClientProject, kind: str, code: str) -> None:
    """Email when the project has one, else WhatsApp from Al-Narjis's number (best effort)."""
    text = f"رمز الدخول إلى بوابة النرجس: {code}\nصالح 10 دقائق. لا تشاركه مع أي أحد."
    try:
        if project.email:
            from src.services import email_service

            if email_service.is_configured():
                await email_service.send_email(project.email, "رمز الدخول إلى البوابة", text)
                return
        from src.services import whatsapp_sender

        if whatsapp_sender.is_enabled():
            async with factory() as s:
                await whatsapp_sender.send_now(s, lead_id=None, phone=project.phone, text=text)
                await s.commit()
    except Exception:  # noqa: BLE001 - never leak delivery errors (or the code) to the caller
        log.warning("portal OTP delivery failed for project %s", project.id)


@router.post("/api/portal/login/request")
async def login_request(body: IdentBody, request: Request):
    kind, ident = _ident(body.identifier)
    now = datetime.now(UTC)
    async with _factory(request)() as session:
        projects = await _projects_for(session, kind, ident)
        if body.project_id:
            projects = [p for p in projects if str(p.id) == body.project_id]
        if projects:
            recent = (await session.execute(select(func.count()).select_from(PortalLoginCode).where(
                PortalLoginCode.identifier == ident, PortalLoginCode.kind == "otp",
                PortalLoginCode.created_at >= now - timedelta(minutes=15)))).scalar_one()
            if recent < OTP_PER_15MIN:
                project = projects[0]
                code = portal_auth.new_otp()
                session.add(PortalLoginCode(project_id=project.id, kind="otp", identifier=ident,
                                            code_hash=portal_auth.hash_secret(code),
                                            expires_at=now + timedelta(seconds=portal_auth.OTP_TTL)))
                await session.commit()
                await _deliver_otp(_factory(request), project, kind, code)
    # Same answer whether or not the identifier exists (no account enumeration).
    return {"sent": True, "channel": kind, "expires_in": portal_auth.OTP_TTL}


@router.post("/api/portal/login/verify")
async def login_verify(body: IdentBody, request: Request):
    kind, ident = _ident(body.identifier)
    code = re.sub(r"\D", "", body.code or "")
    now = datetime.now(UTC)
    async with _factory(request)() as session:
        row = (await session.execute(select(PortalLoginCode).where(
            PortalLoginCode.identifier == ident, PortalLoginCode.kind == "otp", PortalLoginCode.used_at.is_(None),
        ).order_by(PortalLoginCode.created_at.desc()).limit(1))).scalar_one_or_none()
        if row is None or _aware(row.expires_at) < now or row.attempts >= portal_auth.OTP_MAX_ATTEMPTS:
            raise HTTPException(401, "الرمز غير صالح أو منتهي")
        if not code or portal_auth.hash_secret(code) != row.code_hash:
            row.attempts += 1
            await session.commit()
            raise HTTPException(401, "الرمز غير صالح أو منتهي")
        row.used_at = now
        project = await session.get(ClientProject, row.project_id)
        await session.commit()
    resp = JSONResponse({"project_id": str(project.id)})
    return portal_auth.set_session_cookie(resp, project)


# ---------------------------------------------------------------- login: magic link
@router.get("/portal/login")
async def magic_login(token: str, request: Request):
    claims = portal_auth.read_magic_token(token)
    now = datetime.now(UTC)
    async with _factory(request)() as session:
        row = None
        if claims:
            row = (await session.execute(select(PortalLoginCode).where(
                PortalLoginCode.project_id == _uuid(claims["p"]), PortalLoginCode.kind == "magic",
                PortalLoginCode.code_hash == portal_auth.hash_secret(str(claims.get("n"))),
            ))).scalar_one_or_none()
        if row is None or row.used_at is not None or _aware(row.expires_at) < now:
            return RedirectResponse("/portal?login=expired", status_code=303)
        row.used_at = now
        project = await session.get(ClientProject, row.project_id)
        await session.commit()
    return portal_auth.set_session_cookie(RedirectResponse("/portal", status_code=303), project)


# ---------------------------------------------------------------- legacy + session
class LegacyBody(BaseModel):
    project_id: str


@router.post("/api/portal/session/legacy")
async def legacy_exchange(body: LegacyBody, request: Request):
    """Old browsers kept only the project UUID. Unpaid projects may trade it for a
    limited session (checkout in flight); active subscriptions must log in."""
    async with _factory(request)() as session:
        try:
            project = await session.get(ClientProject, UUID(body.project_id))
        except ValueError:
            project = None
    if not portal_auth.legacy_allowed(project):
        raise HTTPException(401, "Portal login required")
    return portal_auth.set_session_cookie(JSONResponse({"project_id": str(project.id), "limited": True}),
                                          project, limited=True)


@router.get("/api/portal/session")
async def current_session(request: Request, probe: bool = False):
    # ?probe=1 is the portal's on-load "am I signed in?" check: an anonymous
    # visitor is the normal case there, so it answers 200 {"authenticated": false}
    # instead of a 401 that every browser logs as a console error on checkout.
    def _anon():
        if probe:
            return {"authenticated": False}
        raise HTTPException(401, "Portal login required")

    claims = portal_auth.session_claims(request)
    if not claims:
        return _anon()
    async with _factory(request)() as session:
        project = await session.get(ClientProject, _uuid(claims["p"]))
    if not portal_auth.session_valid_for(claims, project):
        return _anon()
    return {"authenticated": True, "project_id": str(project.id), "status": project.status}


@router.post("/api/portal/logout")
async def logout():
    return portal_auth.clear_session_cookie(JSONResponse({"ok": True}))


# ---------------------------------------------------------------- tenant review queue
class TextBody(BaseModel):
    text: Optional[str] = None
    mode: Optional[str] = None
    token: Optional[str] = None


def _draft(d) -> dict:
    return {"id": str(d.id), "recipient": d.recipient, "kind": d.kind, "inbound_text": d.inbound_text,
            "draft_text": d.draft_text, "final_text": d.final_text, "status": d.status,
            "meta": {k: v for k, v in (d.meta or {}).items() if k in ("intent", "kb", "handoff", "queued", "human")},
            "send_result": d.send_result, "created_at": d.created_at.isoformat() if d.created_at else None}


@router.get("/api/portal/projects/{pid}/replies")
async def portal_replies(pid: str, request: Request, status: str = "pending"):
    async with _factory(request)() as session:
        project = await portal_auth.require_portal_project(session, request, pid)
        rows = await tenant_reply.list_drafts(session, project.id, status=status or None)
        return {"mode": tenant_reply.mode_of(project), "can_send": tenant_reply.can_send(project),
                "drafts": [_draft(d) for d in rows]}


async def _decide(request: Request, pid: str, draft_id: str, action: str, text: str | None):
    async with _factory(request)() as session:
        project = await portal_auth.require_portal_project(session, request, pid)
        try:
            d = await tenant_reply.get_draft(session, project.id, _uuid(draft_id))
        except LookupError:
            raise HTTPException(404, "Not found")
        if d.status != "pending":
            raise HTTPException(409, f"draft already {d.status}")
        if action == "reject":
            d.status = "rejected"
            d.decided_at = datetime.now(UTC)
        else:
            if text and text.strip():
                d.final_text = text.strip()[:4000]
            await tenant_reply.send_draft(session, d, project)
        await session.commit()
        return _draft(d)


@router.post("/api/portal/projects/{pid}/replies/{draft_id}/approve")
async def portal_approve(pid: str, draft_id: str, request: Request, body: TextBody | None = None):
    return await _decide(request, pid, draft_id, "approve", body.text if body else None)


@router.post("/api/portal/projects/{pid}/replies/{draft_id}/reject")
async def portal_reject(pid: str, draft_id: str, request: Request):
    return await _decide(request, pid, draft_id, "reject", None)


@router.get("/api/portal/projects/{pid}/contacts")
async def portal_contacts(pid: str, request: Request):
    async with _factory(request)() as session:
        project = await portal_auth.require_portal_project(session, request, pid)
        return {"contacts": [tenant_reply.contact_to_dict(c) for c in await tenant_reply.list_contacts(session, project.id)]}


@router.post("/api/portal/projects/{pid}/contacts/{contact}/reply")
async def portal_manual_reply(pid: str, contact: str, body: TextBody, request: Request):
    async with _factory(request)() as session:
        project = await portal_auth.require_portal_project(session, request, pid)
        try:
            d = await tenant_reply.manual_reply(session, project, contact, body.text or "")
        except LookupError:
            raise HTTPException(404, "Not found")
        except ValueError as e:
            raise HTTPException(400, str(e))
        await session.commit()
        return _draft(d)


@router.post("/api/portal/projects/{pid}/contacts/{contact}/release")
async def portal_release(pid: str, contact: str, request: Request):
    """End a human handoff: the agent answers this contact again."""
    async with _factory(request)() as session:
        project = await portal_auth.require_portal_project(session, request, pid)
        c = await tenant_reply._contact(session, project.id, contact)
        if c is None:
            raise HTTPException(404, "Not found")
        c.handoff_at, c.handoff_reason = None, None
        await session.commit()
        return tenant_reply.contact_to_dict(c)


@router.get("/api/portal/projects/{pid}/reply-settings")
async def portal_get_settings(pid: str, request: Request):
    async with _factory(request)() as session:
        project = await portal_auth.require_portal_project(session, request, pid)
        return {"mode": tenant_reply.mode_of(project), "can_send": tenant_reply.can_send(project),
                "number_linked": bool(project.wa_phone_number_id)}


@router.post("/api/portal/projects/{pid}/reply-settings")
async def portal_set_settings(pid: str, body: TextBody, request: Request):
    if body.mode not in ("off", "review"):
        raise HTTPException(403, "Auto-send is enabled by Al-Narjis after the review period")
    async with _factory(request)() as session:
        project = await portal_auth.require_portal_project(session, request, pid)
        project.reply_mode = body.mode
        await session.commit()
        return {"mode": project.reply_mode}


# ---------------------------------------------------------------- owner controls
async def _owner_project(session, pid: str) -> ClientProject:
    project = await session.get(ClientProject, _uuid(pid))
    if project is None:
        raise HTTPException(404, "Project not found")
    return project


@router.post("/api/owner/projects/{pid}/reply-settings", dependencies=[Depends(require_owner)])
async def owner_set_mode(pid: str, body: TextBody, request: Request):
    if body.mode not in tenant_reply.MODES:
        raise HTTPException(422, "mode must be off|review|auto")
    async with _factory(request)() as session:
        project = await _owner_project(session, pid)
        project.reply_mode = body.mode
        await session.commit()
        return {"project_id": pid, "mode": project.reply_mode, "can_send": tenant_reply.can_send(project)}


@router.post("/api/owner/projects/{pid}/whatsapp-token", dependencies=[Depends(require_owner)])
async def owner_set_token(pid: str, body: TextBody, request: Request):
    token = (body.token or "").strip()
    async with _factory(request)() as session:
        project = await _owner_project(session, pid)
        project.wa_access_token_enc = tenant_reply.encrypt_token(token) if token else None
        await session.commit()
        return {"project_id": pid, "token_configured": bool(token), "can_send": tenant_reply.can_send(project)}


@router.post("/api/owner/projects/{pid}/portal-link", dependencies=[Depends(require_owner)])
async def owner_portal_link(pid: str, request: Request):
    nonce = portal_auth.new_nonce()
    async with _factory(request)() as session:
        project = await _owner_project(session, pid)
        session.add(PortalLoginCode(project_id=project.id, kind="magic", code_hash=portal_auth.hash_secret(nonce),
                                    expires_at=datetime.now(UTC) + timedelta(seconds=portal_auth.MAGIC_TTL)))
        await session.commit()
    token = portal_auth.make_magic_token(project.id, nonce)
    return {"url": f"{_base_url(request)}/portal/login?token={token}", "expires_in": portal_auth.MAGIC_TTL}


@router.post("/api/owner/projects/{pid}/portal-revoke", dependencies=[Depends(require_owner)])
async def owner_portal_revoke(pid: str, request: Request):
    async with _factory(request)() as session:
        project = await _owner_project(session, pid)
        project.portal_token_version = int(project.portal_token_version or 0) + 1
        await session.commit()
        return {"project_id": pid, "portal_token_version": project.portal_token_version}
