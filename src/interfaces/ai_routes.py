"""POST /api/ai/ask — pgvector RAG answer with fast/deep routing, review and human handoff.

The question is a customer message and may contain PII. It is not logged.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.ai import router as ai_router
from src.utils.rate_limit import rate_limit_ai_ask

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["ai"])

# Closing the DB session must not hold the answer hostage. A dead Postgres
# connection raises or blocks inside session.close() after the answer exists;
# the access line is written only once the response starts, so a hang here is
# what the client sees as a dropped TLS connection.
_SESSION_CLOSE_TIMEOUT_S = 2.0


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


async def _close_session(session_cm) -> None:
    try:
        await asyncio.wait_for(
            session_cm.__aexit__(None, None, None),
            timeout=_SESSION_CLOSE_TIMEOUT_S,
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        # Type only. The driver message can echo the SQL, which contains the question.
        log.warning("ai ask session close failed error=%s", type(exc).__name__)


@router.post("/ask", dependencies=[Depends(rate_limit_ai_ask)])
async def ask(body: AskIn, request: Request) -> JSONResponse:
    factory = request.app.state.session_factory
    session_cm = factory()
    session = await session_cm.__aenter__()
    try:
        result = await ai_router.ask(body.question, session=session)
    finally:
        await _close_session(session_cm)
    # One JSON body, content-length = UTF-8 byte length. Not a restreamed buffer.
    return JSONResponse(result.as_dict())
