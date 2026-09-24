"""Thread-safe session scoping helpers for the shared-database tenant model.

``isolated_session`` yields a normal :class:`AsyncSession` built by the existing
factory while the tenant context is active (commit/rollback semantics are
identical to ``async with session_factory() as session``).

``tenant_filter`` attaches a ``tenant_id`` predicate to a query ONLY when both
(a) isolation is explicitly enabled for this context and (b) the target model
actually exposes a ``tenant_id`` column. Models without the column (or with
isolation off) are passed through untouched, keeping legacy behaviour intact.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

from src.core.architecture.tenant.context import (
    current_tenant_id,
    tenant_isolation_enabled,
    tenant_scope,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


def tenant_filter(query: Any, model: Any) -> Any:
    """Return ``query`` scoped to the current tenant where applicable.

    The query is returned unchanged when isolation is disabled, when no tenant
    is set, or when the model has no ``tenant_id`` attribute — so the function
    is safe to apply blindly to any SQLAlchemy statement.
    """
    if not tenant_isolation_enabled():
        return query
    tid = current_tenant_id()
    if not tid:
        return query
    if not hasattr(model, "tenant_id"):
        return query
    return query.where(model.tenant_id == tid)


@asynccontextmanager
async def isolated_session(
    session_factory: Any,
    tenant_id: Optional[str] = None,
) -> AsyncGenerator[Any, None]:
    """Open a session inside the given (or inherited) tenant context.

    The concrete tenant id is stamped on the session as a harmless attribute so
    downstream audit/telemetry code can read ``session.tenant_id`` without
    changing any query behaviour.
    """
    resolved = tenant_id or current_tenant_id()
    with tenant_scope(resolved, isolate=bool(tenant_id)):
        async with session_factory() as session:
            setattr(session, "tenant_id", resolved or "system")
            yield session
