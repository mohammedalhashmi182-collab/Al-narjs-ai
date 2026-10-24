"""Offer-vs-capability copy, weekly reports, monitoring, WhatsApp templates,
PDPL pages and conversation QA (feat/offer-ops-compliance)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.owner_auth import make_session_token
from src.db.session import Base
from src.models import ClientProject, InboundMessage, OutboundMessage
from src.models.automation import ReplyDraft
from src.models.ops import WeeklyReport, WhatsAppTemplate
from src.models.usage import UsageEvent
from src.services import catalog, draft_qa, ops_monitor, wa_templates, weekly_reports

TPL = Path(__file__).resolve().parent.parent / "src" / "web" / "templates"
NOW = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)  # Wednesday


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
    ops_monitor._reset_throttle()
    yield sent
    ops_monitor._reset_throttle()


def _client(maker, owner=True):
    from src.main import app

    app.state.session_factory = maker
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                             cookies={"narjis_owner": make_session_token()} if owner else {})


# ------------------------------------------------------------------ 1. offer vs capability

UNBUILT_LIVE_CLAIMS = ["ووكيل صوتي بلهجة سعودية\"", "ربط سلة وزد:", "٣ قنوات + وكيل صوتي", "+ خط صوت",
                       "Salla and Zid integration:", "3 channels + a voice agent", "+ a voice line"]


def test_catalog_no_longer_sells_unbuilt_features_as_live():
    text = "\n".join(line for p in catalog.PACKAGES.values() for line in p["scope"] + p["scope_en"])
    for claim in UNBUILT_LIVE_CLAIMS:
        assert claim not in text
    # Salla/Zid is labelled coming soon and is not sold as included.
    growth = catalog.PACKAGES["numuw"]
    assert any("قريباً" in line for line in growth["coming"])
    assert any("coming soon" in line.lower() for line in growth["coming_en"])
    for key in catalog.PACKAGE_ORDER:
        for line in catalog.PACKAGES[key]["scope"] + catalog.PACKAGES[key]["scope_en"]:
            low = line.lower()
            assert "تيليجرام" not in line and "ماسنجر" not in line
            assert "telegram" not in low and "messenger" not in low
            assert "وكيل صوتي" not in line and "دقائق الصوت" not in line
            assert "voice agent" not in low and "voice minute" not in low


def test_salla_zid_scope_line_stays_coming_soon():
    """النمو lists the store connection as coming soon, not as included."""
    line = next(item for item in catalog.PACKAGES["numuw"]["coming"] if "سلة" in item)
    assert line == "ربط سلة أو زد (قريباً)"
    en = next(item for item in catalog.PACKAGES["numuw"]["coming_en"] if "Salla" in item)
    assert "coming soon" in en.lower()
    assert not any("سلة" in item for item in catalog.PACKAGES["numuw"]["scope"])


def test_prices_and_limits_unchanged():
    assert [catalog.PACKAGES[k]["amount"] for k in catalog.PACKAGE_ORDER] == [79000, 149000, 299000]
    assert [catalog.PACKAGES[k]["limits"]["conversations"] for k in catalog.PACKAGE_ORDER] == [1000, 4000, 10000]


def test_landing_does_not_sell_voice_minutes():
    html = (TPL / "landing.html").read_text(encoding="utf-8") + (TPL / "partials" / "_pricing_section.html").read_text(encoding="utf-8")
    assert "دقائق الصوت" not in html and "Voice minutes" not in html


# ------------------------------------------------------------------ 6. conversation QA

def test_qa_accepts_catalog_prices():
    from src.services import smart_reply

    r = draft_qa.score_draft(smart_reply.plan_lines("numuw"))
    assert not any(i["code"] == "invented_price" for i in r["issues"]), r


def test_qa_flags_invented_price():
    r = draft_qa.score_draft("باقة بيع بـ 777 ريال شهرياً فقط")
    assert r["flagged"] and r["issues"][0]["code"] == "invented_price" and r["issues"][0]["detail"] == [777]


def test_qa_accepts_price_found_in_kb():
    r = draft_qa.score_draft("سعر التوصيل 25 ريال", kb_texts=["رسوم التوصيل داخل الرياض 25 ريال"])
    assert r["score"] == 100


def test_qa_flags_unbuilt_feature_unless_coming_soon():
    assert draft_qa.score_draft("عندنا وكيل صوتي يرد على المكالمات")["issues"][0]["code"] == "unbuilt_feature"
    assert draft_qa.score_draft("الوكيل الصوتي قريباً")["score"] == 100


def test_qa_flags_guarantee_and_arabic_digits():
    r = draft_qa.score_draft("نضمن لك 50% زيادة في المبيعات بسعر ٨٨٨ ر.س")
    codes = {i["code"] for i in r["issues"]}
    assert {"invented_price", "unsupported_claim"} <= codes and r["flagged"]


async def test_low_score_draft_stays_pending_in_auto_mode(maker, monkeypatch):
    from src.services import smart_reply

    sent = []

    async def _fake_send(session, draft, base_url=None):
        sent.append(draft.id)

    monkeypatch.setattr(smart_reply, "_send_draft", _fake_send)
    async with maker() as s:
        await smart_reply.set_mode(s, "telegram", "auto")
        bad = ReplyDraft(channel="telegram", recipient="1", kind="reply", draft_text="السعر 777 ريال", status="pending")
        good = ReplyDraft(channel="telegram", recipient="2", kind="reply", draft_text="أهلاً بك", status="pending")
        await smart_reply.queue_or_send(s, bad)
        await smart_reply.queue_or_send(s, good)
        assert bad.meta["qa"]["flagged"] and sent == [good.id]
        assert smart_reply.draft_to_dict(bad)["qa_flagged"] is True
        await s.commit()
    async with _client(maker) as c:
        r = await c.get("/api/owner/ops/qa/flagged")
        assert r.status_code == 200 and [d["id"] for d in r.json()["drafts"]] == [str(bad.id)]


# ------------------------------------------------------------------ 2. weekly report

async def _project(s, package="tashgheel", phone="0555000009"):
    p = ClientProject(client_name="متجر الورد", phone=phone, package=package, status="active",
                      current_period_end=NOW + timedelta(days=20))
    s.add(p)
    await s.commit()
    return p


async def test_weekly_report_counts_real_events_only(maker, alerts):
    start, end = weekly_reports.week_bounds(NOW)
    assert start.weekday() == 6 and (end - start).days == 7 and end <= NOW
    async with maker() as s:
        p = await _project(s)
        small = await _project(s, package="radd", phone="0555000010")
        s.add_all([
            UsageEvent(project_id=p.id, kind="conversation", channel="whatsapp", contact_key="a", occurred_at=start - timedelta(days=3)),
            UsageEvent(project_id=p.id, kind="conversation", channel="whatsapp", contact_key="a", occurred_at=start + timedelta(days=1)),
            UsageEvent(project_id=p.id, kind="conversation", channel="telegram", contact_key="b", occurred_at=start + timedelta(days=2)),
            UsageEvent(project_id=p.id, kind="conversation", channel="telegram", contact_key="c", occurred_at=end + timedelta(hours=1)),
        ])
        await s.commit()
        reps = await weekly_reports.generate_all(s, NOW)
        assert [r.project_id for r in reps] == [p.id]  # radd is not an Operate project
        m = reps[0].metrics
        assert (m["conversations"], m["unique_contacts"], m["new_contacts"], m["returning_contacts"]) == (2, 2, 1, 1)
        assert m["by_channel"] == {"whatsapp": 1, "telegram": 1}
        assert reps[0].status == "draft" and "متجر الورد" in reps[0].text
        again = await weekly_reports.generate_all(s, NOW)
        assert again[0].id == reps[0].id  # idempotent per week
    assert any("للمراجعة" in a for a in alerts)
    del small


async def test_weekly_report_needs_owner_approval_and_uses_fallback(maker, alerts):
    async with maker() as s:
        p = await _project(s)
        rep = await weekly_reports.generate_for_project(s, p, NOW)
        await s.commit()
        rid = rep.id
        assert (await s.execute(select(OutboundMessage))).scalars().first() is None  # nothing sent on draft
    async with _client(maker, owner=False) as anon:
        assert (await anon.post(f"/api/owner/ops/weekly-reports/{rid}/approve")).status_code in (401, 403, 303, 307)
    async with _client(maker) as c:
        r = await c.post(f"/api/owner/ops/weekly-reports/{rid}/edit", json={"text": "تقرير معدّل"})
        assert r.json()["final_text"] == "تقرير معدّل"
        r = await c.post(f"/api/owner/ops/weekly-reports/{rid}/approve")
        body = r.json()
        assert body["status"] == "approved" and body["send_result"]["path"] == "fallback"
        assert (await c.post(f"/api/owner/ops/weekly-reports/{rid}/approve")).status_code == 409
    async with maker() as s:
        msg = (await s.execute(select(OutboundMessage))).scalars().one()
        assert msg.status == wa_templates.FALLBACK_STATUS and msg.text == "تقرير معدّل"


# ------------------------------------------------------------------ 4. WhatsApp templates

def test_template_payload_shape_has_no_credentials():
    tpl = WhatsAppTemplate(name="renewal_reminder_ar", language="ar", category="UTILITY", purpose="renewal",
                           body=wa_templates.DEFAULT_TEMPLATES["renewal_reminder_ar"]["body"], param_count=4)
    p = wa_templates.build_template_payload("+966 55 500 0009", tpl, ["أ", "ب"])
    assert p["type"] == "template" and p["to"] == "966555000009"
    params = p["template"]["components"][0]["parameters"]
    assert len(params) == 4 and params[2]["text"] == "-"
    assert "Bearer" not in str(p) and "token" not in str(p).lower()


async def test_seed_is_draft_and_never_overwrites(maker):
    async with maker() as s:
        assert await wa_templates.seed_defaults(s) == len(wa_templates.DEFAULT_TEMPLATES)
        await wa_templates.set_status(s, "followup_ar", "approved")
        assert await wa_templates.seed_defaults(s) == 0
        assert (await s.get(WhatsAppTemplate, "followup_ar")).status == "approved"
        assert (await s.get(WhatsAppTemplate, "renewal_reminder_ar")).status == "draft"


@pytest.fixture
def wa_on(monkeypatch):
    from src.config import settings as st

    object.__setattr__(st, "whatsapp_token", "TEST-TOKEN")
    object.__setattr__(st, "whatsapp_phone_number_id", "123")
    yield
    object.__setattr__(st, "whatsapp_token", None)
    object.__setattr__(st, "whatsapp_phone_number_id", None)


async def test_out_of_window_uses_approved_template(maker, wa_on, monkeypatch, alerts):
    posted = []

    async def _post(payload):
        posted.append(payload)
        return {"ok": True, "provider_message_id": "wamid.1"}

    monkeypatch.setattr(wa_templates, "_post_template", _post)
    async with maker() as s:
        await wa_templates.seed_defaults(s)
        r = await wa_templates.send_business_initiated(s, phone="0555000009", purpose="followup", text="نتابع معك")
        assert r["path"] == "fallback" and not posted  # template still draft
        await wa_templates.set_status(s, "followup_ar", "approved")
        r = await wa_templates.send_business_initiated(s, phone="0555000009", purpose="followup", text="نتابع معك",
                                                       params=["سارة"])
        assert r == {"ok": True, "path": "template", "template": "followup_ar"}
        assert posted[0]["template"]["name"] == "followup_ar"
        row = (await s.execute(select(OutboundMessage).where(OutboundMessage.message_type == "template"))).scalars().one()
        assert row.status == "sent" and row.provider_message_id == "wamid.1" and "سارة" in row.text


async def test_inside_window_sends_plain_text(maker, wa_on, monkeypatch):
    from src.services import whatsapp_sender

    calls = []

    async def _send_now(session, **kw):
        calls.append(kw)
        return {"ok": True}

    monkeypatch.setattr(whatsapp_sender, "send_now", _send_now)
    async with maker() as s:
        s.add(InboundMessage(sender_number="966555000009", provider_message_id="m1", occurred_at=datetime.now(UTC) - timedelta(hours=2)))
        await s.commit()
        assert await wa_templates.within_window(s, "0555000009")
        r = await wa_templates.send_business_initiated(s, phone="0555000009", purpose="renewal", text="تجديد")
        assert r["path"] == "session_text" and calls[0]["text"] == "تجديد"


async def test_template_admin_api(maker):
    async with _client(maker) as c:
        r = await c.get("/api/owner/ops/wa-templates")
        names = {t["name"] for t in r.json()["templates"]}
        assert set(wa_templates.DEFAULT_TEMPLATES) == names
        assert (await c.put("/api/owner/ops/wa-templates/followup_ar", json={"status": "approved"})).json()["status"] == "approved"
        assert (await c.put("/api/owner/ops/wa-templates/followup_ar", json={"status": "bogus"})).status_code == 400
        assert (await c.put("/api/owner/ops/wa-templates/nope", json={"status": "approved"})).status_code == 404


def test_template_docs_list_every_template():
    doc = (Path(__file__).resolve().parent.parent / "docs" / "whatsapp-templates.md").read_text(encoding="utf-8")
    for name in wa_templates.DEFAULT_TEMPLATES:
        assert name in doc


# ------------------------------------------------------------------ 3. monitoring

async def _ok_probe(url):
    return {"ok": True, "status_code": 200}


async def _down_probe(url):
    return {"ok": False, "error": "ConnectError"}


async def test_deep_health_reports_db_and_externals(maker, monkeypatch):
    monkeypatch.setattr(ops_monitor, "configured_externals", lambda: {"telegram": True, "whatsapp": False,
                                                                     "moyasar": False, "gemini": False})
    r = await ops_monitor.deep_health(maker, _ok_probe)
    assert r["status"] == "healthy" and r["db"]["ok"] and r["external"]["whatsapp"]["configured"] is False
    r = await ops_monitor.deep_health(maker, _down_probe)
    assert r["status"] == "degraded" and r["degraded"] == ["telegram"]


def test_capability_readiness_never_exposes_secret_values(monkeypatch):
    from src.integrations import config as store_config
    from src.integrations import crypto as store_crypto
    from src.services import email_service
    from src.services.agent_tools import web_search

    monkeypatch.setattr(email_service, "is_configured", lambda: True)
    monkeypatch.setattr(web_search, "status", lambda: {"enabled": True, "provider": "tavily", "env_vars": ["INTERNAL_VAR"]})
    monkeypatch.setattr(store_config, "enabled", lambda: False)
    monkeypatch.setattr(store_crypto, "key_ready", lambda: True)
    monkeypatch.setattr(store_config, "salla_oauth_ready", lambda: True)
    monkeypatch.setattr(store_config, "zid_oauth_ready", lambda: False)

    data = ops_monitor.capability_readiness()
    assert data == {
        "email": {"configured": True},
        "web_search": {"enabled": True, "provider": "tavily"},
        "stores": {
            "enabled": False,
            "store_crypto_ready": True,
            "salla_oauth_ready": True,
            "zid_oauth_ready": False,
        },
    }
    text = str(data).lower()
    assert "secret" not in text and "token" not in text and "key" not in text


async def test_health_endpoint_stays_cheap_and_deep_is_opt_in(maker, monkeypatch):
    monkeypatch.setattr(ops_monitor, "configured_externals", lambda: {})
    async with _client(maker, owner=False) as c:
        assert (await c.get("/health")).json() == {"status": "healthy", "version": "0.1.0"}
        deep = (await c.get("/health/deep")).json()
        assert deep["status"] == "healthy" and deep["db"]["ok"] is True
        text = str(deep).lower()
        assert "token" not in text and "secret" not in text


async def test_uptime_check_alerts_owner_once(maker, monkeypatch, alerts):
    monkeypatch.setattr(ops_monitor, "configured_externals", lambda: {})
    r = await ops_monitor.run_uptime_check(maker, base_url="https://example.test", probe=_down_probe)
    assert r["status"] == "unhealthy" and len(alerts) == 1 and "/health" in alerts[0]
    await ops_monitor.run_uptime_check(maker, base_url="https://example.test", probe=_down_probe)
    assert len(alerts) == 1  # throttled
    ok = await ops_monitor.run_uptime_check(maker, base_url="https://example.test", probe=_ok_probe)
    assert ok["status"] == "healthy"


async def test_webhook_5xx_alerts_owner(maker, alerts, monkeypatch):
    from src.services import payments as pm

    async def _boom(session, event):
        raise pm.PaymentError("moyasar down")

    from src.config import settings as st

    object.__setattr__(st, "moyasar_webhook_secret", "S")
    monkeypatch.setattr(pm, "handle_moyasar_webhook", _boom)
    try:
        async with _client(maker, owner=False) as c:
            r = await c.post("/webhooks/moyasar", json={"secret_token": "S", "id": "x"})
        assert r.status_code == 502
        assert len(alerts) == 1 and "ميسّر" in alerts[0] and "502" in alerts[0] and "secret" not in alerts[0].lower()
    finally:
        object.__setattr__(st, "moyasar_webhook_secret", None)


def test_runbook_covers_required_incidents():
    doc = (Path(__file__).resolve().parent.parent / "docs" / "runbooks.md").read_text(encoding="utf-8")
    for heading in ("Failed deploy", "Meta (WhatsApp) token", "Payment webhook failure"):
        assert heading in doc


# ------------------------------------------------------------------ 5. PDPL / contact pages

@pytest.mark.parametrize("path,needle", [("/dpa", "PDPL"), ("/subprocessors", "Gemini"), ("/contact", "data-open-assistant")])
async def test_public_compliance_pages_render(maker, path, needle):
    async with _client(maker, owner=False) as c:
        r = await c.get(path, follow_redirects=True)
    assert r.status_code == 200 and needle in r.text
    assert 'href="#"' not in r.text
    # site contact = the Al-Narjis assistant + email; no direct channels
    assert "t.me/" not in r.text and "wa.me/" not in r.text
    assert 'id="siteAssistant"' in r.text
    for link in ("/privacy", "/terms", "/data-deletion"):
        assert f'href="{link}"' in r.text


def test_google_subprocessor_includes_embeddings():
    from src.interfaces.ops_routes import SUBPROCESSORS

    google = next(row for row in SUBPROCESSORS if row["name"].startswith("Google"))
    assert "embeddings" in google["purpose_en"]
    assert "تضمين النصوص" in google["purpose_ar"]
    assert "embeddings" not in google["purpose_ar"]


def test_retention_table_is_on_subprocessors_and_dpa():
    from src.interfaces.ops_routes import RETENTION

    assert any("30" in r["period_ar"] for r in RETENTION)
    for name in ("dpa.html", "subprocessors.html"):
        assert "retention" in (TPL / name).read_text(encoding="utf-8")


def test_footer_links_to_new_pages():
    html = (TPL / "landing.html").read_text(encoding="utf-8")
    for link in ('href="/dpa"', 'href="/subprocessors"', 'href="/contact"'):
        assert link in html
