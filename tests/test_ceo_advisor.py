"""CEO advisor: deterministic diagnosis, real agents, honest plan and price."""
from __future__ import annotations

import pytest

from src.services import catalog, ceo_advisor, payments


def test_tiers_are_the_owner_prices_in_halalas():
    assert {k: p["amount"] for k, p in catalog.PACKAGES.items()} == {
        "bidaya": 79000, "numuw": 149000, "sharikat": 299000,
    }
    for p in catalog.PACKAGES.values():
        assert p["amount"] == int(p["price"]) * 100


def test_tier_allowances_follow_the_feasibility_ladder():
    counts = [catalog.plan_agent_count(k) for k in catalog.PACKAGE_ORDER]
    assert counts == [5, 15, 34]
    assert catalog.PACKAGES["sharikat"]["display_agents"] == 35
    for key in catalog.PACKAGE_ORDER:
        team = catalog.PACKAGE_TEAMS[key]
        assert team[0] == catalog.CEO_SLUG
        assert len(team) - 1 == catalog.plan_agent_count(key)  # the CEO leads on top
        assert set(team) <= set(catalog.EMPLOYEES)


@pytest.mark.parametrize("n,expected", [(1, "bidaya"), (5, "bidaya"), (6, "numuw"), (15, "numuw"), (16, "sharikat"), (34, "sharikat"), (40, "sharikat")])
def test_plan_is_the_smallest_tier_that_covers_the_team(n, expected):
    assert ceo_advisor.recommend_plan(n) == expected


def test_full_company_request_wins():
    assert ceo_advisor.recommend_plan(1, full_company=True) == "sharikat"
    d = ceo_advisor.diagnose_rules("أريد شركة كاملة تدير كل شيء")
    assert ceo_advisor.build_result(d)["plan"]["key"] == "sharikat"


def test_store_and_support_problem_staffs_real_agents():
    d = ceo_advisor.diagnose_rules("متجري على سلة مبيعاته ضعيفة والعملاء ينتظرون الرد على الواتساب")
    assert "store_manager" in d.agents and "customer_service" in d.agents
    assert catalog.CEO_SLUG not in d.agents
    assert set(d.agents) <= set(catalog.EMPLOYEES)


def test_a_single_need_gets_a_small_team_and_vague_text_gets_one_agent():
    assert ceo_advisor.diagnose_rules("تسعير خدماتي غير واضح وهامش الربح ضعيف").agents == ["finance_pricing"]
    vague = ceo_advisor.build_result(ceo_advisor.diagnose_rules("أحتاج مساعدة في عملي"))
    assert vague["agent_count"] == 1 and vague["plan"]["key"] == "bidaya"


@pytest.mark.usefixtures("vat15")
def test_result_price_matches_the_payment_vat_logic():
    r = ceo_advisor.build_result(ceo_advisor.diagnose_rules("Instagram engagement is weak"))
    plan = r["plan"]
    base = catalog.plan_amount(plan["key"], "monthly", plan["addons"])
    assert plan["base_halalas"] == base
    assert plan["vat_halalas"] == payments.vat_amount(base)
    assert plan["total_halalas"] == payments.total_with_vat(base) == round(base * 1.15)
    assert r["cta"]["subscribe"].startswith(f"/portal?pkg={plan['key']}")
    assert r["cta"]["telegram"] == ""
    assert r["cta"]["whatsapp"] == ""


class _BadProvider:
    _clients = {"gemini": object()}

    async def complete_with_fallback(self, *_a, **_k):
        raise RuntimeError("provider down")


class _Resp:
    def __init__(self, content):
        self.content = content


class _GoodProvider:
    _clients = {"gemini": object()}

    async def complete_with_fallback(self, *_a, **_k):
        return _Resp('{"diagnosis_ar": "تشخيص", "diagnosis_en": "dx", "agents": ["data_analyst", "invented_agent", "orchestrator"]}')


async def test_model_failure_falls_back_to_rules():
    r = await ceo_advisor.diagnose("متجري على سلة ضعيف", provider=_BadProvider())
    assert r["source"] == "rules" and r["agents"]


async def test_model_output_is_validated_against_the_catalog():
    r = await ceo_advisor.diagnose("نحتاج تقارير", provider=_GoodProvider())
    assert r["source"] == "llm"
    assert [a["slug"] for a in r["agents"]] == ["data_analyst"]
    assert r["plan"]["key"] == "bidaya"


async def test_no_cloud_key_means_rules_only():
    class _OllamaOnly:
        _clients = {"ollama": object()}

        async def complete_with_fallback(self, *_a, **_k):  # pragma: no cover
            raise AssertionError("must not be called")

    r = await ceo_advisor.diagnose("حساب انستقرام ضعيف", provider=_OllamaOnly())
    assert r["source"] == "rules"


async def test_endpoint_returns_the_recommendation():
    from httpx import ASGITransport, AsyncClient
    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/ceo/consult", json={"problem": "متجري على سلة والعملاء ينتظرون الرد"})
        assert r.status_code == 200
        body = r.json()
        assert body["plan"]["key"] in catalog.PACKAGES and body["agents"]
        short = await c.post("/api/ceo/consult", json={"problem": "hi"})
        assert short.status_code == 400


def test_contact_channels_are_phone_and_email_only():
    from src.services import transfer

    channels = transfer.contact_channels("مرحبا")
    assert channels["messenger"] == ""
    assert channels["telegram"] == ""
    assert channels["whatsapp"] == ""
    assert channels["phone"] == "tel:+966540799266"
    assert channels["phone_display"] == "0540799266"
    assert channels["email"] == "mailto:AlNarjisai@gmail.com"
