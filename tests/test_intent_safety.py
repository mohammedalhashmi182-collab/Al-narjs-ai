"""Regression coverage for purchase intent and financial safety."""

import pytest

from src.services.intent_classify import classify_intent


@pytest.mark.parametrize("text", [
    "أبي أعرف السعر", "أبغى أشترك، كم السعر؟", "أريد معرفة التكلفة",
])
def test_price_takes_priority_over_buying(text):
    assert classify_intent(text)[0] == "PRICE"


@pytest.mark.parametrize("text", [
    "أبي معلومات", "ابغى وكيل للمبيعات", "اريد مساعدتك", "how is your business",
])
def test_generic_requests_are_not_purchase_intent(text):
    assert classify_intent(text)[0] != "READY_TO_BUY"


@pytest.mark.parametrize("text", ["أبغى أشترك", "موافق نبدأ", "I want to subscribe"])
def test_explicit_purchase_still_recognized(text):
    assert classify_intent(text)[0] == "READY_TO_BUY"


def test_normalizes_keywords_as_well_as_input():
    assert classify_intent("عندي سؤال عن الفاتورة")[0] == "PROPOSAL"
    assert classify_intent("أبغى أشترك وعندي سؤال عن الفاتورة")[0] == "PROPOSAL"


def test_opt_out_wins_over_purchase():
    assert classify_intent("لا ترسل، اشترك")[0] == "OPT_OUT"
