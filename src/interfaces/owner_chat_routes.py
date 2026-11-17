"""Owner-only chat and agent instructions. The public site does not use these routes."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.core.owner_auth import require_owner
from src.services import owner_chat
from src.utils.rate_limit import rate_limit_owner_chat

router = APIRouter(tags=["owner-chat"])


class ChatIn(BaseModel):
    message: str | None = None
    conversation_id: str | None = None
    agent: str | None = None
    slug: str | None = None
    agents: list[str] | None = None


class CreateIn(BaseModel):
    name_ar: str | None = None
    role_ar: str | None = None
    instructions: str | None = None


class UpdateIn(BaseModel):
    name_ar: str | None = None
    role_ar: str | None = None
    instructions: str | None = None
    enabled: bool | None = None


def _error(exc: owner_chat.OwnerChatError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"ok": False, "detail": exc.text})


@router.get("/api/owner/chat/agents")
async def list_owner_agents(request: Request):
    require_owner(request)
    factory = request.app.state.session_factory
    async with factory() as session:
        views = await owner_chat.list_views(session)
    return {"agents": [view.as_dict() for view in views]}


@router.post("/api/owner/chat/agents")
async def create_owner_agent(body: CreateIn, request: Request):
    require_owner(request)
    factory = request.app.state.session_factory
    async with factory() as session:
        try:
            view = await owner_chat.create_custom(
                session,
                body.name_ar or "",
                body.role_ar or "",
                body.instructions or "",
            )
            await session.commit()
        except owner_chat.OwnerChatError as exc:
            await session.rollback()
            return _error(exc)
    return view.as_dict()


@router.patch("/api/owner/chat/agents/{slug}")
async def update_owner_agent(slug: str, body: UpdateIn, request: Request):
    require_owner(request)
    factory = request.app.state.session_factory
    async with factory() as session:
        try:
            view = await owner_chat.update_agent(session, slug, body.model_dump(exclude_unset=True))
            await session.commit()
        except owner_chat.OwnerChatError as exc:
            await session.rollback()
            return _error(exc)
    return view.as_dict()


@router.post("/api/owner/chat")
async def owner_chat_turn(body: ChatIn, request: Request):
    require_owner(request)
    rate_limit_owner_chat(request)
    factory = request.app.state.session_factory
    provider = getattr(request.app.state, "model_provider", None)
    async with factory() as session:
        try:
            result = await owner_chat.converse(
                session,
                provider,
                message=body.message or "",
                conversation_id=body.conversation_id,
                agent=body.agent,
                slug=body.slug,
                agents=body.agents,
            )
            await session.commit()
        except owner_chat.OwnerChatError as exc:
            await session.rollback()
            return _error(exc)
    return result
