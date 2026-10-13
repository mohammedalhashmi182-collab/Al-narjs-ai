"""CEO diagnosis uses token matching: 'محل ورد' is a flower shop, not a reply problem."""
import pytest

from src.services import ceo_advisor


def keys(text):
    return {n.key for n in ceo_advisor.diagnose_rules(text).needs}


@pytest.mark.parametrize("text", [
    "محل ورد في الرياض",
    "عندي محل ورد وأبي أكبّر المشروع",
    "بائع ورود وهدايا",
    "مورد مواد غذائية في جدة",
    "نبيع البرد والمكيفات",
    "مصنع بردة",
])
def test_reply_false_positives(text):
    assert "support" not in keys(text)


@pytest.mark.parametrize("text", [
    "ما أقدر أرد على العملاء بسرعة",
    "الرد على الواتساب متأخر",
    "وردود العملاء كثيرة",
    "تأخر بالرد على الرسائل",
    "we can't keep up with customer replies",
    "عندي شكاوى كثيرة",
])
def test_reply_true_positives(text):
    assert "support" in keys(text)


@pytest.mark.parametrize("text,absent", [
    ("I sell apples", "tech"),       # 'app' must not match 'apples'
    ("زدت عدد الموظفين", "store"),    # 'زد' (Zid) must not match 'زدت'
    ("عندي ربحية عالية", "pricing"),  # short stem 'ربح' needs a whole word
])
def test_short_stems_need_whole_words(text, absent):
    assert absent not in keys(text)


@pytest.mark.parametrize("text,present", [
    ("our app is slow", "tech"),
    ("متجري على سلة وزد", "store"),
    ("والإعلانات ما تجيب نتائج", "ads"),
    ("بالتسويق ضعيفين", "marketing"),
    ("نبي نبيع أكثر", "sales"),
])
def test_prefixes_and_suffixes(text, present):
    assert present in keys(text)


def test_full_company_phrase_and_variants():
    assert ceo_advisor.diagnose_rules("أبي شركة كاملة").full_company
    assert ceo_advisor.diagnose_rules("ابي شركه كامله").full_company  # ة/ه and أ/ا folding
    assert not ceo_advisor.diagnose_rules("شركة صغيرة").full_company


def test_variants_do_not_strip_root_letters():
    assert "رد" not in ceo_advisor._variants("ورد")
    assert "رد" in ceo_advisor._variants("الرد")
    assert "ردود" in ceo_advisor._variants("وردود")
