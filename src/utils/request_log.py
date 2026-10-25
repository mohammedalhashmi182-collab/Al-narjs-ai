"""One start line and one end line per HTTP request, sharing a request id.

A drop that never reaches the app has no start line. A drop after the handler
ran but before headers left has ``status=-``. The question, the body, the
query string and the raw path are not logged: the line carries the route
template, or a path with phones and ids masked when routing did not match.
"""

from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders

log = logging.getLogger(__name__)

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_HEX_ID_RE = re.compile(r"^[0-9a-fA-F]{16,}$")
# Arabic-Indic and Persian digits, so a phone written with them still counts.
_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def _mask_segment(segment: str) -> str:
    """Replace a phone, a UUID, or another id. Leave ordinary words alone."""
    if not segment or (segment.startswith("{") and segment.endswith("}")):
        return segment
    if _UUID_RE.fullmatch(segment):
        return "{id}"
    folded = segment.translate(_INDIC_DIGITS)
    if _HEX_ID_RE.fullmatch(folded):
        return "{id}"
    if sum(ch.isdigit() for ch in folded) >= 6:
        return "{n}"
    if _UUID_RE.search(segment):
        return _UUID_RE.sub("{id}", segment)
    return segment


def sanitized_path(path: str) -> str:
    """Fallback when routing did not attach a route template."""
    if not path:
        return "/"
    return "/".join(_mask_segment(part) for part in path.split("/"))


def route_for_log(scope: dict) -> str:
    """Route template after routing, else a path with phones and ids masked.

    ``scope['path']`` on portal contact routes is the customer's phone number.
    ``path_format`` is the template (``{contact}``) and is safe to log.
    """
    route = scope.get("route")
    template = getattr(route, "path_format", None)
    if isinstance(template, str) and template:
        return template
    return sanitized_path(scope.get("path") or "/")


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
        try:
            from src.services.error_monitor import request_id_var

            request_id_var.set(rid)
        except Exception:  # noqa: BLE001
            pass
        method = scope.get("method") or "-"
        raw_path = scope.get("path") or "/"
        if raw_path.startswith("/static/"):
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        state: dict = {"status": None}
        # Routing has not run yet, so this is the masked path. The end line
        # repeats the call and picks up the route template once it exists.
        log.info("http start id=%s method=%s route=%s", rid, method, route_for_log(scope))

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
            route = route_for_log(scope)
            if status is None:
                log.warning(
                    "http end id=%s method=%s route=%s status=- duration_ms=%s",
                    rid, method, route, duration_ms,
                )
            else:
                log.info(
                    "http end id=%s method=%s route=%s status=%s duration_ms=%s",
                    rid, method, route, status, duration_ms,
                )
