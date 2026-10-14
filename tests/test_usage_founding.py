"""Usage metering, founding offer and usage add-on packs at checkout."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.owner_auth import make_session_token
from src.db.session import Base
from src.models import ClientProject, Payment
from src.models.usage import SubscriptionUsage, UsageEvent
from src.services import catalog, founding, renewals, usage
from src.services import payments as pm

NOW = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
def alerts(monkeypatch):
    sent: list[str] = []

    async def _fake(text):
        sent.append(text)
        return {"ok": True}

    from src.services import telegram_sender

    monkeypatch.setattr(telegram_sender, "send_owner_alert", _fake)
    return sent


async def _project(s, package="radd", end=None, status="active", **kw):
    proj = ClientProject(client_name="عميل", phone="0555000009", package=package, status=status,
                         current_period_end=end, **kw)
    s.add(proj)
    await s.commit()
    return proj


# ---------------------------------------------------------------- windows

def test_window_is_monthly_and_anchored_on_the_period_end():
    p = SimpleNamespace(current_period_end=datetime(2027, 1, 31, tzinfo=timezone.utc))
    start, end = usage.usage_window(p, NOW)
    assert (start.date().isoformat(), end.date().isoformat()) == ("2026-09-30", "2026-10-31")
    # annual plans still reset monthly
    start, end = usage.usage_window(p, datetime(2027, 1, 30, tzinfo=timezone.utc))
    assert start.month == 12 and end == p.current_period_end


def test_window_without_period_end_is_the_calendar_month():
    start, end = usage.usage_window(SimpleNamespace(current_period_end=None), NOW)
    assert start == datetime(2026, 10, 1, tzinfo=timezone.utc)
    assert end == datetime(2026, 11, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------- metering

async def test_conversation_counts_once_per_contact_per_24h(maker, alerts):
    async with maker() as s:
        proj = await _project(s)
        a = await usage.record_conversation(s, proj, "966500000001", now=NOW)
        b = await usage.record_conversation(s, proj, "966500000001", now=NOW + timedelta(hours=5))
        c = await usage.record_conversation(s, proj, "966500000002", now=NOW + timedelta(hours=5))
        d = await usage.record_conversation(s, proj, "966500000001", now=NOW + timedelta(hours=25))
        assert [a["counted"], b["counted"], c["counted"], d["counted"]] == [True, False, True, True]
        row = await usage.current_usage(s, proj, NOW)
        assert row.conversations == 3


async def test_alerts_at_80_and_100_once_and_service_is_never_cut(maker, alerts, monkeypatch):
    monkeypatch.setitem(catalog.PACKAGES["radd"], "limits", {"conversations": 5, "voice_minutes": 0, "meta_cap": 10000})
    async with maker() as s:
        proj = await _project(s)
        results = [await usage.record_conversation(s, proj, f"c{i}", now=NOW) for i in range(7)]
        assert all(r["counted"] for r in results)  # over the limit still counted, never refused
        row = await usage.current_usage(s, proj, NOW)
        assert row.conversations == 7
        assert row.over_limit and row.overage_conversations == 2
        assert sorted(row.alerts_sent) == ["conversations:100", "conversations:80"]
        assert len(alerts) == 2 and "80" in alerts[0] and "تجاوز الحد" in alerts[1]
        assert usage.suggested_packs(row)["conversation_packs"] == 1
        assert usage.suggested_packs(row)["packs_amount"] == 9900


async def test_voice_on_a_plan_without_voice_alerts_and_rounds_up(maker, alerts):
    async with maker() as s:
        proj = await _project(s, package="radd")
        r = await usage.record_voice(s, proj, 61, ref="call-1", now=NOW)
        dup = await usage.record_voice(s, proj, 61, ref="call-1", now=NOW)
        assert r["counted"] and not dup["counted"]
        row = await usage.current_usage(s, proj, NOW)
        assert usage.usage_summary(proj, row)["metrics"]["voice_minutes"]["used"] == 2
        assert row.over_limit and row.overage_voice_minutes == 2
        assert "voice_minutes:100" in row.alerts_sent


async def test_meta_fee_from_webhook_status_is_counted_once(maker, alerts):
    status = {"id": "wamid.1", "status": "sent",
              "pricing": {"billable": True, "category": "marketing", "pricing_model": "PMP"}}
    assert usage.meta_fee_for_status(status) == (catalog.META_FEE_RATES["marketing"], "marketing")
    assert usage.meta_fee_for_status({"pricing": {"billable": False, "category": "service"}})[0] == 0
    async with maker() as s:
        proj = await _project(s, package="bay")
        await usage.record_meta_fee(s, proj, 17, ref="wamid.1", now=NOW)
        await usage.record_meta_fee(s, proj, 17, ref="wamid.1", now=NOW)
        row = await usage.current_usage(s, proj, NOW)
        assert row.meta_fees == 17 and not row.over_limit


async def test_counters_reset_with_the_next_window_and_packs_raise_limits(maker, alerts):
    async with maker() as s:
        proj = await _project(s, package="bay", addon_conversation_packs=2, addon_voice_packs=1)
        await usage.record_conversation(s, proj, "x", now=NOW)
        nxt = await usage.current_usage(s, proj, NOW + timedelta(days=31))
        assert nxt.conversations == 0
        assert nxt.limit_conversations == 6000 and nxt.limit_voice_minutes == 250
        rows = (await s.execute(select(SubscriptionUsage))).scalars().all()
        assert len(rows) == 2


async def test_whatsapp_webhook_meters_a_linked_client_number(maker, alerts):
    from src.services import whatsapp_webhook

    async with maker() as s:
        proj = await _project(s, package="bay", wa_phone_number_id="1234567890")
        payload = {"entry": [{"changes": [{"value": {
            "metadata": {"phone_number_id": "1234567890"},
            "contacts": [{"wa_id": "966511111111"}],
            "messages": [{"id": "wamid.in1", "from": "966511111111", "type": "text", "text": {"body": "hi"},
                          "timestamp": str(int(NOW.timestamp()))}],
            "statuses": [{"id": "wamid.out1", "status": "delivered",
                          "pricing": {"billable": True, "category": "utility"}}],
        }}]}]}
        await whatsapp_webhook.process_inbound_payload(s, payload)
        await s.commit()
        events = (await s.execute(select(UsageEvent).where(UsageEvent.project_id == proj.id))).scalars().all()
        assert sorted(e.kind for e in events) == ["conversation", "meta_fee"]
        # an unlinked number is not metered
        payload["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"] = "999"
        payload["entry"][0]["changes"][0]["value"]["messages"][0]["id"] = "wamid.in2"
        await whatsapp_webhook.process_inbound_payload(s, payload)
        assert len((await s.execute(select(UsageEvent))).scalars().all()) == 2


# ---------------------------------------------------------------- founding

async def test_founding_auto_applies_and_waives_setup(maker):
    async with maker() as s:
        monthly = await pm.create_payment(s, "bay", "a", "0555000100", None, founding=None)
        annual = await pm.create_payment(s, "bay", "b", "0555000101", None, billing_period="annual", founding=None)
        regular = await pm.create_payment(s, "bay", "c", "0555000102", None)  # default: not auto
    assert monthly.founding and monthly.amount == 149900 - 149900 * 20 // 100  # no 990 setup fee
    assert annual.founding and annual.amount == 1499000 - 1499000 * 30 // 100
    assert "المؤسسين" in monthly.description
    assert not regular.founding and regular.amount == 149900 + 99000


async def test_founding_stops_at_15_seats_and_revoke_frees_one(maker):
    async with maker() as s:
        projects = []
        for i in range(15):
            proj = await _project(s, package="radd", status="pending")
            pay = await pm.create_payment(s, "radd", "x", f"05550002{i:02d}", None, project_id=proj.id, founding=None)
            assert pay.founding
            pay.status = "paid"
            await s.commit()
            await pm.activate_subscription(s, pay)
            projects.append(proj)
        assert await founding.seats_remaining(s) == 0
        assert all(p.founding and p.founding_commitment_until is not None for p in projects)
        late = await pm.create_payment(s, "radd", "late", "0555000300", None, founding=None)
        assert not late.founding and late.amount == 59900
        result = await founding.revoke(s, projects[0])
        assert result["revoked"] and result["seats_remaining"] == 1
        nxt = await pm.create_payment(s, "radd", "next", "0555000301", None, founding=None)
        assert nxt.founding


async def test_unpaid_founding_orders_do_not_consume_seats(maker, monkeypatch):
    monkeypatch.setitem(catalog.FOUNDING_OFFER, "seats", 1)
    async with maker() as s:
        first = await pm.create_payment(s, "radd", "a", "0555000400", None, founding=None)
        second = await pm.create_payment(s, "radd", "b", "0555000401", None, founding=None)
        # Both unpaid orders are shown the founding price; neither takes the seat.
        assert first.founding and second.founding
        assert await founding.seats_remaining(s) == 1


async def test_paid_founding_order_consumes_a_seat(maker):
    async with maker() as s:
        proj = await _project(s, package="radd", status="pending")
        pay = await pm.create_payment(s, "radd", "x", "0555000410", None, project_id=proj.id, founding=None)
        assert await founding.seats_remaining(s) == 15
        pay.status = "paid"
        await s.commit()
        await pm.activate_subscription(s, pay)
        assert proj.founding and await founding.seats_remaining(s) == 14


async def test_seats_rechecked_at_activation_price_honoured_without_exceeding(maker, monkeypatch):
    monkeypatch.setitem(catalog.FOUNDING_OFFER, "seats", 1)
    async with maker() as s:
        p1 = await _project(s, package="radd", status="pending")
        p2 = await _project(s, package="radd", status="pending")
        pay1 = await pm.create_payment(s, "radd", "a", "0555000420", None, project_id=p1.id, founding=None)
        pay2 = await pm.create_payment(s, "radd", "b", "0555000421", None, project_id=p2.id, founding=None)
        assert pay1.founding and pay2.founding
        for pay in (pay1, pay2):
            pay.status = "paid"
            await s.commit()
            await pm.activate_subscription(s, pay)
        assert p1.founding and not p2.founding  # never more than the seat count
        assert pay2.founding and pay2.amount == 59900 - 59900 * 20 // 100  # price honoured
        assert p2.status == "active"
        assert await founding.seats_remaining(s) == 0


async def test_founding_renewal_keeps_price_until_locked_and_not_after_revoke(maker):
    async with maker() as s:
        proj = await _project(s, package="bay", end=NOW + timedelta(days=2), founding=True,
                              founding_at=NOW - timedelta(days=28), founding_locked_until=NOW + timedelta(days=300))
        out = await renewals.run_renewals(s, now=NOW, days_before=5, use_gateway=False)
        assert len(out["invoiced"]) == 1
        pay = (await s.execute(select(Payment).where(Payment.project_id == proj.id))).scalar_one()
        assert pay.founding and pay.amount == 149900 - 149900 * 20 // 100
        await founding.revoke(s, proj)
        again = await pm.create_payment(s, "bay", "c", "0555000009", None, project_id=proj.id,
                                        is_renewal=True, founding=None)
        assert not again.founding and again.amount == 149900


async def test_legacy_renewal_never_gets_founding(maker):
    async with maker() as s:
        assert not await founding.eligible_for_order(s, "team", is_renewal=True)


# ---------------------------------------------------------------- packs

async def test_usage_packs_are_billed_and_carried_to_the_project(maker):
    async with maker() as s:
        proj = await _project(s, package="bay", status="pending")
        pay = await pm.create_payment(s, "bay", "x", "0555000500", None, project_id=proj.id,
                                      billing_period="annual", conversation_packs=2, voice_packs=1)
        assert pay.amount == 1499000 + 3 * 9900 * 10
        assert "محادثة إضافية" in pay.description and "دقيقة صوت" in pay.description
        pay.status = "paid"
        await s.commit()
        await pm.activate_subscription(s, pay)
        assert (proj.addon_conversation_packs, proj.addon_voice_packs) == (2, 1)
        assert usage.project_limits(proj)["conversations"] == 6000
    with pytest.raises(pm.PaymentError):
        pm.usage_packs_amount(catalog.MAX_USAGE_PACKS + 1, 0)
    with pytest.raises(pm.PaymentError):
        pm.usage_packs_amount(-1, 0)


# ---------------------------------------------------------------- API

async def test_checkout_api_applies_founding_and_packs(maker):
    from src.main import app

    app.state.session_factory = maker
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/payments", json={"refund_consent": True, "package": "radd", "method": "invoice",
                                                "conversation_packs": 1})
        seats = (await c.get("/api/founding")).json()
        bad = await c.post("/api/payments", json={"refund_consent": True, "package": "radd", "method": "invoice",
                                                  "voice_packs": 99})
    body = r.json()
    assert body["founding_applied"] is True
    assert body["amount"] == 59900 - 59900 * 20 // 100 + 9900
    assert body["discount"] == 59900 * 20 // 100
    assert seats["seats_total"] == 15 and seats["seats_remaining"] == 15
    assert bad.status_code == 400


async def test_owner_usage_and_founding_endpoints_are_owner_only(maker, alerts):
    from src.main import app

    async with maker() as s:
        proj = await _project(s, package="bay", founding=True, founding_at=NOW)
    app.state.session_factory = maker
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as anon:
        assert (await anon.get("/api/owner/usage")).status_code == 401
        assert (await anon.post(f"/api/owner/founding/{proj.id}/revoke")).status_code == 401
    async with httpx.AsyncClient(transport=transport, base_url="http://test",
                                 cookies={"narjis_owner": make_session_token()}) as owner:
        ev = await owner.post(f"/api/owner/usage/{proj.id}/events", json={"kind": "voice", "quantity": 120, "ref": "c1"})
        link = await owner.post(f"/api/owner/projects/{proj.id}/whatsapp-number", json={"phone_number_id": "555"})
        rep = (await owner.get("/api/owner/usage")).json()
        fnd = (await owner.get("/api/owner/founding")).json()
        rev = await owner.post(f"/api/owner/founding/{proj.id}/revoke")
        rev2 = await owner.post(f"/api/owner/founding/{proj.id}/revoke")
    assert ev.json()["counted"] and link.json()["wa_phone_number_id"] == "555"
    row = rep["customers"][0]
    assert row["metrics"]["voice_minutes"]["used"] == 2 and row["founding"] is True
    assert fnd["status"]["seats_used"] == 1
    assert rev.status_code == 200 and rev2.status_code == 409


def test_landing_and_portal_show_founding_seats():
    from fastapi.testclient import TestClient

    from src.main import app

    with TestClient(app) as c:
        page = c.get("/home").text
        pkgs = c.get("/api/portal/packages").json()
    assert "founding" in pkgs and pkgs["usage_packs_max"] == catalog.MAX_USAGE_PACKS
    if pkgs["founding"]["seats_remaining"] is not None:
        assert "data-founding-remaining" in page


def test_migration_0007_follows_0006():
    import importlib.util
    import pathlib

    path = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0007_usage_founding.py"
    spec = importlib.util.spec_from_file_location("m0007", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.revision == "0007" and mod.down_revision == "0006"
