"""The site assistant's instructions and KB say payment is not open yet while it is closed."""

from pathlib import Path

from src.core import karma_persona
from src.services import payments as pm

KB = Path(__file__).resolve().parents[1] / "data" / "kb" / "narjs_services.md"
FORBIDDEN = ("فعّل باقتك فوراً", "pay by card via Moyasar", "Moyasar", "ميسر", "ميسّر")


def _prompt(locale):
    return karma_persona.build_consult_system_prompt(
        locale=locale, packages_text="P", employees_text="E"
    )


def test_consult_instructions_name_bank_transfer_when_the_account_is_published():
    assert pm.payments_open() is False
    assert pm.capabilities()["card"] is False
    assert pm.customer_bank_transfer_enabled() is False
    for locale in ("ar", "en"):
        prompt = _prompt(locale)
        assert "bank transfer against the invoice" not in prompt
        assert "قيد التفعيل" in prompt


def test_consult_instructions_say_payment_closed_without_an_account(monkeypatch):
    monkeypatch.setattr(pm, "customer_bank_transfer_enabled", lambda: False)
    monkeypatch.setattr(pm, "paypal_checkout_open", lambda: False)
    assert not pm.payments_open()
    prompt = _prompt("en")
    assert "الدفع الإلكتروني قيد التفعيل حالياً" in prompt
    assert "register their interest" in prompt


def test_consult_instructions_switch_when_payment_opens(monkeypatch):
    monkeypatch.setattr(pm, "paypal_checkout_open", lambda: True)
    monkeypatch.setattr(pm, "customer_bank_transfer_enabled", lambda: False)
    prompt = _prompt("ar")
    assert "قيد التفعيل" not in prompt
    assert "PayPal" in prompt
    assert "Never ask for card" in prompt


def test_refund_fact_is_setup_fee_only():
    prompt = _prompt("ar")
    assert "do not promise a refund outcome" in prompt
    assert "AlNarjisai@gmail.com" in prompt


def test_kb_states_bank_transfer_and_correct_refund():
    text = KB.read_text(encoding="utf-8")
    assert "تحويل بنكي من صفحة الدفع" not in text
    assert "لا نطلب تحويلاً بنكياً" in text
    assert "AlNarjisai@gmail.com" in text
    for bad in FORBIDDEN:
        assert bad not in text, bad
    refund = text[text.index("### س37") : text.index("### س38")]
    assert "لا نعد هنا بنتيجة استرداد" in refund and "AlNarjisai@gmail.com" in refund
    assert "الزهراني" not in refund
    assert "الخدمة تبدأ فوراً" not in refund
    for bad in ("الأحد إلى الخميس", "Sun–Thu", "Sun-Thu"):
        assert bad not in text
