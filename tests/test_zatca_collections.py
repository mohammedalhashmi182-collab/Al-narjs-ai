"""ZATCA phase-1 simplified tax invoices, credit notes and collections."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.config import settings as st
from src.db.session import Base
from src.models import ClientProject, Payment
from src.models.billing import CollectionReminder
from src.models.company import OutboundMessage
from src.models.usage import SubscriptionUsage
from src.services import catalog, collections, zatca
from src.services import payments as pm

NOW = datetime(2026, 10, 14, 6, 0, tzinfo=timezone.utc)


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture(autouse=True)
def _quiet_channels(monkeypatch):
    sent = {"owner": [], "email": []}

    async def owner(text):
        sent["owner"].append(text)
        return {"ok": True}

    async def email(to, subject, body, html=None):
        sent["email"].append((to, subject))
        return True

    from src.services import email_service, telegram_sender

    monkeypatch.setattr(telegram_sender, "send_owner_alert", owner)
    monkeypatch.setattr(email_service, "send_email", email)
    monkeypatch.setattr(st, "seller_vat_number", None)
    monkeypatch.setattr(st, "billing_auto_send", False)
    return sent


# ------------------------------------------------------------------ QR / seller

def test_tlv_qr_round_trip():
    ts = datetime(2026, 10, 14, 5, 30, tzinfo=timezone.utc)
    b64 = zatca.qr_tlv_base64("مؤسسة ذا أريبيان كونفو", "310122393500003", ts, 68885, 8985)
    d = zatca.decode_tlv(b64)
    assert d == {1: "مؤسسة ذا أريبيان كونفو", 2: "310122393500003", 3: "2026-10-14T05:30:00Z",
                 4: "688.85", 5: "89.85"}


def test_vat_placeholder_flagged_until_configured(monkeypatch):
    s = zatca.seller()
    assert s["vat_placeholder"] and s["vat_number"] == zatca.VAT_PLACEHOLDER
    assert not zatca.readiness()["ready"]
    monkeypatch.setattr(st, "seller_vat_number", "310122393500003")
    assert zatca.seller()["vat_number"] == "310122393500003"
    assert zatca.readiness()["ready"]
    monkeypatch.setattr(st, "seller_vat_number", "12345")  # malformed -> still placeholder
    assert zatca.seller()["vat_placeholder"]


def test_plan_names_are_human_arabic():
    assert zatca.plan_name_ar("radd") == "باقة ردّ"
    assert "radd" not in zatca.plan_name_ar("radd")
    assert zatca.plan_name_ar("team") == "باقة فريق"


# ------------------------------------------------------------------ lines

async def test_lines_reconcile_with_setup_addons_packs(maker, monkeypatch):
    from src.services import catalog as _c
    monkeypatch.setitem(_c.USAGE_ADDONS["voice_minutes"], "purchasable", True)  # billing maths for when voice launches
    async with maker() as s:
        p = await pm.create_payment(s, "numuw", "x", "0555000000", None, addons=2,
                                    conversation_packs=1, voice_packs=1, founding=False)
    pv = zatca.preview(p)
    names = [l["name"] for l in pv["lines"]]
    assert names[0].startswith("باقة النمو")
    assert any("وكيل إضافي" in n for n in names)
    assert any("رسوم إعداد" in n for n in names)
    assert sum(1 for n in names if n.startswith("باقة ١")) == 2
    assert pv["subtotal"] == p.amount
    assert pv["total"] == pm.total_with_vat(p.amount)
    assert all(l["vat_rate"] == 15 for l in pv["lines"])


async def test_founding_discount_is_a_line(maker):
    async with maker() as s:
        p = await pm.create_payment(s, "bidaya", "x", "0555000000", None, founding=True)
    pv = zatca.preview(p)
    disc = [l for l in pv["lines"] if l["net"] < 0]
    assert disc and "المؤسسين" in disc[0]["name"]
    assert pv["subtotal"] == p.amount and pv["total"] == pm.total_with_vat(p.amount)


# ------------------------------------------------------------------ issue

async def test_sequential_numbers_and_idempotent_issue(maker):
    async with maker() as s:
        a = await pm.create_payment(s, "bidaya", "a", "0555000001", None, founding=False)
        b = await pm.create_payment(s, "numuw", "b", "0555000002", None, founding=False)
        assert await zatca.ensure_invoice(s, a) is None  # unpaid: pro-forma only
        a.status = b.status = "paid"
        await s.commit()
        ia = await zatca.ensure_invoice(s, a, now=NOW)
        ib = await zatca.ensure_invoice(s, b, now=NOW)
        again = await zatca.ensure_invoice(s, a)
    assert (ia.invoice_number, ib.invoice_number) == ("INV-000001", "INV-000002")
    assert again.id == ia.id
    qr = zatca.decode_tlv(ia.qr_tlv)
    assert qr[4] == f"{pm.total_with_vat(a.amount) / 100:.2f}" and qr[5] == f"{pm.vat_amount(a.amount) / 100:.2f}"


async def test_credit_notes_never_exceed_invoice(maker):
    async with maker() as s:
        p = await pm.create_payment(s, "bidaya", "a", "0555000001", None, founding=False)
        p.status = "paid"
        await s.commit()
        inv = await zatca.ensure_invoice(s, p, now=NOW)
        part = await zatca.issue_credit_note(s, p, amount=10000, reason="استرداد جزئي")
        assert part.invoice_number == "CRN-000001" and part.kind == "credit_note"
        assert part.subtotal == 10000 and part.vat_total == 1500
        assert part.original_invoice_id == inv.id
        rest = await zatca.issue_credit_note(s, p)
        assert rest.subtotal == inv.subtotal - 10000
        with pytest.raises(zatca.ZatcaError):
            await zatca.issue_credit_note(s, p, amount=1)


async def test_unpaid_order_cannot_be_credited(maker):
    async with maker() as s:
        p = await pm.create_payment(s, "bidaya", "a", "0555000001", None, founding=False)
        with pytest.raises(zatca.ZatcaError):
            await zatca.issue_credit_note(s, p)


# ------------------------------------------------------------------ collections

async def _project_with_renewal(s, end, status="invoice"):
    proj = ClientProject(client_name="متجر", phone="0555111222", email="c@example.com", package="radd",
                         status="active", current_period_end=end)
    s.add(proj)
    await s.commit()
    pay = await pm.create_payment(s, "bidaya", "متجر", "0555111222", "c@example.com", project_id=proj.id,
                                  is_renewal=True, founding=False)
    pay.status = status
    proj.renewal_payment_id = pay.id
    await s.commit()
    return proj, pay


@pytest.mark.parametrize("delta,stage", [(timedelta(days=4), "d-5"), (timedelta(hours=12), "d-1"),
                                         (timedelta(hours=-2), "d0"), (timedelta(days=-3, hours=-1), "d+3")])
def test_due_stage(delta, stage):
    assert collections.due_stage(NOW + delta, NOW) == stage


async def test_reminders_are_drafts_by_default_and_run_once(maker, _quiet_channels):
    async with maker() as s:
        proj, pay = await _project_with_renewal(s, NOW + timedelta(hours=12))
        r1 = await collections.run_collections(s, now=NOW, base_url="https://karmaai.online")
        r2 = await collections.run_collections(s, now=NOW, base_url="https://karmaai.online")
        drafts = (await s.execute(select(OutboundMessage))).scalars().all()
    assert [x["stage"] for x in r1["reminders"]] == ["d-1"] and r2["reminders"] == []
    ch = r1["reminders"][0]["channels"]
    assert ch == {"owner_telegram": "sent", "email": "draft", "whatsapp": "draft:needs_template"}
    assert r1["whatsapp_template_missing"] and not r1["auto_send"]
    assert _quiet_channels["email"] == [] and len(_quiet_channels["owner"]) == 1
    assert {d.channel for d in drafts} == {"email", "whatsapp"} and all(d.status == "draft" for d in drafts)
    assert all(f"/invoice/{pay.id}" in d.text for d in drafts)


async def test_auto_send_emails_customer(maker, monkeypatch, _quiet_channels):
    from src.services import email_service

    monkeypatch.setattr(st, "billing_auto_send", True)
    monkeypatch.setattr(email_service, "is_configured", lambda: True)
    async with maker() as s:
        await _project_with_renewal(s, NOW - timedelta(hours=1))
        r = await collections.run_collections(s, now=NOW)
    assert r["reminders"][0]["stage"] == "d0" and r["reminders"][0]["channels"]["email"] == "sent"
    assert _quiet_channels["email"][0][0] == "c@example.com"


async def test_paid_renewal_gets_no_reminder(maker):
    async with maker() as s:
        await _project_with_renewal(s, NOW + timedelta(hours=12), status="paid")
        r = await collections.run_collections(s, now=NOW)
    assert r["reminders"] == []


async def test_failed_payment_recovery_link_once(maker):
    async with maker() as s:
        p = await pm.create_payment(s, "bidaya", "a", "0555000001", "a@example.com", founding=False)
        p.status = "failed"
        p.created_at = NOW - timedelta(hours=2)
        await s.commit()
        r1 = await collections.run_collections(s, now=NOW, base_url="https://karmaai.online")
        r2 = await collections.run_collections(s, now=NOW)
    assert r1["recovery"][0]["recovery_url"] == f"https://karmaai.online/invoice/{p.id}"
    assert r2["recovery"] == []


async def test_overage_invoice_from_closed_usage_window(maker):
    async with maker() as s:
        proj = ClientProject(client_name="متجر", phone="0555111222", package="radd", status="active",
                             current_period_end=NOW + timedelta(days=20))
        s.add(proj)
        await s.commit()
        s.add(SubscriptionUsage(project_id=proj.id, period_start=NOW - timedelta(days=40),
                                period_end=NOW - timedelta(days=10), over_limit=True,
                                overage_conversations=1500, overage_meta_fees=1234, alerts_sent=[]))
        await s.commit()
        r1 = await collections.run_collections(s, now=NOW)
        r2 = await collections.run_collections(s, now=NOW)
        pay = (await s.execute(select(Payment).where(Payment.package == zatca.OVERAGE_PACKAGE))).scalar_one()
        rows = (await s.execute(select(CollectionReminder))).scalars().all()
        pay.status = "paid"
        await s.commit()
        inv = await zatca.ensure_invoice(s, pay, now=NOW)
        res = await pm.activate_subscription(s, pay)
    conv_amt = catalog.USAGE_ADDONS["conversations"]["amount"]
    assert len(r1["overage"]) == 1 and r2["overage"] == []
    assert pay.amount == 2 * conv_amt + 1234 and pay.addon_conversation_packs == 2 and pay.project_id is None
    assert rows[0].stage.startswith("overage:")
    assert [l["net"] for l in inv.lines] == [2 * conv_amt, 1234] and inv.total == pm.total_with_vat(pay.amount)
    assert not res["activated"]  # paying overage never touches the subscription period


async def test_invoice_page_renders_tax_invoice(maker, monkeypatch):
    import httpx

    from src.main import app

    monkeypatch.setattr(st, "seller_vat_number", "310122393500003")
    app.state.session_factory = maker
    async with maker() as s:
        p = await pm.create_payment(s, "bidaya", "a", "0555000001", None, founding=False)
        unpaid = await pm.create_payment(s, "bidaya", "b", "0555000002", None, founding=False)
        p.status = "paid"
        await s.commit()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get(f"/invoice/{p.id}")
        u = await c.get(f"/invoice/{unpaid.id}")
    assert r.status_code == 200
    assert "فاتورة ضريبية مبسطة" in r.text and "INV-000001" in r.text and "310122393500003" in r.text
    assert "باقة البداية" in r.text and ">bidaya<" not in r.text
    assert "فاتورة مبدئية" in u.text and "INV-" not in u.text
