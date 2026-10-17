"""One start line and one end line per HTTP request, sharing a request id.

A drop that never reaches the app has no start line. A drop after the handler
ran but before headers left has ``status=-``. The question and the body are
not logged.
"""

from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders

log = logging.getLogger(__name__)

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _request_id(scope: dict) -> str:
    for name, value in scope.get("headers") or []:
        if name.lower() == b"x-request-id":
            text = value.decode("latin-1", "ignore").strip()
            if _ID_RE.fullmatch(text):
                return text
            break
    return uuid.uuid4().hex[:16]


class RequestLogMiddleware:
    """Pure ASGI. The body is forwarded unchanged, with ``X-Request-Id`` added."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        rid = _request_id(scope)
        method = scope.get("method") or "-"
        path = scope.get("path") or "/"
        if path.startswith("/static/"):
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        state: dict = {"status": None}
        log.info("http start id=%s method=%s path=%s", rid, method, path)

        async def send_wrapper(message):
            if message["type"] == "http.response.start" and state["status"] is None:
                state["status"] = int(message.get("status") or 0)
                headers = MutableHeaders(scope=message)
                headers.setdefault("x-request-id", rid)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = int((time.perf_counter() - started) * 1000)
            status = state["status"]
            if status is None:
                log.warning(
                    "http end id=%s method=%s path=%s status=- duration_ms=%s",
                    rid, method, path, duration_ms,
                )
            else:
                log.info(
                    "http end id=%s method=%s path=%s status=%s duration_ms=%s",
                    rid, method, path, status, duration_ms,
                )
