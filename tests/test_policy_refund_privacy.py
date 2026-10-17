"""Owner policy decisions (2026-10-13): checkout refund consent, prompts, FAQ, legal pages."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

import httpx
import pytest
import yaml
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models import Payment
from src.services import payments as pm
from src.services import policies

@pytest.fixture(autouse=True)
def _bank_transfer_code_path(monkeypatch):
    monkeypatch.setenv("CUSTOMER_BANK_TRANSFER_ENABLED", "1")


ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "src" / "web" / "templates"


@contextmanager
def _no_gateway():
    from src.config import settings as s

    old = s.moyasar_api_secret
    object.__setattr__(s, "moyasar_api_secret", None)
    pm._credential_cache.clear()
    try:
        yield
    finally:
        object.__setattr__(s, "moyasar_api_secret", old)
        pm._credential_cache.clear()


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def anon(maker):
    from src import main

    main.app.state.session_factory = maker
    main._payment_replays.clear()
    main._payment_locks.clear()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as c:
        yield c


async def test_payment_without_consent_is_blocked(anon, maker):
    with _no_gateway():
        r = await anon.post("/api/payments", json={"package": "radd", "method": "invoice"})
    assert r.status_code == 422
    assert policies.REFUND_CONSENT_AR in r.json()["detail"]["message_ar"]
    async with maker() as s:
        assert (await s.execute(Payment.__table__.select())).first() is None


async def test_payment_false_consent_is_blocked(anon):
    with _no_gateway():
        r = await anon.post("/api/payments", json={"package": "radd", "method": "mada", "refund_consent": False})
    assert r.status_code == 422


async def test_consent_timestamp_is_stored(anon, maker):
    with _no_gateway():
        r = await anon.post("/api/payments", json={"package": "radd", "method": "invoice", "refund_consent": True})
    assert r.status_code == 200, r.text
    async with maker() as s:
        p = await s.get(Payment, UUID(r.json()["payment_id"]))
    assert p.refund_consent_at is not None
    assert p.refund_consent_version == policies.POLICY_VERSION


def test_checkout_has_mandatory_consent_checkbox():
    html = (TPL / "portal.html").read_text(encoding="utf-8")
    assert 'id="refundConsent"' in html and "required" in html.split('id="refundConsent"')[1][:80]
    assert policies.REFUND_CONSENT_AR in html
    assert "refund_consent: true" in html
    assert "consentBox.checked" in html


def test_terms_and_privacy_carry_the_policies():
    terms = (TPL / "terms.html").read_text(encoding="utf-8")
    privacy = (TPL / "privacy.html").read_text(encoding="utf-8")
    assert policies.REFUND_CONSENT_AR in terms
    assert "الخصم المكرر" in terms and "24/7" in terms
    assert "30 يوماً" in privacy and "خارج المملكة" in privacy and "ZATCA" in privacy


def test_prompts_carry_the_policies():
    from src.services import ceo_advisor

    from types import SimpleNamespace

    system, _ = ceo_advisor._llm_prompt("عندي متجر", SimpleNamespace(agents=["customer_service"]), "ar")
    assert "Refunds: none after activation" in system
    for slug in ("sales_closer", "customer_service"):
        d = yaml.safe_load((ROOT / "agents" / "base" / f"{slug}.yaml").read_text(encoding="utf-8"))
        assert "Refunds: none after activation" in d["prompts"]["default"], slug
        assert "24 hours a day, 7 days a week" in d["prompts"]["default"], slug


async def test_owner_faq_seed_is_idempotent(maker):
    from src.services.agent_tools import knowledge_base

    async with maker() as s:
        assert await policies.seed_owner_faq(s) is True
        assert await policies.seed_owner_faq(s) is False
        hits = await knowledge_base.search(s, "هل فيه استرداد بعد التفعيل؟")
    assert hits and "استرداد" in hits[0]["text"]


async def test_smart_reply_answers_policy_without_seed(maker):
    from src.services import smart_reply

    async with maker() as s:
        hits = await smart_reply._kb_hits(s, "متى أوقات الدعم عندكم؟")
    assert hits and "24/7" in smart_reply.compose_kb_answer(hits)
