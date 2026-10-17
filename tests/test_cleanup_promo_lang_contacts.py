"""Expired launch offer, one language per HTML response, and the current contacts."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from src.main import app
from src.services import email_service

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "src" / "web" / "templates"


def _visible(html: str) -> str:
    html = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.S | re.I)
    html = re.sub(r"<style\b[^>]*>.*?</style>", "", html, flags=re.S | re.I)
    return html


def test_guide_drops_the_expired_offer_and_points_at_pricing():
    html = (TEMPLATES / "guide.html").read_text(encoding="utf-8")
    assert "NARJIS50" not in html
    assert "حتى 14 أكتوبر" not in html
    assert "خصم 50%" not in html
    assert html.count('href="/pricing"') >= 2


def test_customer_email_does_not_sell_the_expired_code():
    welcome = email_service._welcome_html("سارة")
    follow = email_service._followup_html(3, "سارة")
    plain = "عرض الإطلاق يمنحك خصم 50%"
    for blob in (welcome, follow, email_service._FOLLOWUP_COPY[1]["subject"], email_service._FOLLOWUP_COPY[3]["cta"]):
        assert "NARJIS50" not in blob
        assert "14 أكتوبر" not in blob
        assert plain not in blob
    assert "https://karmaai.online/pricing" in welcome
    assert "https://karmaai.online/pricing" in follow


def test_pages_render_only_the_active_language():
    cases = {
        "/portal": ("الدخول إلى بوابتك", "Sign in to your portal"),
        "/consult": ("تحدث بحرية عن عملك", "Talk freely about your business"),
        "/dpa": ("اتفاقية معالجة البيانات", "Data Processing Agreement"),
        "/subprocessors": ("المعالجون الفرعيون", "Subprocessors"),
        "/privacy": ("سياسة الخصوصية", "Privacy Policy"),
        "/terms": ("الشروط والأحكام", "Terms of Service"),
        "/data-deletion": ("تعليمات حذف البيانات", "Data Deletion Instructions"),
    }
    with TestClient(app) as client:
        for path, (arabic, english) in cases.items():
            ar = _visible(client.get(path, cookies={"narjis_lang": "ar"}).text)
            en = _visible(client.get(f"/en{path}", cookies={"narjis_lang": "en"}).text)
            assert arabic in ar, path
            assert english not in ar, path
            assert 'data-lang="en"' not in ar, path
            assert english in en, path
            assert arabic not in en, path
            assert 'data-lang="ar"' not in en, path


def test_language_toggle_still_reloads_the_prefixed_url():
    """Portal and consult keep the pill. Legal pages switch by /ar/ and /en/ only."""
    with TestClient(app) as client:
        for path in ("/portal", "/consult"):
            html = client.get(path, cookies={"narjis_lang": "ar"}).text
            assert 'data-lang-btn="ar"' in html and 'data-lang-btn="en"' in html
            assert "goLang" in html
            assert 'class="arabic active"' in html
            assert 'class="arabic {{' not in html
            english = client.get(f"/en{path}").text
            assert 'lang="en"' in english
            assert 'class="english active"' in english


def test_old_contact_channels_are_gone_from_code():
    files = {
        ROOT / "src/services/transfer.py": "t.me/AlNarjs7BOT",
        ROOT / "src/services/lead_outreach.py": "t.me/AlNarjs7BOT",
        ROOT / "src/services/tenant_reply.py": "t.me/alnarjs",
        ROOT / "src/config/settings.py": "0552978753",
        TEMPLATES / "sales_dashboard.html": "t.me/AlNarjs7BOT",
        TEMPLATES / "sales_lead.html": "t.me/AlNarjs7BOT",
    }
    for path, banned in files.items():
        assert banned not in path.read_text(encoding="utf-8"), path.name
    from src.config.settings import Settings

    assert Settings.model_fields["whatsapp_business_number"].default == "0540799266"


def test_sales_surfaces_use_the_current_contacts():
    lead = (TEMPLATES / "sales_lead.html").read_text(encoding="utf-8")
    dash = (TEMPLATES / "sales_dashboard.html").read_text(encoding="utf-8")
    assert "btn-tg" not in lead
    assert "Al-Narjis@karmaai.online" in lead and "0540799266" in lead
    assert "mailto:Al-Narjis@karmaai.online" in dash
    assert "0540799266" in dash
