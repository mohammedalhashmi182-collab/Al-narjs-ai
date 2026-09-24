"""Tests for the architectural middleware package.

Covers: ContextVar tenant isolation, thread-safe session filtration, the
centralized agent catalog, dynamic routing with safe fallbacks, the bounded
self-correction loop, and the wrapped WhatsApp controller (parity with the
production inbound pipeline).
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import Column, Integer, String, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import StaticPool
from src.core.architecture.registry.agent_catalog import AgentCatalog
from src.core.architecture.router.dynamic_router import DynamicRouter
from src.core.architecture.tenant.context import (
    current_tenant_id,
    tenant_isolation_enabled,
    tenant_scope,
)
from src.core.architecture.tenant.scope import tenant_filter
from src.core.architecture.validation.self_correction import (
    OutputValidator,
    SelfCorrectionLoop,
)
from src.core.model_provider import ModelResponse
from src.services.lead_normalize import normalize_phone

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = REPO_ROOT / "agents" / "base"


# ---------------------------------------------------------------------------
# Tenant context
# ---------------------------------------------------------------------------

def test_tenant_context_default_and_scope():
    assert current_tenant_id() is None
    assert not tenant_isolation_enabled()

    with tenant_scope("acme", isolate=True) as tid:
        assert tid == "acme"
        assert current_tenant_id() == "acme"
        assert tenant_isolation_enabled()

    assert current_tenant_id() is None
    assert not tenant_isolation_enabled()


def test_tenant_scope_default_resolves_to_system():
    with tenant_scope(None) as tid:
        assert tid == "system"
        assert not tenant_isolation_enabled()


def test_tenant_filter_passthrough_and_apply():
    _Base = declarative_base()

    class WithTenant(_Base):
        __tablename__ = "with_tenant"
        id = Column(Integer, primary_key=True)
        tenant_id = Column(String(50))

    class NoTenant(_Base):
        __tablename__ = "no_tenant"
        id = Column(Integer, primary_key=True)

    q_with = select(WithTenant)
    q_no = select(NoTenant)

    with tenant_scope("acme", isolate=False):
        assert tenant_filter(q_with, WithTenant) is q_with

    with tenant_scope("acme", isolate=True):
        filtered = tenant_filter(q_with, WithTenant)
        assert "tenant_id" in str(filtered.compile())
        # A model without tenant_id must pass through untouched.
        assert tenant_filter(q_no, NoTenant) is q_no


# ---------------------------------------------------------------------------
# Agent catalog
# ---------------------------------------------------------------------------

def test_catalog_loads_yaml_agents():
    catalog = AgentCatalog(AGENT_DIR)
    assert catalog.load_dir() > 0
    assert catalog.count() == catalog.load_dir()

    sales = catalog.get("sales_closer")
    assert sales is not None
    assert sales.code == "GR-06"
    assert sales.modes == ["objection_handling", "offer_build", "cart_recovery"]
    assert sales.owner_only is False
    assert sales.default_model.startswith("gemini:")


def test_catalog_best_match_and_fallback():
    catalog = AgentCatalog(AGENT_DIR)
    catalog.load_dir()

    fallback = catalog.fallback()
    assert fallback.slug in ("customer_service", "social_media", "marketing_agent")

    match = catalog.best_match("handle sales objections and close the deal")
    assert match is not None
    assert match.score > 0.0

    include_owner = catalog.best_match(
        "operating report for the owner", include_owner_only=True
    )
    assert include_owner is None or include_owner.agent is not None


# ---------------------------------------------------------------------------
# Dynamic router
# ---------------------------------------------------------------------------

class _FakeProvider:
    def __init__(self, primary_error: bool = True):
        self.primary_error = primary_error
        self.calls = []

    async def complete(self, spec, request):
        self.calls.append(("complete", str(spec)))
        if self.primary_error:
            raise RuntimeError("primary model exploded")
        return ModelResponse(
            content="primary-ok", model=str(spec), tokens_used=7, latency_ms=5
        )

    async def complete_with_fallback(self, chain, request):
        self.calls.append(("fallback", chain))
        return ModelResponse(
            content="fallback-ok", model="gemini:x", tokens_used=9, latency_ms=6
        )


@pytest.mark.asyncio
async def test_router_exact_decision_and_fallback_execution():
    catalog = AgentCatalog(AGENT_DIR)
    catalog.load_dir()
    provider = _FakeProvider(primary_error=True)
    router = DynamicRouter(catalog, provider)

    decision = router.decide("anything", agent_slug="sales_closer")
    assert decision.strategy.value == "exact"
    assert decision.agent_slug == "sales_closer"
    assert decision.confidence == 1.0

    result = await router.execute(decision.agent_slug, agent_slug="sales_closer")
    assert result.success is True
    assert result.fallback_used is True
    assert result.content == "fallback-ok"
    assert ("complete", "gemini:gemini-3.6-flash") in provider.calls
    assert ("fallback", "gemini") in provider.calls


@pytest.mark.asyncio
async def test_router_graceful_failure_without_provider():
    catalog = AgentCatalog(AGENT_DIR)
    catalog.load_dir()
    router = DynamicRouter(catalog, None)

    result = await router.execute("local task", agent_slug="sales_closer")
    assert result.success is False
    assert "model provider not wired" in (result.error or "")


@pytest.mark.asyncio
async def test_router_primary_success_no_fallback():
    catalog = AgentCatalog(AGENT_DIR)
    catalog.load_dir()
    provider = _FakeProvider(primary_error=False)
    router = DynamicRouter(catalog, provider)

    result = await router.execute("simple", agent_slug="sales_closer")
    assert result.success is True
    assert result.fallback_used is False
    assert result.content == "primary-ok"


# ---------------------------------------------------------------------------
# Self-correction loop
# ---------------------------------------------------------------------------

class _RouterStub:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.tasks = []

    async def execute(self, task, **kwargs):
        self.tasks.append(task)
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_self_correction_fixes_invalid_output():
    from pydantic import BaseModel

    class Out(BaseModel):
        ok: bool

    stub = _RouterStub(
        ModelResponse(content="not-json", model="m", tokens_used=1, latency_ms=1),
        ModelResponse(content='{"ok": true}', model="m", tokens_used=2, latency_ms=1),
    )
    loop = SelfCorrectionLoop(stub, OutputValidator(), max_corrections=2)

    result, outcome = await loop.run("answer", response_model=Out)

    assert result.content == '{"ok": true}'
    assert outcome.valid is True
    assert outcome.parsed.ok is True
    assert loop.stats().total_attempts == 2
    assert loop.stats().corrections == 1
    assert loop.stats().last_corrected is True
    # The second attempt received the previous errors as feedback.
    assert "rejected" in stub.tasks[1]


@pytest.mark.asyncio
async def test_self_correction_bounded():
    from pydantic import BaseModel

    class Out(BaseModel):
        ok: bool

    stub = _RouterStub(
        ModelResponse(content="bad", model="m", tokens_used=1, latency_ms=1),
        ModelResponse(content="also-bad", model="m", tokens_used=1, latency_ms=1),
        ModelResponse(content="again", model="m", tokens_used=1, latency_ms=1),
    )
    loop = SelfCorrectionLoop(stub, OutputValidator(), max_corrections=2)

    result, outcome = await loop.run("answer", response_model=Out)

    assert loop.stats().total_attempts == 3
    assert outcome.valid is False
    assert result is not None


# ---------------------------------------------------------------------------
# Wrapped WhatsApp controller (parity with the production pipeline)
# ---------------------------------------------------------------------------

async def _make_engine():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    from src.db.session import Base as AppBase

    async with engine.begin() as conn:
        await conn.run_sync(AppBase.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _insert_lead(maker, *, company="AcmeCo", phone="0555112233", status="NEW"):
    from src.models import AcquisitionLead

    async with maker() as s:
        lead = AcquisitionLead(
            id=uuid4(),
            company_name=company,
            segment="services",
            suggested_package="social",
            phone=normalize_phone(phone),
            phone_raw=phone,
            lead_status=status,
            priority="MEDIUM",
        )
        s.add(lead)
        await s.commit()
        await s.refresh(lead)
        return lead


def _inbound_payload(msg_id: str, text: str, sender: str = "966555112233") -> dict:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": sender,
                                    "id": msg_id,
                                    "timestamp": "1730000000",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                            "contacts": [{"wa_id": sender}],
                        }
                    }
                ]
            }
        ]
    }


@pytest.mark.asyncio
async def test_wrapped_webhook_parity_and_dedup():
    from src.core.architecture.controller import process_webhook

    engine, maker = await _make_engine()
    try:
        lead = await _insert_lead(maker, phone="0555112233")
        payload = _inbound_payload("msg-arch-1", "بكم السعر؟", sender="966555112233")

        summary = await process_webhook(maker, payload, tenant_id="acme")
        assert summary["messages_processed"] == 1
        assert summary["mapped_leads"] == 1
        assert summary["duplicates_skipped"] == 0

        # Tenant id and trace id were stamped on the session inside the guard.
        from src.core.architecture.tenant.context import current_tenant_id

        assert current_tenant_id() is None  # restored after the guard

        summary2 = await process_webhook(maker, payload, tenant_id="acme")
        assert summary2["messages_processed"] == 0
        assert summary2["duplicates_skipped"] == 1

        from src.models import AcquisitionLead

        async with maker() as s:
            fresh = (
                await s.execute(select(AcquisitionLead).where(AcquisitionLead.id == lead.id))
            ).scalar_one()
            assert fresh.lead_status == "INTERESTED"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_wrapped_webhook_rolls_back_on_failure():
    from src.core.architecture.controller import process_webhook

    engine, maker = await _make_engine()
    try:

        async def _boom(session, payload):
            raise RuntimeError("handler exploded")

        with pytest.raises(RuntimeError):
            await process_webhook(maker, {}, process_fn=_boom)
    finally:
        await engine.dispose()
