"""Prevent customer-facing KB drift from the approved Narjis policy.

These tests only inspect tracked text; they never access production services.
"""
from pathlib import Path

from src.ai.rag import chunk_markdown


KB = Path(__file__).resolve().parents[1] / "data" / "kb" / "narjs_services.md"


def test_operator_personal_name_not_in_public_kb_or_index_chunks():
    text = KB.read_text(encoding="utf-8")
    indexed = "\n".join(item["text"] for item in chunk_markdown(text, "data/kb/narjs_services.md"))
    for private_name_part in ("الزهراني", "غرم الله", "أحمد عبدالله"):
        assert private_name_part not in text
        assert private_name_part not in indexed


def test_voice_copy_distinguishes_site_voice_from_phone_calls():
    text = KB.read_text(encoding="utf-8")
    voice_answer = text.split("### س14:", 1)[1].split("## ثانياً", 1)[0]
    assert "المستشار الصوتي متاح عبر صفحة الصوت" in voice_answer
    assert "عند دعم المتصفح وتوفر الخدمة" in voice_answer
    assert "المكالمات الهاتفية" in voice_answer
    assert "قريباً" not in voice_answer


def test_kb_preserves_commercial_and_safety_invariants():
    text = KB.read_text(encoding="utf-8")
    for approved in ("790", "1,490", "2,990", "لا نطلب تحويلاً بنكياً",
                     "لا نعد هنا بنتيجة استرداد", "AlNarjisai@gmail.com"):
        assert approved in text
    assert "15%" not in text
