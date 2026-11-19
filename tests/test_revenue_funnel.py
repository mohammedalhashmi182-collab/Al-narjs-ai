"""Revenue funnel: identity, message proof, Gmail ingest, dispatch, KPIs, E2E.

No network, no production data, no real payment and no outbound send.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.services.agent_dispatch import SPECIALTY, choose_agent
from src.services.funnel_messages import ProofError, is_actually_sent, legacy_api_ack_state, resolve_state
from src.services.funnel_metrics import explain_legacy_outbound
from src.services.funnel_replies import classify_reply
from src.services.gmail_reconcile import LeastPrivilegeError, MailSnapshot, ReconcileDisabled, assert_least_privilege, fetch_headers, refuse_reason


def test_reply_classes_and_opt_out_wins():
    assert classify_reply("أبغى العرض لو سمحت") == "interested"
    assert classify_reply("ليس الآن، بعد العيد") == "not_now"
    assert classify_reply("رجاءً إلغاء الرسائل") == "opt_out"
    assert classify_reply("مهتم ولكن أوقفوا الرسائل") == "opt_out"
    assert classify_reply("شكراً") == "unknown"
    assert classify_reply("") == "unknown"


def test_api_accept_is_not_a_send_or_a_delivery():
    assert resolve_state(requested="sent", proof_kind="api_accept", proof_ref="api-1") == "accepted"
    assert resolve_state(requested="delivered", proof_kind="api_accept", proof_ref="api-1") == "accepted"
    with pytest.raises(ProofError):
        resolve_state(requested="queued", proof_kind="mailbox_message_id", proof_ref="<id@mail>")
    assert resolve_state(requested="draft", proof_kind="none", proof_ref=None) == "draft"
    assert resolve_state(requested="queued", proof_kind="none", proof_ref=None) == "queued"
    sent = resolve_state(requested="sent", proof_kind="mailbox_message_id", proof_ref="<a@b>")
    assert sent == "sent"
    assert is_actually_sent("queued", None) is False
    assert is_actually_sent("accepted", None) is False
    assert is_actually_sent("sent", "<a@b>") is True
    with pytest.raises(ProofError):
        resolve_state(requested="delivered", proof_kind="delivery_receipt", proof_ref="dsn-1", prior_was_sent=False)


def test_legacy_ack_is_not_counted_as_sent():
    assert legacy_api_ack_state("sent") == "accepted"
    assert legacy_api_ack_state("queued") == "queued"
    assert legacy_api_ack_state("draft") == "draft"
    assert explain_legacy_outbound("sent")["actually_sent"] is False
    assert explain_legacy_outbound("sent")["delivered"] is False
    assert explain_legacy_outbound("queued")["counts_as_sent"] is False


def test_gmail_scope_is_readonly_only():
    assert_least_privilege(["https://www.googleapis.com/auth/gmail.readonly"])
    with pytest.raises(LeastPrivilegeError):
        assert_least_privilege([
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
        ])
    with pytest.raises(LeastPrivilegeError):
        assert_least_privilege(["https://www.googleapis.com/auth/gmail.modify"])
    with pytest.raises(ReconcileDisabled):
        fetch_headers()
    assert refuse_reason("production", ["--fixture", "x.json"]) == "refusing: production"
    assert "does not contact Gmail" in refuse_reason("test", [])


def test_dispatch_uses_specialty_and_capacity_not_all_agents():
    from src.services import catalog

    assert len(catalog.EMPLOYEES) >= 39
    for kind, names in SPECIALTY.items():
        assert len(names) < 10
        picked = choose_agent(kind, {})
        assert picked == names[0]
        assert picked in names
    loaded = {"sales_closer": 4, "lead_acquisition": 0, "customer_manager": 2}
    assert choose_agent("sales", loaded) == "lead_acquisition"
    assert "content_writer" not in SPECIALTY["sales"]
    assert choose_agent("customer_service", {"customer_service": 3}) == "customer_manager"


async def _engine():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def test_identity_dedupes_on_either_field_and_does_not_merge_two_people():
    from src.models import AcquisitionLead
    from src.models.funnel import FunnelEvent, LeadAlias
    from src.services.funnel_identity import bind_legacy_lead, resolve_lead

    engine, maker = await _engine()
    async with maker() as session:
        first = await resolve_lead(session, email="a@example.com", name="أ", source="website")
        second = await resolve_lead(session, phone="0551112223", name="ب", source="website")
        await session.commit()
        conflict = await resolve_lead(
            session,
            email="a@example.com",
            phone="0551112223",
            name="خلط",
            source="website",
        )
        await session.commit()
        assert conflict["conflict"] is True
        assert conflict["lead"].id == first["lead"].id
        phone_alias = (
            await session.execute(select(LeadAlias).where(LeadAlias.external_key == "+966551112223"))
        ).scalar_one()
        assert phone_alias.lead_id == second["lead"].id
        again = await resolve_lead(session, phone="0551112223", source="consult_assistant")
        assert again["created"] is False
        assert again["lead"].id == second["lead"].id
        legacy = await bind_legacy_lead(session, "legacy-1", email="a@example.com")
        legacy_again = await bind_legacy_lead(session, "legacy-1", email="a@example.com")
        await session.commit()
        assert legacy["lead"].id == legacy_again["lead"].id == first["lead"].id
        events = (await session.execute(select(func.count()).select_from(FunnelEvent))).scalar_one()
        assert events >= 1
        people = (await session.execute(select(func.count()).select_from(AcquisitionLead))).scalar_one()
        assert people == 2
    await engine.dispose()


async def test_messages_replies_and_gmail_snapshot_are_idempotent(caplog):
    from src.models import AcquisitionLead
    from src.models.funnel import FunnelMessage, FunnelReply
    from src.services.funnel_callback import open_callback
    from src.services.funnel_identity import resolve_lead
    from src.services.funnel_metrics import daily_kpis
    from src.services.funnel_record import ConsentBlocked, approve_outreach, record_delivery, record_message, record_reply
    from src.services.gmail_reconcile import ingest_snapshot

    engine, maker = await _engine()
    email = "buyer@example.com"
    async with maker() as session:
        resolved = await resolve_lead(session, email=email, name="مشتري", source="website")
        lead = resolved["lead"]
        await open_callback(session, lead, source="website", consent_marketing=False)
        queued = await record_message(
            session, lead_id=lead.id, channel="email", direction="outbound",
            requested="queued", proof_kind="none", enforce_consent=True, purpose="inquiry",
        )
        assert queued["actually_sent"] is False
        accepted = await record_message(
            session, lead_id=lead.id, channel="email", direction="outbound",
            requested="sent", proof_kind="api_accept", proof_ref="api-only-1",
            enforce_consent=True, purpose="inquiry",
        )
        assert accepted["state"] == "accepted"
        assert accepted["actually_sent"] is False
        with pytest.raises(ProofError):
            await record_delivery(session, sent_message_id="api-only-1", receipt_id="dsn-x")
        with pytest.raises(ConsentBlocked):
            await approve_outreach(session, lead_id=lead.id, message_id="<m@mail>", purpose="marketing")
        sent = await approve_outreach(session, lead_id=lead.id, message_id="<m@mail>", purpose="inquiry")
        assert sent["actually_sent"] is True
        assert sent["delivered"] is False
        again = await approve_outreach(session, lead_id=lead.id, message_id="<m@mail>", purpose="inquiry")
        assert again["deduplicated"] is True
        delivered = await record_delivery(session, sent_message_id="<m@mail>", receipt_id="dsn-1")
        assert delivered["delivered"] is True
        reply = await record_reply(
            session, evidence_ref="<reply@mail>", text="أبغى العرض هذا الأسبوع",
            in_reply_to="<m@mail>", lead_id=lead.id,
        )
        assert reply["classification"] == "interested"
        await session.commit()
        lead_id = lead.id

    async with maker() as session:
        lead = await session.get(AcquisitionLead, lead_id)
        assert lead.lead_status == "NEW"
        assert lead.buying_signal is True
        assert lead.last_reply_at is not None
        rows = (await session.execute(select(FunnelMessage))).scalars().all()
        assert sum(1 for row in rows if row.state in {"draft", "queued"}) == 1
        snapshot = await ingest_snapshot(session, [
            MailSnapshot(
                message_id="<gmail-out@mail>",
                from_addr="AlNarjisai@gmail.com",
                to_addrs=(email,),
                text="مسودة لا تُحفظ",
                occurred_at=datetime.now(UTC),
            ),
            MailSnapshot(
                message_id="<gmail-in@mail>",
                from_addr=email,
                to_addrs=("alnarjisai@gmail.com",),
                in_reply_to="<gmail-out@mail>",
                text="إلغاء الرسائل من فضلكم",
                occurred_at=datetime.now(UTC),
            ),
        ])
        second = await ingest_snapshot(session, [
            MailSnapshot(message_id="<gmail-out@mail>", from_addr="alnarjisai@gmail.com", to_addrs=(email,)),
        ])
        await session.commit()
        assert snapshot["linked"] == 2
        assert snapshot["opt_outs"] == 1
        assert second["deduplicated"] == 1
        assert email not in json.dumps(snapshot)
        lead = await session.get(AcquisitionLead, lead_id)
        assert lead.opt_out is True
        assert lead.lead_status == "NEW"
        replies = (await session.execute(select(func.count()).select_from(FunnelReply))).scalar_one()
        assert replies == 2
        kpis = await daily_kpis(session)
        assert kpis["actually_sent"] >= 2
        assert kpis["delivered"] >= 1
        assert kpis["human_replies"] >= 2
        assert kpis["qualified_conversations"] >= 1
        assert "zero_activity" not in {item["code"] for item in kpis["alerts"]}
    text = " ".join(caplog.messages)
    assert email not in text
    await engine.dispose()


async def test_payment_links_only_with_a_token_and_sandbox_stays_local():
    from src.core.portal_auth import make_lead_token
    from src.models import Payment
    from src.models.funnel import PaymentLeadLink
    from src.services.funnel_identity import resolve_lead
    from src.services.funnel_payments import link_payment, open_sandbox_payment
    from src.services.payments import create_payment

    engine, maker = await _engine()
    async with maker() as session:
        resolved = await resolve_lead(session, email="pay@example.com", name="دافع", source="website")
        await session.commit()
        lead_id = resolved["lead"].id
        payment = await create_payment(
            session, "bidaya", customer_email="pay@example.com", founding=False, lead_id=None,
        )
        guessed = await link_payment(session, payment)
        assert guessed["linked"] is False
        assert payment.lead_id is None
        bad = await link_payment(session, payment, token="not-a-token")
        assert bad["reason"] == "token_rejected"
        assert payment.lead_id is None
        token = make_lead_token(lead_id)
        linked = await link_payment(session, payment, token=token)
        repeat = await link_payment(session, payment, token=token)
        await session.commit()
        assert linked["linked"] is True
        assert repeat["deduplicated"] is True
        assert payment.status == "pending"
        assert payment.gateway != "moyasar" or payment.status != "paid"
        stored = await session.get(Payment, payment.id)
        assert stored.lead_id == lead_id
        assert stored.amount == payment.amount
        links = (await session.execute(select(func.count()).select_from(PaymentLeadLink))).scalar_one()
        assert links == 1

    sandbox = await open_sandbox_payment(maker, lead_id)
    assert sandbox["status"] == "paid"
    assert sandbox["gateway"] == "sandbox"
    assert sandbox["linked"] is True
    async with maker() as session:
        row = await session.get(Payment, UUID(sandbox["payment_id"]))
        assert row.gateway == "sandbox"
        assert row.lead_id == lead_id
    await engine.dispose()


async def test_e2e_visit_consult_reply_proposal_sandbox_and_report(monkeypatch):
    from src.core.owner_auth import make_session_token
    from src.main import app
    from src.models import AcquisitionLead, Task
    from src.models.automation import LeadPipeline
    from src.services.agent_dispatch import route_open_callbacks
    from src.services.funnel_record import ConsentBlocked, approve_outreach, record_proposal, record_reply
    from src.services.funnel_payments import open_sandbox_payment

    from src.utils.rate_limit import consult_limiter

    consult_limiter.reset()
    monkeypatch.setattr("src.services.email_service.is_configured", lambda: False)
    engine, maker = await _engine()
    app.state.session_factory = maker
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as anon:
        visit = await anon.get("/consult", follow_redirects=True)
        assert visit.status_code == 200
        assert "consult" in str(visit.url)
        incomplete = await anon.post("/api/consult/callback", json={"name": "غير قابل للتواصل"})
        assert incomplete.status_code == 422
        opened = await anon.post("/api/consult/callback", json={
            "name": "شركة التجربة",
            "email": "journey@example.com",
            "phone": "0553078789",
            "message": "نريد عرضاً",
            "consent": True,
        })
        assert opened.status_code == 200
        body = opened.json()
        assert body["created"] is True
        assert body["callback"]["owner_agent"] in SPECIALTY["sales"]
        assert body["callback"]["next_step"]
        assert body["callback"]["sla_due_at"]
        lead_id = body["lead_id"]
        again = await anon.post("/api/consult/callback", json={
            "email": "journey@example.com",
            "message": "نفس العميل",
        })
        assert again.json()["lead_id"] == lead_id
        assert again.json()["created"] is False

    routed = await route_open_callbacks(maker)
    assert routed["assigned"] == 1
    assert (await route_open_callbacks(maker))["already_assigned"] == 1

    async with maker() as session:
        sent = await approve_outreach(
            session, lead_id=UUID(lead_id), message_id="<journey@mail>", purpose="inquiry",
        )
        assert sent["actually_sent"] is True
        reply = await record_reply(
            session,
            evidence_ref="<journey-reply@mail>",
            text="نعم أبغى العرض",
            in_reply_to="<journey@mail>",
            lead_id=UUID(lead_id),
        )
        assert reply["classification"] == "interested"
        proposal = await record_proposal(session, lead_id=UUID(lead_id), evidence_ref="proposal-journey-1")
        assert proposal["evidence_ref"] == "proposal-journey-1"
        lead = await session.get(AcquisitionLead, UUID(lead_id))
        assert lead.lead_status == "NEW"
        task = (await session.execute(select(Task).where(Task.key == f"funnel:sales:{lead_id}"))).scalar_one()
        assert task.owner_agent in SPECIALTY["sales"]
        assert task.result.get("send_proof") == "journey@mail"
        pipe = await session.get(LeadPipeline, UUID(lead_id))
        assert pipe is not None
        assert pipe.stage == "offer_sent"
        await session.commit()
        with pytest.raises(ConsentBlocked):
            lead.opt_out = True
            await session.commit()
            await approve_outreach(session, lead_id=UUID(lead_id), message_id="<blocked@mail>", purpose="inquiry")

    paid = await open_sandbox_payment(maker, UUID(lead_id))
    assert paid["gateway"] == "sandbox"

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"narjis_owner": make_session_token()},
    ) as owner:
        report = await owner.get("/api/owner/funnel/daily")
        assert report.status_code == 200
        kpis = report.json()
        assert kpis["actually_sent"] >= 1
        assert kpis["human_replies"] >= 1
        assert kpis["qualified_conversations"] >= 1
        assert kpis["proposals"] >= 1
        assert kpis["linked_payments"] >= 1
        detail = await owner.get(f"/api/acquisition/leads/{lead_id}")
        assert detail.status_code == 200
        assert detail.json()["callback"]["owner_agent"] in SPECIALTY["sales"]
        page = await owner.get(f"/acquisition/leads/{lead_id}")
        assert page.status_code == 200
        assert "d.callback" in page.text
        assert "الوكيل المسؤول" in page.text
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as anon:
        denied = await anon.get("/api/owner/funnel/daily")
        assert denied.status_code == 401
    await engine.dispose()
