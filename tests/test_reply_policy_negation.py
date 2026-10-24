"""The reply guard must not invert sentences that already deny phone support or tax invoices."""

from src.core.karma_persona import enforce_reply_policy


def test_negated_phone_support_is_kept():
    out = enforce_reply_policy("لا توجد خدمات الدعم عبر الهاتف أو الواتساب.")
    assert "الموقع والبريد" not in out.split("\n")[0]
    assert "الهاتف" in out


def test_english_negated_phone_support_is_kept():
    out = enforce_reply_policy("We do not offer phone support.", locale="en")
    assert out.startswith("We do not offer phone support")


def test_negated_tax_invoice_line_is_kept():
    line = "لا نصدر فواتير ضريبية لأننا غير مسجلين."
    assert line in enforce_reply_policy(line)


def test_positive_claims_still_fixed():
    assert "الهاتف" not in enforce_reply_policy("نقدم الدعم عبر الهاتف دائماً")
    out = enforce_reply_policy("نصدر فاتورة ضريبية لكل عميل")
    assert "فاتورة ضريبية" not in out and "بدون ضريبة" in out
