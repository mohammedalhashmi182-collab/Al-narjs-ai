"""Public CEO brief and the owner list of those briefs.

POST /api/engagement
POST /api/engagement/{token}/message
GET  /api/engagement/{token}
GET  /api/owner/engagements
GET  /brief
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from src.core.owner_auth import require_owner
from src.utils.rate_limit import rate_limit_engagement

router = APIRouter()


class StartBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    lang: str | None = None
    name: str = ""
    phone: str = ""
    email: str = ""


class TurnBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


def _factory(request: Request):
    return request.app.state.session_factory


def _provider(request: Request):
    return getattr(request.app.state, "model_provider", None)


@router.post("/api/engagement", dependencies=[Depends(rate_limit_engagement)])
async def start(body: StartBody, request: Request):
    from src.services.customer_engagement import open_engagement, public_view

    locale = body.lang if body.lang in ("ar", "en") else request.cookies.get("narjis_lang", "ar")
    async with _factory(request)() as session:
        engagement = await open_engagement(
            session,
            message=body.message,
            locale=locale or "ar",
            name=body.name.strip()[:120],
            phone=body.phone.strip()[:32],
            email=body.email.strip()[:255],
            provider=_provider(request),
        )
        await session.commit()
        await session.refresh(engagement)
        return public_view(engagement)


@router.post("/api/engagement/{token}/message", dependencies=[Depends(rate_limit_engagement)])
async def turn(token: str, body: TurnBody, request: Request):
    from src.services.customer_engagement import apply_turn, by_token, public_view

    async with _factory(request)() as session:
        engagement = await by_token(session, token)
        if engagement is None:
            raise HTTPException(404, "Not found")
        await apply_turn(session, engagement, body.message, provider=_provider(request))
        await session.commit()
        await session.refresh(engagement)
        return public_view(engagement)


@router.get("/api/engagement/{token}")
async def read(token: str, request: Request):
    from src.services.customer_engagement import by_token, public_view

    async with _factory(request)() as session:
        engagement = await by_token(session, token)
        if engagement is None:
            raise HTTPException(404, "Not found")
        return public_view(engagement)


@router.get("/api/owner/engagements", dependencies=[Depends(require_owner)])
async def owner_list(request: Request):
    from src.services.customer_engagement import list_recent

    async with _factory(request)() as session:
        return {"engagements": await list_recent(session)}


@router.get("/brief", response_class=HTMLResponse)
async def brief_page(request: Request):
    from src.main import templates

    lang = request.cookies.get("narjis_lang", "ar")
    return templates.TemplateResponse(request, "brief.html", {"ar": lang != "en"})
