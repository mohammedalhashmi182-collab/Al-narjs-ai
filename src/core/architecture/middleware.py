"""Additive ASGI middleware: carries an optional ``X-Tenant-Id`` request
header into the ContextVar tenant context, restoring it after the response.

The middleware is purely informational: it does NOT enable tenant filtering by
itself. Isolation only activates when a controller opts in via
``isolated_session``/``webhook_guard`` with an explicit tenant id, so existing
traffic (which sends no tenant header) is byte-for-byte unchanged.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import structlog

from src.core.architecture.tenant.context import tenant_scope

TENANT_HEADER = "x-tenant-id"
DEFAULT_TENANT = "system"


class TenantMiddleware:
    """Reads ``X-Tenant-Id`` (when present) and sets the tenant context."""

    def __init__(
        self,
        app: Any,
        header: str = TENANT_HEADER,
        default_tenant: Optional[str] = None,
    ) -> None:
        self.app = app
        self.header = header
        self.default_tenant: str = default_tenant or DEFAULT_TENANT

    async def __call__(self, scope: Dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        tenant_id = self.default_tenant
        try:
            needle = self.header.encode("latin-1").lower()
            for name, value in scope.get("headers") or []:
                if name.lower() == needle:
                    candidate = value.decode("latin-1").strip()
                    if candidate:
                        tenant_id = candidate
                    break
        except Exception:
            pass

        with tenant_scope(tenant_id):
            try:
                structlog.contextvars.bind_contextvars(tenant_id=tenant_id)
            except Exception:
                pass
            try:
                await self.app(scope, receive, send)
            finally:
                try:
                    structlog.contextvars.unbind_contextvars("tenant_id")
                except Exception:
                    pass
