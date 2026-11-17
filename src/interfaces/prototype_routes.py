"""Live prototype pages for the prototype engineer.

GET  /p/{token}       shell: banner + sandboxed iframe
GET  /p/{token}/app   sanitized document, strict CSP, frameable only by us
POST /api/prototypes  owner or an active portal session
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.services import prototype_live

router = APIRouter()


class PrototypeBody(BaseModel):
    idea: str = Field(min_length=1, max_length=8000)
    users: str = Field(default="", max_length=2000)
    platform: str = Field(default="web", max_length=200)
    project_id: str | None = None


def _app_response(document: str) -> HTMLResponse:
    return HTMLResponse(
        document,
        headers={
            "Content-Security-Policy": prototype_live.PROTOTYPE_APP_CSP,
            "X-Frame-Options": "SAMEORIGIN",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "X-Robots-Tag": "noindex, nofollow",
            "Cache-Control": "private, no-store",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
        },
    )


async def _load_project(session, project_id: str):
    from uuid import UUID

    from src.models import ClientProject

    try:
        key = UUID(str(project_id))
    except ValueError:
        return None
    return (await session.execute(select(ClientProject).where(ClientProject.id == key))).scalar_one_or_none()


async def _actor(request: Request, session, body: PrototypeBody):
    """Owner, or the portal session's own active project. Never another tenant."""
    from src.core.owner_auth import check_owner
    from src.core.portal_auth import session_claims, session_valid_for

    if check_owner(request):
        project = None
        if body.project_id:
            project = await _load_project(session, body.project_id)
            if project is None:
                raise HTTPException(404, "Project not found")
            if project.status != "active":
                raise HTTPException(402, "Subscription not active — activate your plan first")
        return project
    claims = session_claims(request)
    project_id = (claims or {}).get("p")
    if not project_id:
        raise HTTPException(401, "Portal login required")
    if body.project_id and body.project_id != str(project_id):
        raise HTTPException(403, "Portal login required")
    project = await _load_project(session, str(project_id))
    if not session_valid_for(claims, project):
        raise HTTPException(401, "Portal login required")
    if project.status != "active":
        raise HTTPException(402, "Subscription not active — activate your plan first")
    return project


@router.get("/p/{token}/app", response_class=HTMLResponse)
async def prototype_app(token: str, request: Request):
    if not prototype_live.valid_token(token):
        raise HTTPException(404, "Prototype not found")
    from src.models.prototype import LivePrototype

    async with request.app.state.session_factory() as session:
        row = (
            await session.execute(select(LivePrototype).where(LivePrototype.token == token))
        ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Prototype not found")
    return _app_response(row.html)


@router.get("/p/{token}", response_class=HTMLResponse)
async def prototype_shell(token: str, request: Request):
    if not prototype_live.valid_token(token):
        raise HTTPException(404, "Prototype not found")
    from src.main import templates
    from src.models.prototype import LivePrototype

    async with request.app.state.session_factory() as session:
        exists = (
            await session.execute(select(LivePrototype.id).where(LivePrototype.token == token))
        ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(404, "Prototype not found")
    response = templates.TemplateResponse(
        request,
        "prototype_shell.html",
        {"token": token, "frame_src": prototype_live.public_path(token) + "/app"},
    )
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.post("/api/prototypes")
async def create_prototype(body: PrototypeBody, request: Request):
    from src.services import usage

    async with request.app.state.session_factory() as session:
        project = await _actor(request, session, body)
        try:
            await prototype_live.prepare(request, session, project, body.idea, body.users, body.platform)
            token = await prototype_live.generate_and_store(
                session,
                model_provider=request.app.state.model_provider,
                idea=body.idea,
                users=body.users,
                platform=body.platform,
                locale=request.cookies.get("narjis_lang", "ar"),
                project_id=str(project.id) if project is not None else None,
            )
            if project is not None:
                await usage.record_conversation(
                    session, project, f"prototype:{project.id}", "portal", ref=token,
                )
            await session.commit()
        except prototype_live.PrototypeRejected as exc:
            raise HTTPException(400, exc.message_ar) from None
        except prototype_live.PrototypeLimited as exc:
            raise HTTPException(exc.status, exc.message_ar) from None
        except prototype_live.PrototypeGenerationError:
            raise HTTPException(502, "تعذر بناء الصفحة التجريبية الآن. حاول مرة أخرى.") from None
    return {
        "url": prototype_live.public_path(token),
        "open_url": prototype_live.public_url(token),
        "status": "ready",
    }
