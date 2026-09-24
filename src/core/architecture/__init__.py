"""Architectural middleware: tenant isolation, agent catalog, dynamic
routing and self-correction, exposed as one additive, non-breaking package."""

from src.core.architecture.controller import GuardedConsult, process_webhook
from src.core.architecture.middleware import DEFAULT_TENANT, TENANT_HEADER, TenantMiddleware
from src.core.architecture.registry.agent_catalog import (
    AgentCapability,
    AgentCatalog,
    CatalogMatch,
)
from src.core.architecture.router.dynamic_router import (
    DynamicRouter,
    RouteDecision,
    RouterResult,
    RouteStrategy,
)
from src.core.architecture.tenant.context import (
    current_tenant_id,
    enable_isolation,
    tenant_isolation_enabled,
    tenant_name,
    tenant_scope,
)
from src.core.architecture.tenant.scope import isolated_session, tenant_filter
from src.core.architecture.validation.self_correction import (
    CorrectionStats,
    OutputValidator,
    SelfCorrectionLoop,
    ValidationOutcome,
)

__all__ = [
    "DEFAULT_TENANT",
    "TENANT_HEADER",
    "AgentCapability",
    "AgentCatalog",
    "CatalogMatch",
    "CorrectionStats",
    "DynamicRouter",
    "GuardedConsult",
    "OutputValidator",
    "RouteDecision",
    "RouteStrategy",
    "RouterResult",
    "SelfCorrectionLoop",
    "TenantMiddleware",
    "ValidationOutcome",
    "current_tenant_id",
    "enable_isolation",
    "isolated_session",
    "process_webhook",
    "tenant_filter",
    "tenant_isolation_enabled",
    "tenant_name",
    "tenant_scope",
]
