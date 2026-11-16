"""Owner dashboard: start the AI CEO scout and approve drafts locally."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.core.owner_auth import require_owner
from src.services import ceo_scout

router = APIRouter(
    prefix="/api/owner/ceo",
    dependencies=[Depends(require_owner)],
    tags=["ceo-scout"],
)


class DecideBody(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")


@router.post("/start")
async def start_ceo(request: Request):
    return await ceo_scout.start_search(request.app.state.session_factory)


@router.get("/scout")
async def scout_status(request: Request):
    return await ceo_scout.current_status(request.app.state.session_factory)


@router.post("/opportunities/{key}/decide")
async def decide_opportunity(key: str, body: DecideBody, request: Request):
    result = await ceo_scout.decide(request.app.state.session_factory, key, body.decision)
    if result is None:
        raise HTTPException(404, "opportunity not found")
    return result
