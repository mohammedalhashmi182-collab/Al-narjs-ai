"""Website → Telegram deep-link attribution (``?start=lead_<uuid>``).

The early-access form returns the lead id and hands the visitor a Telegram deep
link. When the visitor presses it the chat must attach to that exact CRM record —
that is the only channel that reaches a phone-only lead — without inventing a
"replied" status for a mere ``/start`` press.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.interfaces.telegram_routes import WELCOME_TEXT, _first_contact_text
from src.models import AcquisitionLead, InboundMessage, LeadEvent
from src.services.telegram_webhook import _lead_id_from_start, process_inbound_update


async def _make_engine():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def maker():
    engine, session_maker = await _make_engine()
    yield session_maker
    await engine.dispose()


async def _seed(session: AsyncSession, name: str = "مطعم الأصالة") -> AcquisitionLead:
    lead = AcquisitionLead(
        company_name=name,
        contact_name="صاحب المطعم",
        phone="+966553078789",
        email="owner@example.com",
        source="website",
        segment="restaurant_food",
        lead_status="NEW",
        priority="MEDIUM",
        priority_score=50,
    )
    session.add(lead)
    await session.commit()
    await session.refresh(lead)
    return lead


def _start_update(chat_id: int, text: str) -> dict:
    return {
        "update_id": 900001,
        "message": {
            "message_id": 7001,
            "date": 1750000000,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": chat_id, "is_bot": False},
            "text": text,
        },
    }


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("/start lead_6f9619c0-1111-4222-8333-444444444444", "6f9619c0-1111-4222-8333-444444444444"),
        ("lead_6f9619c0-1111-4222-8333-444444444444", "6f9619c0-1111-4222-8333-444444444444"),
        ("/start support", None),
        ("/start", None),
        ("", None),
    ],
)
def test_lead_id_from_start_parses_only_deep_links(text: str, expected) -> None:
    assert _lead_id_from_start(text) == expected


async def test_deep_link_start_attaches_chat_to_the_exact_lead(maker) -> None:
    async with maker() as session:
        lead = await _seed(session)
        summary = await process_inbound_update(session, _start_update(555000111, f"/start lead_{lead.id}"))
        await session.commit()

        assert summary["messages_processed"] == 1
        assert summary["mapped_leads"] == 1

        inbound = (
            await session.execute(
                select(InboundMessage).where(InboundMessage.sender_number == "555000111")
            )
        ).scalar_one()
        assert inbound.lead_id == lead.id
        assert inbound.processing_status == "processed"

        events = (
            await session.execute(select(LeadEvent).where(LeadEvent.lead_id == lead.id))
        ).scalars().all()
        assert [e.event_type for e in events] == ["telegram_connected"]

        refreshed = (
            await session.execute(select(AcquisitionLead).where(AcquisitionLead.id == lead.id))
        ).scalar_one()
        assert refreshed.lead_status == "NEW"


async def test_next_message_in_the_chat_keeps_the_same_lead(maker) -> None:
    async with maker() as session:
        lead = await _seed(session, "مؤسسة الأثر")
        await process_inbound_update(session, _start_update(555000222, f"/start lead_{lead.id}"))
        summary = await process_inbound_update(
            session,
            _start_update(555000222, "ابغى عرض سعر"),
        )
        await session.commit()

        assert summary["unmatched"] == 0
        inbound = (
            await session.execute(
                select(InboundMessage).where(InboundMessage.sender_number == "555000222")
            )
        ).scalar_one()
        assert inbound.lead_id == lead.id


async def test_unknown_deep_link_id_is_recorded_as_unmatched(maker) -> None:
    async with maker() as session:
        summary = await process_inbound_update(
            session,
            _start_update(555000333, "/start lead_6f9619c0-1111-4222-8333-999999999999"),
        )
        await session.commit()

        assert summary["messages_processed"] == 1
        assert summary["mapped_leads"] == 0
        assert summary["unmatched"] == 1


async def test_first_contact_welcome_names_the_requested_agent(maker) -> None:
    async with maker() as session:
        lead = AcquisitionLead(
            company_name="مجموعة المدى",
            contact_name="مدير العمليات",
            phone="+966500000001",
            email="ops@example.com",
            source="website",
            segment="other",
            lead_status="NEW",
            notes="وكيل خدمة العملاء الذكي",
        )
        session.add(lead)
        await session.commit()
        await session.refresh(lead)

        update = _start_update(555000444, f"/start lead_{lead.id}")
        summary = await process_inbound_update(session, update)
        await session.commit()
        assert summary["mapped_leads"] == 1

        text = await _first_contact_text(session, update, 555000444)
        assert "مجموعة المدى" in text
        assert "وكيل خدمة العملاء الذكي" in text
        assert "بريدك الإلكتروني" in text


async def test_first_contact_welcome_falls_back_for_unknown_chats(maker) -> None:
    async with maker() as session:
        update = _start_update(555000555, "مرحبا")
        await process_inbound_update(session, update)
        await session.commit()

        assert await _first_contact_text(session, update, 555000555) == WELCOME_TEXT