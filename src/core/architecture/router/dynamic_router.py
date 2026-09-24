"""Dynamic agent router with safe exception fallbacks.

Routes a task to the best-matching agent via the centralized catalog, then
executes it against the model provider. Every routing/execution failure is
contained: the router falls back to the registered provider chain and, as a
last resort, returns a structured failure result instead of raising — so the
caller (webhook, consult route, workflow step) never crashes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.core.architecture.registry.agent_catalog import (
    AgentCatalog,
    CatalogMatch,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RouteStrategy(str, Enum):
    EXACT = "exact"
    CAPABILITY = "capability"
    FALLBACK = "fallback"


@dataclass
class RouteDecision:
    """Deterministic routing decision for one task."""

    agent_slug: str
    model_spec: str
    confidence: float
    strategy: RouteStrategy
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_slug": self.agent_slug,
            "model_spec": self.model_spec,
            "confidence": self.confidence,
            "strategy": self.strategy.value,
            "candidates": list(self.candidates),
            "reason": self.reason,
        }


@dataclass
class RouterResult:
    """Outcome of one routed execution — never raises to the caller."""

    success: bool
    content: str
    agent_slug: str
    model_used: str
    tokens_used: int
    latency_ms: int
    error: Optional[str] = None
    fallback_used: bool = False
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    structured_output: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "content": self.content,
            "agent_slug": self.agent_slug,
            "model_used": self.model_used,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "fallback_used": self.fallback_used,
            "decisions": list(self.decisions),
        }


class DynamicRouter:
    """Capability-based router wrapping the model provider safely."""

    def __init__(
        self,
        catalog: Optional[AgentCatalog] = None,
        model_provider: Optional[Any] = None,
        fallback_chain: str = "gemini",
        default_model: str = "gemini:gemini-3.6-flash",
    ) -> None:
        self.catalog: AgentCatalog = catalog or AgentCatalog()
        self.model_provider: Optional[Any] = model_provider
        self.fallback_chain: str = fallback_chain
        self.default_model: str = default_model

    def set_model_provider(self, model_provider: Any) -> None:
        self.model_provider = model_provider

    # -- Decision ------------------------------------------------------------

    def decide(
        self,
        task: str,
        agent_slug: Optional[str] = None,
        category: Optional[str] = None,
        lang: Optional[str] = None,
        include_owner_only: bool = False,
    ) -> RouteDecision:
        """Choose the agent for ``task`` (explicit slug wins)."""
        if agent_slug:
            entry = self.catalog.get(agent_slug)
            if entry is not None:
                return RouteDecision(
                    agent_slug=entry.slug,
                    model_spec=entry.default_model,
                    confidence=1.0,
                    strategy=RouteStrategy.EXACT,
                    candidates=[entry.to_dict()],
                    reason="explicit agent requested",
                )

        match: Optional[CatalogMatch] = self.catalog.best_match(
            task, lang=lang, category=category,
            include_owner_only=include_owner_only,
        )
        if match is not None:
            return RouteDecision(
                agent_slug=match.agent.slug,
                model_spec=match.agent.default_model,
                confidence=match.score,
                strategy=RouteStrategy.CAPABILITY,
                candidates=[self.catalog.get(m.agent.slug).to_dict()
                             for m in self.catalog.match(
                                 task, lang=lang, category=category, top_k=3,
                                 include_owner_only=include_owner_only,
                             ) if self.catalog.get(m.agent.slug)],
                reason="capability match",
            )

        fallback = self.catalog.fallback()
        return RouteDecision(
            agent_slug=fallback.slug,
            model_spec=fallback.default_model,
            confidence=0.0,
            strategy=RouteStrategy.FALLBACK,
            candidates=[],
            reason="capability miss: routed to fallback agent",
        )

    # -- Execution -----------------------------------------------------------

    async def execute(
        self,
        task: str,
        *,
        agent_slug: Optional[str] = None,
        system_prompt: Optional[str] = None,
        response_model: Optional[Any] = None,
        temperature: float = 0.6,
        max_tokens: int = 1500,
        lang: Optional[str] = None,
        category: Optional[str] = None,
        include_owner_only: bool = False,
    ) -> RouterResult:
        """Execute ``task`` safely; never raises to the caller."""
        decision = self.decide(
            task,
            agent_slug=agent_slug,
            category=category,
            lang=lang,
            include_owner_only=include_owner_only,
        )

        if self.model_provider is None:
            return RouterResult(
                success=False,
                content="",
                agent_slug=decision.agent_slug,
                model_used=decision.model_spec,
                tokens_used=0,
                latency_ms=0,
                error="model provider not wired",
                fallback_used=False,
                decisions=[decision.to_dict()],
            )

        from src.core.model_provider import ModelRequest

        request = ModelRequest(
            prompt=task,
            system_prompt=system_prompt or "",
            temperature=temperature,
            max_tokens=max_tokens,
            response_model=response_model,
        )

        start = time.perf_counter()
        chain_failed: List[str] = []
        try:
            try:
                response = await self.model_provider.complete(
                    decision.model_spec, request
                )
            except Exception as e:
                chain_failed.append(str(e))
                logger.warning(
                    "dynamic_router primary failed; using fallback chain",
                    agent=decision.agent_slug,
                    model=decision.model_spec,
                    error=str(e),
                )
                response = await self.model_provider.complete_with_fallback(
                    self.fallback_chain, request
                )

            latency_ms = int((time.perf_counter() - start) * 1000)
            structured = None
            if response.structured_output is not None:
                structured = response.structured_output.model_dump() \
                    if hasattr(response.structured_output, "model_dump") \
                    else response.structured_output

            return RouterResult(
                success=True,
                content=response.content,
                agent_slug=decision.agent_slug,
                model_used=response.model or decision.model_spec,
                tokens_used=response.tokens_used,
                latency_ms=latency_ms,
                error=None,
                fallback_used=bool(chain_failed),
                decisions=[decision.to_dict()],
                structured_output=structured,
            )
        except Exception as e:
            logger.exception(
                "dynamic_router execution failed",
                agent=decision.agent_slug,
                error=str(e),
            )
            return RouterResult(
                success=False,
                content="",
                agent_slug=decision.agent_slug,
                model_used=decision.model_spec,
                tokens_used=0,
                latency_ms=int((time.perf_counter() - start) * 1000),
                error=str(e),
                fallback_used=True,
                decisions=[decision.to_dict()],
            )
