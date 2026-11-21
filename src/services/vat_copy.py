"""One public sentence for VAT, shared by the site, the voice agent, and consult.

The rate itself stays in settings. This module only chooses the wording so a
page and a spoken answer cannot disagree.
"""
from __future__ import annotations

from src.services import payments

AR_NONE = (
    "الأسعار نهائية بدون ضريبة قيمة مضافة، لأن النرجس غير مسجّلة في ضريبة القيمة المضافة؛ "
    "لذلك لا نصدر فواتير ضريبية، ونرسل فاتورة دفع عادية."
)
EN_NONE = (
    "Prices are final with no VAT added, because Al-Narjis is not VAT-registered, "
    "so we do not issue tax invoices."
)
AR_ON = "الأسعار قبل ضريبة القيمة المضافة، وتُضاف الضريبة عند الدفع."
EN_ON = "Prices are before VAT, and VAT is added at checkout."


def registered() -> bool:
    return payments.vat_enabled()


def tax_ar() -> str:
    if registered():
        return f"الأسعار قبل ضريبة القيمة المضافة {payments.vat_percent()}٪، وتُضاف الضريبة عند الدفع."
    return AR_NONE


def tax_en() -> str:
    if registered():
        return f"Prices are before {payments.vat_percent()}% VAT, and VAT is added at checkout."
    return EN_NONE


def voice_price_intro() -> str:
    """The clause that introduces the monthly catalog prices in a voice session."""
    if registered():
        return f"The published monthly prices, before {payments.vat_percent()}% VAT, are:"
    return "The published monthly prices are final, with no VAT added. They are:"


def spoken_tax_rule() -> str:
    """Tell the spoken advisor to use the same sentence, and no other tax wording."""
    if registered():
        sentence = tax_en()
    else:
        sentence = EN_NONE
    return (
        "If the caller asks about tax or VAT, answer with this wording only: "
        f"{sentence}\n"
        "Do not call a price VAT-inclusive, and do not invent a tax invoice.\n"
    )
