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
# How many closes outlived the deadline. The close itself is not cancelled.
_session_close_timeouts = 0
_background_closes: set[asyncio.Task] = set()


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


def _track_close(task: asyncio.Task) -> None:
    """Keep a reference so the close is not garbage-collected mid-flight."""
    _background_closes.add(task)

    def _done(done: asyncio.Task) -> None:
        _background_closes.discard(done)
        try:
            exc = done.exception()
        except asyncio.CancelledError:
            return
        if exc is not None:
            # Type only. The driver message can echo the SQL, which contains the question.
            log.warning("ai ask session close failed error=%s", type(exc).__name__)

    task.add_done_callback(_done)


async def _invalidate_session(session) -> None:
    """Drop the connection if close is still running. Failures are logged, not raised."""
    invalidate = getattr(session, "invalidate", None)
    if invalidate is None:
        return
    try:
        result = invalidate()
        if asyncio.iscoroutine(result):
            await result
    except Exception as exc:  # noqa: BLE001 — concurrent close may already own the session
        log.warning("ai ask session invalidate failed error=%s", type(exc).__name__)


async def _close_session(session_cm, session=None) -> None:
    """Finish ``close()`` even when it misses the deadline.

    ``wait_for`` cancels the inner awaitable on timeout. The close is shielded
    and kept alive in the background, the timeout is counted, and ``invalidate``
    runs beside it so a stuck connection is not returned to the pool.
    """
    global _session_close_timeouts
    task = asyncio.create_task(session_cm.__aexit__(None, None, None))
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=_SESSION_CLOSE_TIMEOUT_S)
    except asyncio.CancelledError:
        _track_close(task)
        raise
    except TimeoutError:
        _session_close_timeouts += 1
        log.warning("ai ask session close timed out count=%s", _session_close_timeouts)
        _track_close(task)
        if session is not None:
            _track_close(asyncio.create_task(_invalidate_session(session)))
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
        await _close_session(session_cm, session)
    # One JSON body, content-length = UTF-8 byte length. Not a restreamed buffer.
    return JSONResponse(result.as_dict())
