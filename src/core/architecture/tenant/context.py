"""ContextVar-based tenant context (thread/async-safe, per-request isolation).

The platform runs on a single shared database. The active tenant id travels in
a :class:`contextvars.ContextVar`, so concurrent requests on the same process
each observe their own tenant without any global mutable state.

``tenant_isolation_enabled`` stays OFF unless it is explicitly turned on. With
isolation off the system behaves exactly as before (the original single-tenant
behaviour) — this is the switch that guarantees zero-downtime adoption.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Human-facing default when no tenant context is supplied.
DEFAULT_TENANT = "system"

_TENANT_ID: ContextVar[Optional[str]] = ContextVar("narjis_tenant_id", default=None)
_ISOLATION_ENABLED: ContextVar[bool] = ContextVar(
    "narjis_tenant_isolation", default=False
)


def set_tenant(tenant_id: Optional[str]) -> Token:
    """Set the active tenant id for the calling context.

    Returns the :class:`contextvars.Token` needed to restore the previous value.
    """
    return _TENANT_ID.set(tenant_id)


def reset_tenant(token: Token) -> None:
    """Restore the tenant context to the value held before ``set_tenant``."""
    _TENANT_ID.reset(token)


def current_tenant_id() -> Optional[str]:
    """Active tenant id for the calling context (``None`` when unset)."""
    return _TENANT_ID.get()


def tenant_name() -> str:
    """Active tenant id with the safe default substituted for display."""
    return current_tenant_id() or DEFAULT_TENANT


def enable_isolation(enabled: bool = True) -> Token:
    """Turn tenant filtering on (or off). Returns the reset token."""
    return _ISOLATION_ENABLED.set(enabled)


def reset_isolation(token: Token) -> None:
    """Restore the previous isolation flag value."""
    _ISOLATION_ENABLED.reset(token)


def tenant_isolation_enabled() -> bool:
    """True when tenant-scoped query filtering is active in this context."""
    return _ISOLATION_ENABLED.get()


@contextmanager
def tenant_scope(tenant_id: Optional[str], isolate: bool = False) -> Iterator[str]:
    """Run a block inside an isolated tenant context.

    ``isolate=False`` (the default) keeps single-tenant passthrough behaviour:
    filtering stays off and the handled code path is byte-for-byte identical to
    the pre-architecture release.
    """
    resolved = str(tenant_id or DEFAULT_TENANT)
    t_id = _TENANT_ID.set(resolved)
    t_iso = _ISOLATION_ENABLED.set(isolate)
    logger.debug("tenant_scope enter", tenant_id=resolved, isolate=isolate)
    try:
        yield resolved
    finally:
        _ISOLATION_ENABLED.reset(t_iso)
        _TENANT_ID.reset(t_id)
