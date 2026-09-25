"""360dialog gateway tests (in-memory DB).

Covers: credential gating for the D360 route, gateway selection between
360dialog and Meta Cloud API, ack-based send lifecycle, secret-free status,
and secret leakage prevention. Governance/opt-out lives in
``test_whatsapp_integration.py`` and is shared by both gateways.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from src.db.session import Base
from src.models import AcquisitionLead, OutboundMessage
from src.services import whatsapp_sender as ws
from src.services.lead_normalize import normalize_phone


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


DIALOG_KEY = "D360-TEST-KEY-DO-NOT-LOG"
PHONE = "966555555555"


@contextmanager
def _dialog(key=DIALOG_KEY, base="https://waba.360dialog.io", token=None, phone_id=None):
    """Point the sender at 360dialog, restore afterwards."""
    from src.config import settings as s

    names = ("dialog_api_key", "dialog_base_url", "whatsapp_token", "whatsapp_phone_number_id")
    old = [getattr(s, n) for n in names]
    object.__setattr__(s, "dialog_api_key", key)
    object.__setattr__(s, "dialog_base_url", base)
    object.__setattr__(s, "whatsapp_token", token)
    object.__setattr__(s, "whatsapp_phone_number_id", phone_id)
    try:
        yield
    finally:
        for n, v in zip(names, old, strict=False):
            object.__setattr__(s, n, v)


@contextmanager
def _meta_only(token="EAAG-TOKEN", phone_id="1111222233334444", key=None):
    """Point the sender at Meta Cloud API only."""
    from src.config import settings as s

    names = ("dialog_api_key", "whatsapp_token", "whatsapp_phone_number_id")
    old = [getattr(s, n) for n in names]
    object.__setattr__(s, "dialog_api_key", key)
    object.__setattr__(s, "whatsapp_token", token)
    object.__setattr__(s, "whatsapp_phone_number_id", phone_id)
    try:
        yield
    finally:
        for n, v in zip(names, old, strict=False):
            object.__setattr__(s, n, v)


async def _insert_lead(maker, *, company="DialogCo", phone="0555555555") -> AcquisitionLead:
    async with maker() as s:
        lead = AcquisitionLead(
            id=uuid4(),
            company_name=company,
            segment="services",
            suggested_package="social",
            phone=normalize_phone(phone),
            phone_raw=phone,
            lead_status="NEW",
            priority="MEDIUM",
        )
        s.add(lead)
        await s.commit()
        await s.refresh(lead)
        return lead


# ---------------------------------------------------------------------------
# 1) Credential gating + gateway selection
# ---------------------------------------------------------------------------

class TestGatewaySelection:
    def test_dialog_key_enables_sender_without_meta_creds(self):
        with _dialog():
            assert ws.is_enabled() is True
            status = ws.send_status()
            assert status["enabled"] is True
            assert status["connected"] is True
            assert status["gateway"] == "dialog360"
            assert status["dialog_configured"] is True
            assert DIALOG_KEY not in json.dumps(status)

    def test_no_creds_disables_sender(self):
        with _dialog(key=None, token=None, phone_id=None):
            assert ws.is_enabled() is False
            status = ws.send_status()
            assert status["enabled"] is False
            assert status["connected"] is False
            assert status["gateway"] == "meta_cloud"
            assert status["disabled_reason"]

    def test_meta_creds_alone_select_meta_gateway(self):
        with _dialog(key=None, token="EAAG-TOKEN", phone_id="1111222233334444"):
            assert ws.is_enabled() is True
            assert ws.send_status()["gateway"] == "meta_cloud"
            assert ws.dialog_enabled() is False

    def test_endpoint_url_and_header_for_dialog(self):
        with _dialog():
            url, headers = ws._gateway_endpoint()
            assert url == "https://waba.360dialog.io/v1/messages"
            assert headers["D360-API-KEY"] == DIALOG_KEY
            assert "Authorization" not in headers
            assert DIALOG_KEY not in json.dumps({"url": url})

    def test_endpoint_url_and_header_for_meta(self):
        with _meta_only():
            url, headers = ws._gateway_endpoint()
            assert url == f"{ws.API_URL}/1111222233334444/messages"
            assert headers["Authorization"].startswith("Bearer ")
            assert "D360-API-KEY" not in headers

    def test_custom_base_url_is_honoured(self):
        with _dialog(base="https://eu.360dialog.io"):
            url, _ = ws._gateway_endpoint()
            assert url.startswith("https://eu.360dialog.io/")


# ---------------------------------------------------------------------------
# 2) Send lifecycle through the 360dialog route
# ---------------------------------------------------------------------------

class TestDialogSendLifecycle:
    async def test_send_success_records_dialog360_provider(self, maker):
        with _dialog():
            lead = await _insert_lead(maker)
            original = ws._post_message
            ws._post_message = _ok_post  # type: ignore[assignment]
            async with maker() as s:
                result = await ws.send_now(s, lead_id=lead.id, phone=lead.phone, text="مرحباً 👋")
                assert result["status"] == "sent"
                assert result["acknowledged"] is True
                assert result["provider"] == "dialog360"
                record = (await s.execute(
                    select(OutboundMessage).order_by(OutboundMessage.created_at.desc()).limit(1)
                )).scalar_one()
                assert record.status == "sent"
                assert record.provider == "dialog360"
                assert record.sent_at is not None
            ws._post_message = original  # type: ignore[assignment]

    async def test_send_failure_never_marks_sent(self, maker):
        with _dialog():
            lead = await _insert_lead(maker)
            original = ws._post_message
            ws._post_message = _fail_post  # type: ignore[assignment]
            async with maker() as s:
                result = await ws.send_now(s, lead_id=lead.id, phone=lead.phone, text="مرحباً")
                assert result["status"] == "failed"
                assert result["acknowledged"] is False
                assert result["provider"] == "dialog360"
                record = (await s.execute(
                    select(OutboundMessage).order_by(OutboundMessage.created_at.desc()).limit(1)
                )).scalar_one()
                assert record.status == "failed"
                assert record.sent_at is None
                assert record.retry_count == 1
            ws._post_message = original  # type: ignore[assignment]

    async def test_dialog_opt_out_lead_is_blocked(self, maker):
        with _dialog():
            lead = await _insert_lead(maker)
            async with maker() as s:
                lead = (await s.execute(
                    select(AcquisitionLead).where(AcquisitionLead.id == lead.id)
                )).scalar_one()
                lead.opt_out = True
                await s.commit()

            original = ws._post_message
            ws._post_message = _boom  # type: ignore[assignment]
            async with maker() as s:
                result = await ws.send_now(s, lead_id=lead.id, phone=lead.phone, text="مرحباً")
                assert result["status"] == "blocked"
                assert result["reason"] == "opted_out"
            ws._post_message = original  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# 3) Secret leakage prevention
# ---------------------------------------------------------------------------

class TestDialogSecrets:
    async def test_status_and_records_never_leak_the_api_key(self, maker):
        with _dialog():
            lead = await _insert_lead(maker)
            original = ws._post_message
            ws._post_message = _ok_post  # type: ignore[assignment]
            async with maker() as s:
                await ws.send_now(s, lead_id=lead.id, phone=lead.phone, text="مرحباً")
                await s.commit()
                summary = await ws.conversation_summary(s)
                dumped = json.dumps(summary)
                assert DIALOG_KEY not in dumped
                record = (await s.execute(
                    select(OutboundMessage).order_by(OutboundMessage.created_at.desc()).limit(1)
                )).scalar_one()
                assert DIALOG_KEY not in json.dumps(record.to_dict())
            ws._post_message = original  # type: ignore[assignment]

    def test_gateway_endpoint_headers_are_the_only_carrier(self):
        with _dialog():
            _, headers = ws._gateway_endpoint()
            assert set(headers) <= {"D360-API-KEY", "Content-Type"}


# ---------------------------------------------------------------------------
# Stub posts (override the real HTTP seam)
# ---------------------------------------------------------------------------

async def _ok_post(record) -> dict:
    return {"ok": True, "status_code": 200, "provider_message_id": "d360.OUT1", "gateway": "dialog360"}


async def _fail_post(record) -> dict:
    return {
        "ok": False,
        "status_code": 429,
        "error": "Rate limit",
        "error_code": "130429",
        "gateway": "dialog360",
    }


async def _boom(*args, **kwargs):
    raise AssertionError("blocked lead must never be sent")
