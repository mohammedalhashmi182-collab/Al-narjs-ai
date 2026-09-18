"""Revenue engine, payment lock and WhatsApp sender behavior (in-memory DB)."""

from __future__ import annotations

import math
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.owner_auth import make_session_token
from src.db.session import Base
from src.services.revenue_tiers import (
    PRICE_SAR,
    TIER_A_MIN,
    data_flags,
    provenance,
    reference_id,
    score_lead,
)
from src.services.revenue_radar import _interleave, build_wave
from src.services.whatsapp_sender import is_enabled, send_status


# ---------------------------------------------------------------------------
# Fixtures (mirror test_company_os for an in-memory DB + real app)
# ---------------------------------------------------------------------------

async def _make_engine():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def maker():
    engine, maker = await _make_engine()
    yield maker
    await engine.dispose()


@pytest.fixture
async def api(maker):
    from src.main import app

    app.state.session_factory = maker
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"narjis_owner": make_session_token()},
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeLead:
    """Minimal lead-like object for deterministic scoring tests."""

    def __init__(
        self,
        *,
        lead_status: str = "NEW",
        quotation_without_purchase: bool = False,
        historical_customer: bool = False,
        last_activity: str | None = None,
        invoice_count: int = 0,
        phone: str | None = None,
        email: str | None = None,
        priority: str | None = "MEDIUM",
        segment: str = "restaurant_food",
        suggested_package: str = "social",
        company_name: str = "Test Co.",
        id: str | None = None,
        source_sheet: str | None = "Sheet2",
        source_customer_code: str | None = None,
        dedup_key: str | None = None,
        phone_raw: str | None = None,
    ):
        for k, v in locals().items():
            if k != "self":
                setattr(self, k, v)
        if self.id is None:
            self.id = str(uuid4())


# ---------------------------------------------------------------------------
# Tier scoring facts
# ---------------------------------------------------------------------------

class TestTierScoring:
    def test_highly_reachable_quotation_is_A(self):
        lead = _FakeLead(
            quotation_without_purchase=True,
            historical_customer=True,
            last_activity="2025-01-01",
            invoice_count=5,
            phone="0555555555",
            email="test@co.com",
            priority="HIGH",
            segment="restaurant_food",
            suggested_package="social",
        )
        result = score_lead(lead)
        assert result.tier == "A"
        assert result.score >= TIER_A_MIN
        assert any("عرض سعر سابق" in r for r in result.reasons)
        assert any("عميل تاريخي" in r for r in result.reasons)
        assert any("واتساب" in r or "هاتف" in r for r in result.reasons)

    def test_cold_no_channel_is_D(self):
        lead = _FakeLead(priority="LOW", phone=None, email=None)
        result = score_lead(lead)
        assert result.tier == "D"
        flags = data_flags(lead)
        assert "no_reachable_channel" in flags

    def test_do_not_contact_is_D(self):
        lead = _FakeLead(lead_status="DO_NOT_CONTACT")
        result = score_lead(lead)
        assert result.tier == "D"

    def test_price_sar_matches_catalog_halalas(self):
        from src.services import catalog

        for pkg, meta in catalog.PACKAGES.items():
            assert meta["amount"] // 100 == PRICE_SAR[pkg], pkg


# ---------------------------------------------------------------------------
# Reference ID / provenance
# ---------------------------------------------------------------------------

class TestReferenceId:
    def test_uses_sheet_and_code(self):
        lead = _FakeLead(source_sheet="2025", source_customer_code="C123")
        assert reference_id(lead) == "2025:C123"

    def test_falls_back_to_dedup_key(self):
        lead = _FakeLead(dedup_key="dk_123")
        assert reference_id(lead) == "dedup:dk_123"

    def test_provenance_never_contains_machine_path(self):
        lead = _FakeLead(source_sheet="2024", source_customer_code="ABC", dedup_key="abc-123")
        p = provenance(lead)
        assert "C:" not in str(p.values())
        assert p["duplicate_protected"] is True
        assert p["source"] == "owner_workbook"


# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------

class TestFlags:
    def test_no_reachable_channel(self):
        lead = _FakeLead(phone=None, email=None)
        assert "no_reachable_channel" in data_flags(lead)

    def test_unparsed_phone_flag(self):
        lead = _FakeLead(phone_raw="06552978753", phone=None)
        assert "unparsed_phone" in data_flags(lead)


# ---------------------------------------------------------------------------
# Interleave + wave ordering
# ---------------------------------------------------------------------------

class TestInterleave:
    def test_interleaves_by_length_proportionally(self):
        q = [1, 2, 3]
        h = [10, 20]
        r = [100]
        result = _interleave([q, h, r])
        assert result[:3] == [1, 10, 100]
        assert result[3] == 2
        assert result[4] == 20
        assert result[5] == 3


# ---------------------------------------------------------------------------
# WhatsApp sender safety
# ---------------------------------------------------------------------------

class TestWhatsApp:
    def test_sender_disabled_without_credentials(self):
        from src.config import settings as _settings

        was_token = _settings.whatsapp_token
        was_phone = _settings.whatsapp_phone_number_id
        try:
            # Force both credentials off for the assertion.
            object.__setattr__(_settings, "whatsapp_token", None)
            object.__setattr__(_settings, "whatsapp_phone_number_id", None)
            assert is_enabled() is False
            status = send_status()
            assert status["enabled"] is False
            assert "wa.me" in status["fallback"]
        finally:
            object.__setattr__(_settings, "whatsapp_token", was_token)
            object.__setattr__(_settings, "whatsapp_phone_number_id", was_phone)


# ---------------------------------------------------------------------------
# Revenue radar + payments confirm (real app, in-memory DB)
# ---------------------------------------------------------------------------

async def test_wave_sizing_reports_real_metrics(api, maker):
    from src.models import AcquisitionLead

    async with maker() as s:
        s.add(AcquisitionLead(
            id=uuid4(),
            company_name="RadarCo",
            segment="retail",
            suggested_package="social",
            phone="0555555555",
            priority="HIGH",
            quotation_without_purchase=True,
            lead_status="NEW",
        ))
        await s.commit()

    wave1 = await build_wave(maker())
    metrics1 = wave1["metrics"]
    assert metrics1["gap_sar"] >= 0
    assert metrics1["potential_sar"] >= 1500
    assert wave1["wave_size"] >= 1


async def test_radar_payloads_have_evidence_and_no_secrets(api, maker):
    from src.models import AcquisitionLead

    async with maker() as s:
        s.add(AcquisitionLead(
            id=uuid4(),
            company_name="EvidenceCo",
            segment="services",
            suggested_package="growth",
            phone="0555123123",
            priority="HIGH",
            quotation_without_purchase=True,
            historical_customer=True,
            lead_status="NEW",
        ))
        await s.commit()

    wave = await build_wave(maker())
    payload = wave["wave"][0]
    assert payload["tier"] in ("A", "B")
    assert payload["reference_id"]
    assert payload["price_sar"] == 800
    assert payload["insight"]
    assert payload["message_draft"]
    assert "C:" not in str(payload)
    assert payload["provenance"]["source"] == "owner_workbook"


async def test_confirm_received_owner_gated(maker):
    from src.main import app

    app.state.session_factory = maker
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/payments/00000000-0000-0000-0000-000000000000/confirm-received", json={}
        )
        assert resp.status_code in (401, 403, 404)


async def test_confirm_received_flips_lead_to_won(api, maker):
    from src.models import AcquisitionLead, Decision, LeadEvent, Payment
    from src.services import payments as pm

    lead_id = uuid4()
    async with maker() as s:
        s.add(AcquisitionLead(
            id=lead_id,
            company_name="ConfirmCo",
            segment="services",
            suggested_package="content",
            phone="0566666666",
            priority="MEDIUM",
            lead_status="NEW",
        ))
        await s.commit()
        payment = await pm.create_payment(s, "content", lead_id=lead_id)
        payment_id = payment.id

    resp = await api.post(
        f"/api/payments/{payment_id}/confirm-received",
        json={"confirmed_by": "owner", "note": "transfer received"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "paid"

    async with maker() as s:
        payment = (await s.execute(select(Payment).where(Payment.id == payment_id))).scalar_one()
        lead = (await s.execute(select(AcquisitionLead).where(AcquisitionLead.id == lead_id))).scalar_one()
        dec_count = len((await s.execute(
            select(Decision).where(Decision.reason == f"payment_ref:{payment_id}")
        )).scalars().all())
        events = (await s.execute(
            select(LeadEvent).where(LeadEvent.lead_id == lead_id).where(LeadEvent.event_type == "status_change")
        )).scalars().all()

    assert payment.status == "paid"
    assert lead.lead_status == "WON"
    assert lead.outreach_status == "WON"
    assert dec_count == 1
    assert len(events) >= 1
    assert events[0].status_after == "WON"


async def test_confirm_received_deduplicates(api, maker):
    from src.models import AcquisitionLead, Decision, Payment
    from src.services import payments as pm

    lead_id = uuid4()
    async with maker() as s:
        s.add(AcquisitionLead(
            id=lead_id,
            company_name="DedupCo",
            segment="retail",
            suggested_package="growth",
            lead_status="NEW",
        ))
        await s.commit()
        payment = await pm.create_payment(s, "growth", lead_id=lead_id)
        payment_id = payment.id

    r1 = await api.post(
        f"/api/payments/{payment_id}/confirm-received",
        json={"note": "first"},
    )
    r2 = await api.post(
        f"/api/payments/{payment_id}/confirm-received",
        json={"note": "second"},
    )
    assert r1.status_code == 200
    assert r2.json().get("already_paid") is True or r2.json().get("outcome", {}).get("deduplicated") is True

    async with maker() as s:
        decisions = (await s.execute(
            select(Decision).where(Decision.reason == f"payment_ref:{payment_id}")
        )).scalars().all()
    assert len(decisions) == 1


async def test_score_lead_reads_plain_dict():
    lead = {
        "company_name": "DictCo",
        "phone": "0551234567",
        "email": "dict@example.com",
        "priority": "HIGH",
        "quotation_without_purchase": True,
        "historical_customer": True,
        "last_activity": "2025-01-01",
        "invoice_count": 5,
        "segment": "restaurant_food",
        "suggested_package": "social",
        "lead_status": "NEW",
    }
    result = score_lead(lead)
    assert result.tier == "A"
    assert result.score >= TIER_A_MIN
    assert "رقم واتساب متاح للتواصل الفوري" in result.reasons
    assert "no_reachable_channel" not in data_flags(lead)
    assert reference_id(lead) == "row:None"


async def test_proposal_page_renders(api, maker):
    from src.models import AcquisitionLead

    lead_id = uuid4()
    async with maker() as s:
        s.add(AcquisitionLead(
            id=lead_id,
            company_name="ProposalCo",
            segment="services",
            suggested_package="content",
            phone="0551234567",
            priority="MEDIUM",
            lead_status="NEW",
        ))
        await s.commit()

    resp = await api.get(f"/acquisition/leads/{lead_id}/proposal")
    assert resp.status_code == 200
    assert "ProposalCo" in resp.text
    assert "content" in resp.text