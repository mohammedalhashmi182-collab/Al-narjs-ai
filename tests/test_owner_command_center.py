"""Owner command center: /owner/command page and GET /api/owner/summary."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.owner_auth import make_session_token
from src.db.session import Base
from src.models import AcquisitionLead, ClientProject, Payment
from src.models.automation import LeadPipeline, ReplyDraft
from src.services import owner_summary

NOW = datetime.now(timezone.utc)


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _seed(maker):
    async with maker() as s:
        a = ClientProject(client_name="مقهى", phone="0555000001", package="radd", status="active",
                          current_period_end=NOW + timedelta(days=3), founding=True, founding_at=NOW)
        b = ClientProject(client_name="متجر", phone="0555000002", package="radd", status="active",
                          current_period_end=NOW + timedelta(days=40))
        s.add_all([a, b])
        lead = AcquisitionLead(company_name="شركة", phone="0555000003", lead_status="NEW")
        s.add(lead)
        await s.flush()
        s.add_all([
            Payment(amount=59900, package="radd", status="paid", gateway="moyasar", gateway_payment_id="m1"),
            Payment(amount=59900, package="radd", status="pending", gateway="invoice", customer_name="عميل تحويل"),
            Payment(amount=59900, package="radd", status="initiated", gateway="moyasar", gateway_payment_id="m2"),
            ReplyDraft(channel="whatsapp", recipient="9665", draft_text="مرحبا", status="pending"),
            ReplyDraft(channel="whatsapp", recipient="9666", draft_text="تم", status="sent"),
            LeadPipeline(lead_id=lead.id, stage="qualified"),
        ])
        await s.commit()
        return a, b


def _client(cookies=None):
    from src.main import app

    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", cookies=cookies or {})


async def test_summary_and_page_require_owner(maker):
    from src.main import app

    app.state.session_factory = maker
    async with _client() as anon:
        assert (await anon.get("/api/owner/summary")).status_code == 401
        page = await anon.get("/owner/command", follow_redirects=False)
        assert page.status_code in (302, 303, 307) and "/login" in page.headers["location"]
    async with _client({"narjis_owner": "forged.token"}) as bad:
        assert (await bad.get("/api/owner/summary")).status_code == 401


async def test_summary_shape_and_numbers(maker):
    from src.main import app

    await _seed(maker)
    app.state.session_factory = maker
    async with _client({"narjis_owner": make_session_token()}) as owner:
        r = await owner.get("/api/owner/summary")
        page = await owner.get("/owner/command")
    assert r.status_code == 200
    d = r.json()
    assert set(d) >= {"generated_at", "revenue", "subscriptions", "renewals_due", "orders", "founding",
                      "usage", "review_queue", "leads", "health"}
    assert d["revenue"]["revenue_halalas"] == 59900 and d["revenue"]["paid_count"] == 1
    assert d["subscriptions"]["active"] == 2 and d["subscriptions"]["mrr_halalas"] == 2 * 59900
    assert d["subscriptions"]["by_plan"][0] == {"plan": "radd", "name": "ردّ", "count": 2,
                                                "mrr_halalas": 119800, "mrr_sar": 1198.0}
    assert d["renewals_due"]["count"] == 1 and d["renewals_due"]["items"][0]["client_name"] == "مقهى"
    assert d["orders"]["unpaid_count"] == 2
    transfers = d["orders"]["awaiting_transfer_confirmation"]
    assert len(transfers) == 1 and transfers[0]["customer"] == "عميل تحويل"
    assert len(d["orders"]["pending_gateway"]) == 1
    # Founding offer removed by the owner: the panel reports it as disabled.
    assert d["founding"]["enabled"] is False and d["founding"]["customers"] == []
    assert d["review_queue"]["pending_total"] == 1
    assert d["leads"]["pipeline"]["qualified"] == 1 and d["leads"]["total_leads"] == 1
    assert d["health"]["database"] is True and d["health"]["status"] in ("ok", "degraded")
    assert {u["flag"] for u in d["usage"]["customers"]} <= {"ok", "warn", "over"}
    assert page.status_code == 200 and "مركز القيادة" in page.text and 'dir="rtl"' in page.text
    assert "/api/owner/summary" in page.text and "confirm-received" in page.text


def test_usage_flags_and_scrub():
    assert owner_summary.scrub("boom sk_live_abcdefghijklmnop failed") == "boom [redacted] failed"
    assert "[redacted]" in owner_summary.scrub("x" * 40)
    assert len(owner_summary.scrub("a " * 500)) <= 160


def test_revoke_button_is_styled():
    html = open("src/web/templates/dashboard.html", encoding="utf-8").read()
    assert 'class="oc-btn"' in html and ".oc-btn{" in html


async def test_usage_rows_flag_at_80_and_100_percent(monkeypatch):
    from src.services import usage

    def row(name, pct, over=False):
        return {"project_id": name, "client_name": name, "package": "radd", "over_limit": over,
                "metrics": {"conversations": {"used": pct * 10, "limit": 1000, "pct": float(pct)}}}

    async def fake(session, now=None, include_inactive=False):
        return [row("a", 50), row("b", 85), row("c", 100), row("d", 10, over=True)]

    monkeypatch.setattr(usage, "owner_usage_report", fake)
    out = await owner_summary._usage(None, NOW)
    flags = {c["client_name"]: c["flag"] for c in out["customers"]}
    assert flags == {"a": "ok", "b": "warn", "c": "over", "d": "over"}
    assert out["warn_count"] == 1 and out["over_count"] == 2
