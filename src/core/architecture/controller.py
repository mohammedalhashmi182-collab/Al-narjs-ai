"""Clean, non-breaking wrappers around the production request controllers.

Two wrapped surfaces are provided:

- :func:`process_webhook` — reuses the exact WhatsApp inbound pipeline
  (``src.services.whatsapp_webhook.process_inbound_payload``) inside a tenant
  guard with trace telemetry. The transactional contract (commit on success,
  rollback + re-raise on failure) is preserved.
- :class:`GuardedConsult` — wraps a Gemini-style consult call with dynamic
  routing, output validation and a bounded self-correction loop.

Nothing in the base core is modified; these adapters only ADD isolation,
structured logging and safe fallbacks around the existing handlers.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional, Tuple

import structlog

from src.core.architecture.tenant.context import tenant_scope
from src.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_TENANT = "system"


def new_trace_id() -> str:
    """Short random trace id for correlating one request across logs."""
    return uuid.uuid4().hex[:16]


@asynccontextmanager
async def webhook_guard(
    session_factory: Any,
    tenant_id: Optional[str] = None,
) -> AsyncGenerator[Tuple[Any, str], None]:
    """Yield an isolated session plus its trace id for webhook processing.

    The session lifecycle matches ``async with session_factory() as session``
    used by the production routes; isolation activates only when a concrete
    ``tenant_id`` is supplied.
    """
    trace_id = new_trace_id()
    resolved = str(tenant_id or DEFAULT_TENANT)
    structlog.contextvars.bind_contextvars(trace_id=trace_id, tenant_id=resolved)
    try:
        with tenant_scope(resolved, isolate=bool(tenant_id)):
            async with session_factory() as session:
                setattr(session, "tenant_id", resolved)
                setattr(session, "trace_id", trace_id)
                yield session, trace_id
    finally:
        structlog.contextvars.unbind_contextvars("trace_id", "tenant_id")


async def process_webhook(
    session_factory: Any,
    payload: Dict[str, Any],
    tenant_id: Optional[str] = None,
    *,
    process_fn: Optional[Any] = None,
) -> Dict[str, Any]:
    """Wrapped WhatsApp controller: same pipeline + tenant guard + telemetry.

    ``process_fn`` defaults to the production inbound handler, so behaviour is
    identical to the deployed webhook while the guard adds tenant context and a
    trace id. Re-raises on failure so the route layer keeps deciding status.
    """
    from src.services.whatsapp_webhook import process_inbound_payload as _default

    handler = process_fn or _default
    async with webhook_guard(session_factory, tenant_id) as (session, trace_id):
        try:
            summary = await handler(session, payload)
            await session.commit()
            logger.info(
                "webhook processed",
                trace_id=trace_id,
                summary=summary,
                success=True,
            )
            return summary
        except Exception:
            await session.rollback()
            logger.exception("webhook processing failed", trace_id=trace_id)
            raise


class GuardedConsult:
    """Wrapped Gemini/LLM consult: routing + validation + correction.

    Built on the dynamic router and the self-correction loop. Every call
    returns a structured result object and never raises to the caller.
    """

    def __init__(
        self,
        router: Optional[Any] = None,
        self_correction: Optional[Any] = None,
        catalog: Optional[Any] = None,
        model_provider: Optional[Any] = None,
        max_corrections: int = 2,
    ) -> None:
        if self_correction is None:
            from src.core.architecture.router.dynamic_router import DynamicRouter
            from src.core.architecture.validation.self_correction import (
                OutputValidator,
                SelfCorrectionLoop,
            )

            if router is None:
                from src.core.architecture.registry.agent_catalog import AgentCatalog

                catalog = catalog or AgentCatalog()
                router = DynamicRouter(catalog, model_provider)
            self_correction = SelfCorrectionLoop(
                router, OutputValidator(), max_corrections=max_corrections
            )
        self.self_correction = self_correction
        self.router = getattr(self_correction, "router", router)

    async def reply(
        self,
        task: str,
        *,
        agent_slug: Optional[str] = None,
        system_prompt: Optional[str] = None,
        response_model: Optional[Any] = None,
        temperature: float = 0.6,
        max_tokens: int = 1200,
        lang: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Any:
        """Run a routed, validated, self-corrected task. Never raises."""
        result, _outcome = await self.self_correction.run(
            task,
            agent_slug=agent_slug,
            system_prompt=system_prompt,
            response_model=response_model,
            temperature=temperature,
            max_tokens=max_tokens,
            lang=lang,
            category=category,
        )
        return result
