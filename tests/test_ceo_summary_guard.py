"""CEO model summaries must not leak internal escalation notes or come back in the wrong language."""

from src.services.ceo_advisor import _safe_summary


def test_internal_escalation_is_replaced():
    assert _safe_summary("يتطلب الأمر تصعيد الطلب فوراً إلى محمد", "بديل", arabic=True) == "بديل"


def test_english_text_in_arabic_field_is_replaced():
    assert _safe_summary("Your clinic needs booking automation", "بديل", arabic=True) == "بديل"


def test_clean_arabic_summary_is_kept():
    assert (
        _safe_summary("متجرك يحتاج رد آلي على العملاء", "بديل", arabic=True)
        == "متجرك يحتاج رد آلي على العملاء"
    )


def test_english_field_guarded_for_leaks_only():
    assert _safe_summary("Escalate to Mohammed now", "fb", arabic=False) == "fb"
    assert _safe_summary("You need a content plan", "fb", arabic=False) == "You need a content plan"
