"""Pre-Moyasar public fixes: closed payment copy, email handoff, catalog counts.

Payment capture stays on hold. These tests pin the visitor-facing corrections
from the read-only audit against main 45798c5.
"""
from pathlib import Path

from src.services import catalog, ceo_advisor, payments

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "src" / "web" / "templates"


def test_moyasar_stays_on_hold():
    assert payments.MOYASAR_ON_HOLD is True
    assert payments.payments_open() is False


def test_refund_reply_names_email_and_duplicate_charges():
    result = ceo_advisor.public_output_check(
        {"agents": [{"slug": "marketing_agent"}], "agent_count": 1, "cta": {}},
        "أبي فلوسي",
    )
    assert result["offer"] is False
    assert "AlNarjisai@gmail.com" in result["diagnosis_ar"]
    assert "لا نعد هنا بنتيجة استرداد" in result["diagnosis_ar"]
    assert "اطلب تواصل" not in result["diagnosis_ar"]


def test_non_public_agents_are_removed_even_when_they_are_the_only_match():
    result = ceo_advisor.public_output_check(
        {
            "offer": True,
            "agents": [{"slug": "finance_pricing", "title_ar": "تسعير"}],
            "agent_count": 1,
            "diagnosis_ar": "وصف تجاري واضح.",
            "diagnosis_en": "A clear commercial description.",
            "cta": {"subscribe": "/portal?pkg=bidaya"},
        },
        "عندي متجر وأبي محتوى يومي للعملاء",
    )
    assert result["agents"] == []
    assert result["agent_count"] == 0


def test_landing_does_not_claim_card_payments_while_closed():
    html = (TPL / "landing.html").read_text(encoding="utf-8")
    assert '"paymentAccepted": "Moyasar"' not in html
    assert "payments_open()" in html
    assert "الدفع الإلكتروني قيد التفعيل حالياً" in html
    assert "بوابة ميسر" not in html
    assert "نهاية الفترة المدفوعة" in html
    assert "/ai-agent/" in html
    assert "mailto:AlNarjisai@gmail.com" in html


def test_cancel_copy_closes_the_team_at_period_end():
    terms = (TPL / "terms.html").read_text(encoding="utf-8")
    refund = (TPL / "refund_policy.html").read_text(encoding="utf-8")
    assert "نهاية الفترة المدفوعة" in terms
    assert "وتتحول الاشتراكات الملغاة إلى إغلاق الفريق" not in terms
    assert "The team closes then." in refund
    assert "Cancelled subscriptions close the team." not in refund


def test_public_agent_count_comes_from_the_catalog():
    landing = (ROOT / "src" / "main.py").read_text(encoding="utf-8")
    home = landing.split("async def landing_page", 1)[1].split("async def public_pulse", 1)[0]
    early = landing.split("async def early_access_page", 1)[1].split("@app.get", 1)[0]
    assert "catalog.AGENT_COUNT" in home and "list_agents" not in home
    assert "catalog.AGENT_COUNT" in early and "list_agents" not in early
    assert catalog.AGENT_COUNT == len(catalog.EMPLOYEES)


def test_owner_surfaces_label_raw_keys():
    owner = (TPL / "owner_command.html").read_text(encoding="utf-8")
    dash = (TPL / "dashboard.html").read_text(encoding="utf-8")
    portal = (TPL / "portal.html").read_text(encoding="utf-8")
    assert "moyasar:'ميسر'" in owner and "lbl(r.plan)" in owner and "lbl(t.status)" in owner
    assert "OC_LABELS" in dash and "ocLabel(p.status)" in dash
    assert "'المنتجات والهندسة': 'Product & Engineering'" in portal
    assert "sharikat: 'Enterprise'" in portal


def test_card_errors_do_not_echo_the_gateway_body():
    src = (ROOT / "src" / "main.py").read_text(encoding="utf-8")
    block = src.split("async def pay_invoice_by_card", 1)[1].split("@app.get", 1)[0]
    assert "card payment unavailable: {str(e)" not in block
    assert 'HTTPException(502, "card payment unavailable")' in block
    assert "use bank transfer" not in block
    assert "email AlNarjisai@gmail.com" in block


def test_default_seller_address_is_empty():
    from src.config.settings import Settings

    field = Settings.model_fields["seller_address_ar"]
    assert field.default == ""
