"""POST /api/ai/ask — pgvector RAG answer with fast/deep routing, review and human handoff.

The question is a customer message and may contain PII. It is not logged.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from src.ai import router as ai_router
from src.utils.rate_limit import rate_limit_ai_ask

router = APIRouter(prefix="/api/ai", tags=["ai"])


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


@router.post("/ask", dependencies=[Depends(rate_limit_ai_ask)])
async def ask(body: AskIn, request: Request) -> dict:
    factory = request.app.state.session_factory
    async with factory() as session:
        result = await ai_router.ask(body.question, session=session)
    return result.as_dict()
