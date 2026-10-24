"""Deterministic public-output check on /api/ceo/consult, built from the failing
launch probes (#3, #6, #9, #10, #12 in launch-final/B-raw.json)."""
import json
from types import SimpleNamespace

import pytest

from src.services import ceo_advisor as ca
from src.services import payments as pm

LEAK = ("محمد", "Mohammed", "تصعيد", "escalat", "ZATCA", "الزكاة", "فاتورة ضريبية رسمية", "policy_guardian")


class FakeProvider:
    """Replays the model output captured in the live probe."""

    def __init__(self, payload):
        self.payload = payload
        self.default_provider = "gemini"
        self.gemini_api_key = "x"

    async def complete_with_fallback(self, _name, _req):
        return SimpleNamespace(content=json.dumps(self.payload, ensure_ascii=False))


async def _run(problem, payload=None, monkeypatch=None):
    provider = None
    if payload is not None:
        provider = FakeProvider(payload)
        monkeypatch.setattr(ca, "_has_cloud_model", lambda _p: True)
    return await ca.diagnose(problem, provider=provider)


def _assert_no_sale(r):
    assert r["offer"] is False
    assert r["agents"] == [] and r["agent_count"] == 0
    assert r["cta"]["subscribe"] == ""


async def test_probe3_flight_booking_gets_no_sales_offer():
    r = await _run("ممكن تحجزون لي فندق ورحلة طيران لإسطنبول الشهر الجاي؟")
    _assert_no_sale(r)
    assert "خارج ما نقدمه" in r["diagnosis_ar"]


async def test_probe6_angry_refund_hides_escalation_and_sales(monkeypatch):
    payload = {
        "agents": ["policy_guardian"],
        "diagnosis_ar": "العميل يطالب باسترداد المبلغ كاملاً. يتطلب الأمر تصعيد الطلب فوراً إلى محمد.",
        "diagnosis_en": "This requires immediate escalation to Mohammed.",
    }
    r = await _run("دفعت لكم وصار لي أسبوعين والوكيل ما اشتغل! أبي فلوسي كاملة الحين وإلا بشتكي", payload, monkeypatch)
    _assert_no_sale(r)
    text = r["diagnosis_ar"] + r["diagnosis_en"]
    for bad in LEAK:
        assert bad not in text
    assert "رسوم الإعداد" in r["diagnosis_ar"] and "10 أيام عمل" in r["diagnosis_ar"]


async def test_probe9_price_question_gets_closed_notice_and_real_prices(monkeypatch):
    payload = {"agents": ["finance_pricing"], "diagnosis_ar": "العميل يستفسر عن الأسعار.", "diagnosis_en": "Asking prices."}
    r = await _run("كم أسعار باقاتكم؟ وفيه رسوم تأسيس؟ وإذا دفعت سنوي فيه خصم؟", payload, monkeypatch)
    _assert_no_sale(r)
    assert r["diagnosis_ar"].startswith(pm.PAYMENTS_CLOSED_AR)
    for fact in ("790", "1,490", "2,990", "990", "1,990", "10 أشهر", "12"):
        assert fact in r["diagnosis_ar"]


async def test_probe10_vat_question_gets_no_tax_invoice_promise(monkeypatch):
    payload = {
        "agents": ["finance_pricing"],
        "diagnosis_ar": "الاستفسار يتعلق بإصدار الفواتير الرسمية وفقاً لأنظمة هيئة الزكاة والضريبة والجمارك (ZATCA).",
        "diagnosis_en": "Issuing official tax invoices in accordance with ZATCA regulations.",
    }
    r = await _run("Do your prices include 15% VAT and will I get a tax invoice with your VAT number?", payload, monkeypatch)
    _assert_no_sale(r)
    assert "ZATCA" not in r["diagnosis_en"]
    assert "do not issue tax invoices" in r["diagnosis_en"]
    assert "لا نصدر فواتير ضريبية" in r["diagnosis_ar"]


async def test_probe12_pay_now_gets_closed_notice_and_no_cta():
    r = await _run("I want to pay by credit card right now for the Growth plan. Send me the payment link.")
    _assert_no_sale(r)
    assert r["diagnosis_en"].startswith(pm.PAYMENTS_CLOSED_EN)


async def test_pay_now_gets_normal_offer_once_payments_open(monkeypatch):
    monkeypatch.setattr(pm, "payments_open", lambda: True)
    r = await _run("I want to pay by credit card right now for the Growth plan. Send me the payment link.")
    assert r["offer"] is True and r["cta"]["subscribe"]


@pytest.mark.parametrize("problem", [
    "عندي فندق صغير في أبها وأبي وكيل يرد على أسئلة الحجوزات في الواتساب",
    "عندي متجر عبايات على زد والطلبات كثيرة، أبي وكيل يرد على أسئلة العملاء عن المقاسات والشحن",
    "عملائي يشتكون من تأخر الردود على الإنستقرام",
    "I run a clinic and patients complain we reply slowly on Instagram",
])
async def test_real_business_problems_still_get_a_team(problem):
    r = await _run(problem)
    assert r["offer"] is True
    assert r["agents"] and r["cta"]["subscribe"].startswith("/portal")


async def test_leaky_llm_summary_is_replaced_for_normal_problem(monkeypatch):
    payload = {"agents": ["customer_service"], "diagnosis_ar": "نحتاج موافقة المالك قبل التنفيذ.",
               "diagnosis_en": "Needs owner approval before execution."}
    r = await _run("عندي متجر عبايات وأبي وكيل يرد على أسئلة العملاء", payload, monkeypatch)
    assert "المالك" not in r["diagnosis_ar"] and "owner" not in r["diagnosis_en"]


async def test_api_route_applies_the_check():
    import httpx
    from src.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post("/api/ceo/consult", json={"problem": "ممكن تحجزون لي فندق ورحلة طيران لإسطنبول؟", "lang": "ar"})
    assert res.status_code == 200
    assert res.json()["offer"] is False
