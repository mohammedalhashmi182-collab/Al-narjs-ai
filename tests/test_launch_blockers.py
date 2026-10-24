"""Launch blockers: package-mismatch activation exploit, public contact leaks,
agent-result email delivery, and API docs in production."""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
from contextlib import contextmanager
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.models import ClientAgent, ClientProject, Payment
from src.services import catalog
from src.services import payments as pm

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@contextmanager
def _settings(**values):
    from src.config import settings as s

    old = {k: getattr(s, k) for k in values}
    for k, v in values.items():
        object.__setattr__(s, k, v)
    pm._credential_cache.clear()
    try:
        yield
    finally:
        for k, v in old.items():
            object.__setattr__(s, k, v)
        pm._credential_cache.clear()


def _client(maker, owner=False, project=None):
    from src import main
    from src.core import portal_auth
    from src.core.owner_auth import make_session_token

    main.app.state.session_factory = maker
    main._payment_replays.clear()
    main._payment_locks.clear()
    main._portal_run_replays.clear()
    main._portal_run_locks.clear()
    cookies = {"narjis_owner": make_session_token()} if owner else {}
    if project is not None:
        cookies[portal_auth.COOKIE_NAME] = portal_auth.make_session_token(project)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test", cookies=cookies)


async def _project(maker, package="numuw", addons=0, status="pending", email=None):
    async with maker() as s:
        p = ClientProject(client_name="c", phone="0555000111", package=package, status=status,
                          addon_agents=addons, email=email)
        s.add(p)
        await s.commit()
        return p


def _price(package, addons=0):
    return min(pm.expected_order_amounts(catalog.resolve_tier(package), catalog.resolve_billing_period(None), addons))


async def _paid(maker, project, package, addons=0, amount=None):
    async with maker() as s:
        pay = Payment(amount=_price(package, addons) if amount is None else amount, currency="SAR",
                      package=package, addon_agents=addons, customer_phone=project.phone,
                      project_id=project.id, status="paid", gateway="moyasar")
        s.add(pay)
        await s.commit()
        return pay


def _cheapest_and_bigger():
    tiers = sorted({catalog.resolve_tier(k) for k in ("bidaya", "numuw", "team")}, key=_price)
    return tiers[0], tiers[-1]


# --- 1. package-mismatch privilege escalation --------------------------------

@pytest.mark.parametrize("kind", ["cheaper_package", "fewer_addons", "wrong_amount"])
async def test_mismatched_payment_does_not_activate_and_goes_to_review(maker, kind):
    cheap, big = _cheapest_and_bigger()
    assert cheap != big
    project = await _project(maker, package=big, addons=2)
    if kind == "cheaper_package":
        pay = await _paid(maker, project, cheap, addons=2)
    elif kind == "fewer_addons":
        pay = await _paid(maker, project, big, addons=0)
    else:
        pay = await _paid(maker, project, big, addons=2, amount=100)
    async with maker() as s:
        out = await pm.activate_subscription(s, await s.get(Payment, pay.id))
    assert out["activated"] is False and out.get("review") is True
    async with maker() as s:
        assert (await s.get(ClientProject, project.id)).status == "pending"
        assert (await s.get(Payment, pay.id)).status == pm.REVIEW_STATUS


async def test_matching_payment_activates(maker):
    _, big = _cheapest_and_bigger()
    project = await _project(maker, package=big, addons=1)
    pay = await _paid(maker, project, big, addons=1)
    async with maker() as s:
        out = await pm.activate_subscription(s, await s.get(Payment, pay.id))
    assert out["activated"] is True
    async with maker() as s:
        assert (await s.get(ClientProject, project.id)).status == "active"


async def test_create_payment_takes_package_and_addons_from_the_project(maker):
    cheap, big = _cheapest_and_bigger()
    project = await _project(maker, package=big, addons=1)
    async with _client(maker, owner=True) as c:
        with _settings(moyasar_api_secret=None):
            r = await c.post("/api/payments", json={
                "refund_consent": True, "package": cheap, "addons": 0, "method": "invoice",
                "project_id": str(project.id)})
    assert r.status_code == 200, r.text
    async with maker() as s:
        pay = (await s.execute(select(Payment))).scalar_one()
    assert catalog.resolve_tier(pay.package) == big
    assert int(pay.addon_agents or 0) == 1
    assert pay.amount == _price(big, 1)


async def test_create_payment_rejects_unknown_or_bad_project(maker):
    async with _client(maker, owner=True) as c:
        with _settings(moyasar_api_secret=None):
            missing = await c.post("/api/payments", json={"refund_consent": True, "package": "bidaya",
                                   "method": "invoice", "project_id": "00000000-0000-0000-0000-000000000000"})
            bad = await c.post("/api/payments", json={"refund_consent": True, "package": "bidaya",
                               "method": "invoice", "project_id": "nope"})
    assert missing.status_code == 404
    assert bad.status_code == 422


# --- 2. no phone / email on public pages --------------------------------------

OWNER_ONLY = {"sales_dashboard.html", "sales_lead.html"}
FORBIDDEN = ("tel:", "mailto:", "0540799266")


def test_public_templates_have_no_phone_or_mailto():
    bad = []
    for path in (ROOT / "src/web/templates").rglob("*.html"):
        if path.name in OWNER_ONLY:
            continue
        text = path.read_text(encoding="utf-8")
        bad += [f"{path.relative_to(ROOT)}: {n}" for n in FORBIDDEN if n in text]
    assert not bad, bad


@pytest.mark.parametrize("path", ["/", "/home", "/ar/home", "/contact", "/about", "/pricing", "/privacy",
                                  "/refund-policy", "/dpa", "/subprocessors", "/data-deletion",
                                  "/ar/services/chatbots", "/invoice/deadbeef-0000-0000-0000-000000000000"])
async def test_rendered_public_pages_have_no_phone_or_mailto(maker, path):
    async with _client(maker) as c:
        r = await c.get(path, follow_redirects=True)
    assert r.status_code < 500
    for needle in FORBIDDEN:
        assert needle not in r.text, (path, needle)


async def test_capabilities_has_no_contact(maker):
    async with _client(maker) as c:
        caps = (await c.get("/api/payments/capabilities")).json()
    assert "contact" not in caps
    assert "0540799266" not in str(caps)


def test_operator_identity_is_kept():
    text = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "src/web/templates").rglob("*.html"))
    assert "FL-272182297" in text


# --- 3. agent results are emailed ---------------------------------------------

def _fake_runtime(monkeypatch, content="RESULT"):
    from src import main

    tmpl = SimpleNamespace(template_text="Do the work for {{client_name}}")
    agent_def = SimpleNamespace(name="Agent", prompt_templates={"default": tmpl}, default_parameters={})

    class _Reg:
        async def get_agent(self, slug):
            return agent_def

    class _Engine:
        def render(self, text, variables):
            return SimpleNamespace(user_prompt=text, system_prompt="sys")

    class _Model:
        async def complete_with_fallback(self, provider, req):
            return SimpleNamespace(content=content)

    monkeypatch.setattr(main.app.state, "agent_registry", _Reg(), raising=False)
    monkeypatch.setattr(main.app.state, "prompt_engine", _Engine(), raising=False)
    monkeypatch.setattr(main.app.state, "model_provider", _Model(), raising=False)
    from src.services import agent_tools

    async def _ctx(*a, **k):
        return ""

    monkeypatch.setattr(agent_tools, "run_context", _ctx)


async def _run(maker, monkeypatch, send):
    from src.services import email_service

    monkeypatch.setattr(email_service, "send_email", send)
    _fake_runtime(monkeypatch)
    project = await _project(maker, status="active", email="buyer@shop.sa")
    async with maker() as s:
        s.add(ClientAgent(project_id=project.id, slug="customer_service", status="awake"))
        await s.commit()
    async with _client(maker, project=project) as c:
        r = await c.post(f"/api/portal/projects/{project.id}/agents/customer_service/run", json={"answers": {}})
    async with maker() as s:
        agent = (await s.execute(select(ClientAgent).where(ClientAgent.project_id == project.id))).scalar_one()
    return r, agent


async def test_run_emails_the_result(maker, monkeypatch):
    sent = []

    async def send(to, subject, body, *a, **k):
        sent.append((to, body))
        return True

    r, agent = await _run(maker, monkeypatch, send)
    assert r.status_code == 200, r.text
    assert r.json()["emailed"] is True and r.json()["emailed_to"] == "buyer@shop.sa"
    assert sent == [("buyer@shop.sa", "RESULT")]
    assert agent.result_emailed_at is not None


@pytest.mark.parametrize("mode", ["false", "raises"])
async def test_email_failure_does_not_break_the_run_or_claim_delivery(maker, monkeypatch, mode):
    async def send(*a, **k):
        if mode == "raises":
            raise RuntimeError("smtp down")
        return False

    r, agent = await _run(maker, monkeypatch, send)
    assert r.status_code == 200, r.text
    assert r.json()["result"] == "RESULT"
    assert r.json()["emailed"] is False and r.json()["emailed_to"] is None
    assert agent.result_emailed_at is None


def test_portal_only_claims_email_when_sent():
    html = (ROOT / "src/web/templates/portal.html").read_text(encoding="utf-8")
    assert "data.emailed === true" in html


# --- 4. no API docs in production ---------------------------------------------

def test_docs_are_disabled_in_production():
    code = (
        "from fastapi.testclient import TestClient\n"
        "from src.main import app\n"
        "c = TestClient(app)\n"
        "print([c.get(p).status_code for p in ('/docs', '/redoc', '/openapi.json')])\n"
    )
    env = {**os.environ, "ENVIRONMENT": "production"}
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip().splitlines()[-1] == "[404, 404, 404]"


def test_docs_stay_available_outside_production():
    from fastapi.testclient import TestClient
    from src.main import app

    assert TestClient(app).get("/openapi.json").status_code == 200


# --- addendum: currency, refusal side effects, run idempotency, contact ------

@pytest.mark.parametrize("currency,ok", [("SAR", True), ("sar", True), ("USD", False), ("", False)])
async def test_activation_requires_sar(maker, currency, ok):
    project = await _project(maker, package="numuw")
    pay = await _paid(maker, project, "numuw")
    async with maker() as s:
        p = await s.get(Payment, pay.id)
        p.currency = currency
        await s.commit()
    async with maker() as s:
        out = await pm.activate_subscription(s, await s.get(Payment, pay.id))
    assert out["activated"] is ok
    async with maker() as s:
        assert (await s.get(ClientProject, project.id)).status == ("active" if ok else "pending")
        if not ok:
            assert out.get("review") is True and "currency" in out["reason"]
            assert (await s.get(Payment, pay.id)).status == pm.REVIEW_STATUS


async def _lead_payment(maker, currency):
    from src.models import AcquisitionLead

    project = await _project(maker, package="numuw")
    pay = await _paid(maker, project, "numuw")
    async with maker() as s:
        lead = AcquisitionLead(company_name="L")
        s.add(lead)
        await s.flush()
        p = await s.get(Payment, pay.id)
        p.lead_id, p.currency = lead.id, currency
        await s.commit()
        return project, pay, lead.id


@pytest.mark.parametrize("currency,activated", [("SAR", True), ("USD", False)])
async def test_lead_won_and_success_log_only_after_activation(maker, currency, activated):
    from src import main
    from src.models import AcquisitionLead, Decision

    project, pay, lead_id = await _lead_payment(maker, currency)
    async with maker() as s:
        out = await main._apply_paid_outcome(s, pay.id)
    assert out["activated"] is activated
    async with maker() as s:
        lead = await s.get(AcquisitionLead, lead_id)
        dec = (await s.execute(select(Decision).where(Decision.reason == f"payment_ref:{pay.id}"))).scalars().all()
    assert len(dec) == 1
    if activated:
        assert lead.lead_status == "WON" and dec[0].status == "resolved"
    else:
        assert lead.lead_status != "WON"
        assert dec[0].status == "review" and dec[0].actual == "review"


async def _keyed_runs(maker, monkeypatch, keys, header=True):
    from src.services import email_service

    sent = []

    async def send(to, subject, body, *a, **k):
        sent.append(to)
        return True

    monkeypatch.setattr(email_service, "send_email", send)
    _fake_runtime(monkeypatch)
    project = await _project(maker, status="active", email="buyer@shop.sa")
    async with maker() as s:
        s.add(ClientAgent(project_id=project.id, slug="customer_service", status="awake"))
        await s.commit()
    out = []
    async with _client(maker, project=project) as c:
        for k in keys:
            url = f"/api/portal/projects/{project.id}/agents/customer_service/run"
            if header:
                r = await c.post(url, json={"answers": {}}, headers={"Idempotency-Key": k})
            else:
                r = await c.post(url, json={"answers": {}, "run_id": k})
            assert r.status_code == 200, r.text
            out.append(r.json())
    return out, sent


@pytest.mark.parametrize("header", [True, False])
async def test_same_run_key_does_not_rerun_or_resend(maker, monkeypatch, header):
    out, sent = await _keyed_runs(maker, monkeypatch, ["k1", "k1"], header=header)
    assert sent == ["buyer@shop.sa"]
    assert out[1]["result"] == out[0]["result"] and out[1].get("replayed") is True


async def test_new_run_key_still_runs(maker, monkeypatch):
    out, sent = await _keyed_runs(maker, monkeypatch, ["k1", "k2"])
    assert len(sent) == 2 and not out[1].get("replayed")


def test_portal_js_sends_a_run_key_and_disables_while_running():
    html = pathlib.Path("src/web/templates/portal.html").read_text(encoding="utf-8")
    assert "'Idempotency-Key': runKey" in html and "setRunBusy(true)" in html
    assert "if (state.running) return;" in html


_PHONE = __import__("re").compile(r"(?:\+?966|\b0)5\d{8}\b|05\d{2}\s?\d{3}\s?\d{3}")
_EMAIL = __import__("re").compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def test_kb_and_grounding_have_no_phone_or_email():
    import inspect

    from src import main

    kb = pathlib.Path("data/kb/narjs_services.md").read_text(encoding="utf-8")
    src = inspect.getsource(main._consult_grounded)
    for text in (kb, src, pathlib.Path("content/contact.json").read_text(encoding="utf-8")):
        assert not _PHONE.search(text) and not _EMAIL.search(text)
    assert "SUPPORT_EMAIL" not in src


def test_grounding_facts_do_not_contain_support_email(monkeypatch):
    from src import main
    from src.services.rag import generate
    from src.services.support import SUPPORT_EMAIL

    seen = {}

    def fake(reply, hits, extra_facts=""):
        seen["facts"] = extra_facts
        return True

    monkeypatch.setattr(generate, "grounded", fake)
    main._consult_grounded("x", [], "pkgs")
    assert SUPPORT_EMAIL not in seen["facts"] and not _PHONE.search(seen["facts"])
