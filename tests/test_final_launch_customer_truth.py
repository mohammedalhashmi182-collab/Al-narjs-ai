"""Final launch truth regressions.

These pin the owner-approved customer-facing facts. A regression here is a
release blocker even when the application still returns HTTP 200.
"""
from pathlib import Path

from src.ai import router
from src.core import karma_persona
from src.services import ceo_advisor, payments

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "src" / "web" / "templates"
KB = ROOT / "data" / "kb" / "narjs_services.md"


def test_moyasar_hold_is_visible_before_customer_enters_details():
    assert payments.MOYASAR_ON_HOLD is True
    portal = (TPL / "portal.html").read_text(encoding="utf-8")
    pricing = (TPL / "pricing.html").read_text(encoding="utf-8")
    landing = (TPL / "landing.html").read_text(encoding="utf-8")
    for text in (portal, pricing, landing):
        assert "payments_pending" in text
    assert "الدفع بالبطاقة قيد التفعيل" in portal
    assert "Card payments are pending activation" in portal


def test_public_kb_states_payment_hold_and_store_integrations_truthfully():
    text = KB.read_text(encoding="utf-8")
    assert "الدفع بالبطاقة عبر ميسر قيد التفعيل" in text
    assert "لا يمكن إكمال دفعة حالياً" in text
    assert "سلة أو زد «قريباً»" in text
    assert "يحدده أحمد" not in text
    assert "يحدده محمد" not in text


def test_public_ai_prompts_never_name_internal_people_for_handoff():
    assert "يحدده محمد" not in router.SYSTEM_AR
    prompt = karma_persona.build_consult_system_prompt(
        locale="ar", packages_text="البداية 790", employees_text="وكيل تسويق"
    )
    assert "صعّد الطلب إلى محمد" not in prompt
    assert "payment is pending" in prompt.lower() or "الدفع" in prompt


def test_phone_support_negation_is_not_flipped():
    text = "لا يوجد دعم هاتفي. التواصل العام عبر مساعد النرجس فقط."
    out = karma_persona.enforce_reply_policy(text, locale="ar")
    assert "لا يوجد دعم هاتفي" in out
    assert "الدعم عبر الموقع والبريد" not in out


def test_ceo_does_not_sell_an_out_of_scope_travel_booking():
    assert ceo_advisor.is_out_of_scope("أريدك تحجز لي تذكرة طيران إلى دبي")
    assert ceo_advisor.is_out_of_scope("Book me a flight to London")
    assert not ceo_advisor.is_out_of_scope("أريد أتمتة الردود في مكتب سفر")


def test_related_agent_links_keep_current_language():
    text = (TPL / "agent_public.html").read_text(encoding="utf-8")
    assert 'href="/{{ _lang }}/ai-agent/{{ rel.slug }}"' in text


def test_english_guide_is_actually_english():
    text = (TPL / "guide.html").read_text(encoding="utf-8")
    assert "{% set _lang = page_lang(request) %}" in text
    assert "30-Day AI Plan" in text
    assert "Download the free guide" in text


def test_terms_cover_monthly_and_annual_billing():
    text = (TPL / "terms.html").read_text(encoding="utf-8")
    assert "شهرية أو سنوية" in text
    assert "monthly or annual" in text
