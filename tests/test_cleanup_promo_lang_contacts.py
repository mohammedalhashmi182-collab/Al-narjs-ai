"""Expired launch offer, one language per HTML response, and the current contacts."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from src.main import app
from src.services import email_service, payments

# Retired WhatsApp digits, split so the old number is not stored contiguously.
RETIRED_PHONE_DIGITS = "552" + "978753"

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
        ROOT / "src/config/settings.py": "0" + RETIRED_PHONE_DIGITS,
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


def _set_promo(monkeypatch, *, code="LAUNCH", percent=50, expires="2099-01-01"):
    settings = payments.get_settings()
    monkeypatch.setattr(settings, "promo_code", code)
    monkeypatch.setattr(settings, "promo_percent", percent)
    monkeypatch.setattr(settings, "promo_expires", expires)


def test_promo_requires_a_set_parseable_future_expiry(monkeypatch):
    today = datetime.now(timezone.utc).date()
    future = (today + timedelta(days=10)).isoformat()
    inactive = [
        ("LAUNCH", 50, None),
        ("LAUNCH", 50, ""),
        ("LAUNCH", 50, "   "),
        ("LAUNCH", 50, "14 أكتوبر 2026"),
        ("LAUNCH", 50, "2026-13-40"),
        ("LAUNCH", 50, "2026/10/14"),
        ("LAUNCH", 50, today.isoformat()),
        ("LAUNCH", 50, (today - timedelta(days=1)).isoformat()),
        ("LAUNCH", 50, (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()),
        ("LAUNCH", 0, future),
        ("", 50, future),
        (None, 50, future),
    ]
    for code, percent, expires in inactive:
        _set_promo(monkeypatch, code=code, percent=percent, expires=expires)
        assert payments.promo_active() is False, (code, percent, expires)
        assert payments.apply_promo(10_000, "LAUNCH") == (10_000, 0)

    _set_promo(monkeypatch, expires=(today + timedelta(days=1)).isoformat())
    assert payments.promo_active() is True
    assert payments.promo_info()["active"] is True
    assert payments.promo_info()["percent"] == 50
    assert payments.apply_promo(10_000, "launch") == (5_000, 50)
    assert payments.apply_promo(10_000, "OTHER") == (10_000, 0)

    later = (datetime.now(timezone.utc) + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _set_promo(monkeypatch, expires=later)
    assert payments.promo_active() is True


def test_portal_noscript_and_promo_field_follow_language_and_promo_state(monkeypatch):
    _set_promo(monkeypatch, expires=None)
    with TestClient(app) as client:
        ar = client.get("/portal", cookies={"narjis_lang": "ar"}).text
        en = client.get("/en/portal").text
    assert "فعّل JavaScript لاختيار الباقة" in ar
    assert "Enable JavaScript to choose a plan" not in ar
    assert "Enable JavaScript to choose a plan" in en
    assert "فعّل JavaScript لاختيار الباقة" not in en
    for html in (ar, en):
        assert 'id="promoInput"' not in html
        assert 'id="promoRow"' not in html
        assert 'id="promoApply"' not in html

    today = datetime.now(timezone.utc).date()
    _set_promo(monkeypatch, code="KEEP", percent=20, expires=(today + timedelta(days=3)).isoformat())
    with TestClient(app) as client:
        ar = client.get("/portal", cookies={"narjis_lang": "ar"}).text
        en = client.get("/en/portal").text
    assert 'id="promoInput"' in ar and "كود الخصم" in ar and "Promo code" not in ar
    assert 'id="promoInput"' in en and "Promo code" in en and "كود الخصم" not in en


def test_named_launch_files_drop_the_retired_code():
    paths = [
        ROOT / "campaigns/ai-awareness/LAUNCH-PLAYBOOK.md",
        ROOT / "campaigns/ai-awareness/creative-assets/creative_builder.py",
        ROOT / "campaigns/ai-awareness/creative-assets/endcard.py",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "NARJIS50" not in text, path.name
    endcard = paths[-1].read_text(encoding="utf-8")
    assert "ينتهي العرض" not in endcard
    assert "خصم 50%" not in endcard


def test_retired_phone_digits_are_gone_and_the_social_batch_uses_the_current_number():
    social = (ROOT / "marketing/social-batch1-ceo-advisor-ar.md").read_text(encoding="utf-8")
    assert "https://wa.me/966540799266" in social
    skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache"}
    skip_suffixes = {
        ".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf", ".mp4",
        ".woff", ".woff2", ".ttf", ".ico", ".pyc",
    }
    hits = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix.lower() in skip_suffixes:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if RETIRED_PHONE_DIGITS in text:
            hits.append(str(path.relative_to(ROOT)))
    assert hits == []


def test_retired_code_is_absent_from_customer_and_marketing_trees():
    """NARJIS50 must not remain under product, marketing, or campaign trees."""
    hits = []
    for base in (ROOT / "src", ROOT / "marketing", ROOT / "campaigns"):
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            try:
                blob = path.read_bytes()
            except OSError:
                continue
            if b"NARJIS50" in blob:
                hits.append(str(path.relative_to(ROOT)))
    assert hits == []


def test_arabic_subprocessors_page_uses_arabic_for_embeddings():
    with TestClient(app) as client:
        ar = client.get("/subprocessors", cookies={"narjis_lang": "ar"}).text
        en = client.get("/en/subprocessors").text
    assert "تضمين النصوص" in ar
    assert "embeddings" not in ar
    assert "embeddings" in en
