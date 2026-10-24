"""The site assistant's instructions and KB say payment is not open yet while it is closed."""
from pathlib import Path

from src.core import karma_persona
from src.services import payments as pm

KB = Path(__file__).resolve().parents[1] / "data" / "kb" / "narjs_services.md"
FORBIDDEN = ("فعّل باقتك فوراً", "pay by card via Moyasar", "Moyasar", "ميسر", "ميسّر")


def _prompt(locale):
    return karma_persona.build_consult_system_prompt(locale=locale, packages_text="P", employees_text="E")


def test_consult_instructions_say_payment_closed_while_flag_on():
    assert not pm.payments_open()
    for locale in ("ar", "en"):
        prompt = _prompt(locale)
        assert "الدفع الإلكتروني قيد التفعيل حالياً" in prompt
        assert "register their interest" in prompt
        assert "pay by card on the secure checkout" not in prompt


def test_consult_instructions_switch_when_payment_opens(monkeypatch):
    monkeypatch.setattr(pm, "payments_open", lambda: True)
    prompt = _prompt("ar")
    assert "قيد التفعيل" not in prompt
    assert "secure checkout page" in prompt


def test_refund_fact_is_setup_fee_only():
    prompt = _prompt("ar")
    assert "ONLY refund is the one-time setup fee" in prompt
    assert "10 business days" in prompt


def test_kb_states_payments_closed_and_correct_refund():
    text = KB.read_text(encoding="utf-8")
    assert "الدفع الإلكتروني قيد التفعيل حالياً" in text
    assert "سجّل اهتمامك عبر مساعد النرجس" in text
    for bad in FORBIDDEN:
        assert bad not in text, bad
    refund = text[text.index("### س37"):text.index("### س38")]
    assert "رسوم الإعداد لمرة واحدة فقط" in refund and "10 أيام عمل" in refund
    assert "الزهراني" not in refund
    assert "الخدمة تبدأ فوراً" not in refund
    for bad in ("الأحد إلى الخميس", "Sun–Thu", "Sun-Thu"):
        assert bad not in text
