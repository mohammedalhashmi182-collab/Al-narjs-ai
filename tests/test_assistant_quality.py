"""Assistant quality fixes from the live agents test (24 Oct 2026).

One test (or more) per fix: tax/setup facts, no phone
support, no contact-detail requests, no invented integrations, less
over-refusal, CEO plan coverage, clinic demo answers, consult model override.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.karma_persona import build_consult_system_prompt, enforce_reply_policy
from src.main import _consult_grounded, _consult_model_metadata, _consult_scope_line, _consult_visitor_numbers, app
from src.services import catalog, ceo_advisor, live_demo

# tax + setup facts; no phone support ---------------------------------------------------------
def _prompt(locale="ar"):
    return build_consult_system_prompt(locale=locale, packages_text="P", employees_text="E")


def test_prompt_states_tax_and_setup_facts():
    p = _prompt()
    assert "NOT VAT-registered" in p and "NO VAT" in p and "tax invoices" in p
    assert "ONE-TIME" in p and "NO annual waiver" in p and "WAIVED" not in p and "not part of the monthly" in p


def test_wrong_vat_claim_is_replaced():
    out = enforce_reply_policy("- جميع الأسعار شاملة لضريبة القيمة المضافة مع إصدار فواتير رسمية\n- باقة النمو 1,490")
    assert "شاملة" not in out and "بدون ضريبة" in out and "1,490" in out


def test_never_claims_phone_support():
    assert "NO phone support" in _prompt()
    for s in ("دعم فني عبر البريد والهاتف", "ودعم عبر البريد والهاتف", "دعم بالبريد الإلكتروني والهاتف"):
        out = enforce_reply_policy(s)
        assert "الهاتف" not in out and "البريد الإلكتروني" in out, out
    assert "phone" not in enforce_reply_policy("We offer email and phone support.", locale="en").lower()
    # Catalog no longer claims phone support (owner-approved 24 Oct 2026); the guard stays.
    assert not any("phone" in x.lower() for p in catalog.PACKAGES.values() for x in p["scope_en"])
    assert "no phone support" in _consult_scope_line("Email and phone support")


# 3) never ask for visitor email/phone --------------------------------------------------------
@pytest.mark.parametrize("ask", [
    "ما هو بريدك الإلكتروني أو رقم هاتفك المفضل؟",
    "هل تفضل أن نرسل لك على بريدك الإلكتروني أم على رقم هاتفك؟",
    "شاركني رقم جوالك ونتواصل معك",
])
def test_contact_requests_become_handoff_button(ask):
    out = enforce_reply_policy("خطة مقترحة.\n" + ask)
    assert "بريدك" not in out and "رقم" not in out and "«اطلب تواصل موظف»" in out
    assert "Never ask for their email" in _prompt()


# 4) no invented integrations -----------------------------------------------------------------
def test_invented_integrations_removed_unless_in_sources():
    reply = "نقوم بربط أنظمة عيادات الأسنان (مثل ساري)\nربط Zapier/Make\nتكامل مع زووم\nخطة واضحة"
    out = enforce_reply_policy(reply)
    for name in ("ساري", "Zapier", "زووم"):
        assert name not in out
    assert "خطة واضحة" in out and "غير مؤكد" in out
    assert "Zapier" in enforce_reply_policy("ربط Zapier", sources="ندعم Zapier")
    assert "Zapier" not in _prompt().split("SERVICES PILLARS")[1].split("REAL PRODUCT")[0].replace(
        "Never name a third-party system (for example Sari, Zapier, Make, Zoom", "")


# 5) less over-refusal, grounded in catalog ---------------------------------------------------
def test_plan_question_with_visitor_numbers_is_grounded():
    history = [{"role": "user", "content": "عندي 50 رسالة يومياً، أي باقة؟"}]
    reply = "50 رسالة يومياً تعني نحو 1,500 محادثة شهرياً، فباقة النمو 1,490 ريال مناسبة. 3 خطوات للبدء."
    assert _consult_grounded(reply, [], "النمو: 1490 SAR, 1,000 conversations", _consult_visitor_numbers(history))
    assert not _consult_grounded("السعر 1,250 ريال", [], "1490", _consult_visitor_numbers(history))


def test_consult_endpoint_answers_plan_question_and_cleans_reply(monkeypatch):
    class _R:
        content = ("### الباقة المناسبة\n- **النمو** 1,490 ريال\n- دعم فني عبر البريد والهاتف\n"
                   "ما هو بريدك الإلكتروني أو رقم هاتفك المفضل؟")

    class _M:
        req = None

        async def complete_with_fallback(self, chain, request):
            _M.req = request
            return _R()

    from src.utils import rate_limit
    if hasattr(rate_limit.consult_limiter, "_hits"):
        rate_limit.consult_limiter._hits.clear()
    with TestClient(app) as c:
        monkeypatch.setattr(app.state, "model_provider", _M())
        r = c.post("/api/consult", json={"messages": [{"role": "user", "content": "أي باقة لـ50 رسالة يومياً؟"}]})
    body = r.json()
    assert r.status_code == 200 and "handoff" not in body, body
    assert "1,490" in body["reply"] and "الهاتف" not in body["reply"] and "بريدك" not in body["reply"]
    sp = _M.req.system_prompt
    assert "Email and phone support" not in sp and "Email support" in sp
    assert "one-time setup fee of 990 SAR" in sp and "charged on monthly and annual billing alike" in sp and "waived" not in sp.lower()
    assert "790" in sp and "1490" in sp and "2990" in sp


# 6) CEO plan really includes the agents ------------------------------------------------------
def test_ceo_plan_covers_recommended_agents():
    agents = ["store_manager", "customer_service", "data_analyst"]
    plan, addons = ceo_advisor.recommend_offer(len(agents), agents=agents)
    team = set(catalog.PACKAGE_TEAMS[plan])
    missing = [a for a in agents if a not in team]
    assert plan != "bidaya" and len(missing) <= addons
    starter = catalog.PACKAGE_TEAMS["bidaya"][1:4]
    assert ceo_advisor.recommend_offer(3, agents=starter) == ("bidaya", 0)


def test_ceo_build_result_uses_agent_coverage():
    d = ceo_advisor.Diagnosis(needs=[], agents=["store_manager", "customer_service", "data_analyst"], full_company=False)
    res = ceo_advisor.build_result(d)
    assert res["plan"]["key"] != "bidaya"


# 7) clinic demo answers ----------------------------------------------------------------------
@pytest.fixture
async def maker():
    from src.db.session import Base
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_demo_answers_from_kb_when_retrieval_hands_off(maker, monkeypatch):
    from src.services import tenant_reply

    async def _give_up(*a, **k):
        return None, "no_answer"

    monkeypatch.setattr(tenant_reply, "_rag_reply", _give_up)
    live_demo.reset_limits()
    async with maker() as s:
        r1 = await live_demo.chat(s, "t", "متى أوقات الدوام؟")
        r2 = await live_demo.chat(s, "t", "كم سعر التبييض؟")
        r3 = await live_demo.chat(s, "t", "مرحبا")
        r4 = await live_demo.chat(s, "t", "أبي أكلم موظف")
    assert "الأحد" in r1["reply"] and r1["kind"] == "kb_reply"
    assert "900" in r2["reply"]
    assert r3["kind"] == "menu" and "أوقات الدوام" in r3["reply"]
    assert r4["kind"] == "handoff"


# 8) Arabic quality: proofreading + optional stronger consult model ---------------------------
def test_consult_model_override_is_optional_and_validated(monkeypatch):
    assert "proofread" in _prompt()
    monkeypatch.delenv("CONSULT_GEMINI_MODEL", raising=False)
    assert _consult_model_metadata() == {}
    monkeypatch.setenv("CONSULT_GEMINI_MODEL", "gemini-pro-latest")
    assert _consult_model_metadata() == {"gemini_model_override": "gemini-pro-latest"}
    monkeypatch.setenv("CONSULT_GEMINI_MODEL", "bad model; rm")
    assert _consult_model_metadata() == {}


def test_plans_make_no_phone_or_official_invoice_claim():
    """Owner decision 24 Oct 2026: no phone support, no 'official'/tax invoices (not VAT-registered)."""
    bad_ar = ("هاتف", "رسمية", "ضريبية")
    bad_en = ("phone", "official invoice", "tax invoice")
    for key, p in catalog.PACKAGES.items():
        ar = " ".join([p.get("tagline", "")] + p.get("scope", []) + p.get("coming", []))
        en = " ".join([p.get("tagline_en", "")] + p.get("scope_en", []) + p.get("coming_en", [])).lower()
        assert not any(b in ar for b in bad_ar), (key, ar)
        assert not any(b in en for b in bad_en), (key, en)
        assert "دعم بالبريد الإلكتروني" in p["scope"] and "Email support" in p["scope_en"], key
