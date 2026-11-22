"""Guards for the GSAP homepage layer: self-hosted motion, fallback, and claims."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "src/web/templates/landing.html"
CSS = ROOT / "src/web/static/css/narjis-gsap.css"
JS = ROOT / "src/web/static/js/narjis-gsap.js"


def test_gsap_assets_are_self_hosted():
    html = LANDING.read_text(encoding="utf-8")
    assert "/static/css/narjis-gsap.css" in html
    assert "/static/js/narjis-gsap.js" in html
    font_css = (ROOT / "src/web/static/css/narjis-kufi-font.css").read_text(encoding="utf-8")
    assert "Noto Kufi Arabic" in font_css
    assert "data:font/woff2;base64," in font_css
    assert "fonts.googleapis" not in font_css
    assert CSS.exists() and JS.exists()
    assert "/static/css/narjis-kufi-font.css" in html
    for name in ("gsap.min.js", "ScrollTrigger.min.js", "lenis.min.js"):
        path = ROOT / "src/web/static/vendor" / name
        assert path.exists() and path.stat().st_size > 1000, name
    assert "cdn.jsdelivr" not in html
    assert "unpkg.com" not in html
    assert "three.module" not in html
    assert "narjis-cinematic.js" not in html


def test_gsap_boot_has_reduced_motion_and_save_data_gates():
    html = LANDING.read_text(encoding="utf-8")
    assert "v3-static" in html and "v3-motion" in html
    assert "prefers-reduced-motion" in html
    assert "saveData" in html
    js = JS.read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in js
    assert "pin:" in js
    assert CSS.read_text(encoding="utf-8").count("prefers-reduced-motion") >= 1


def test_story_does_not_invent_proof_or_forbidden_offers():
    html = LANDING.read_text(encoding="utf-8")
    chunk = html[html.index("v3-journey"):html.index('id="how"')]
    for banned in ("24/7", "مجانا", "خصم", "ضريبة", "أفضل متجر", "عميل سعيد", "★★", "موثوق به"):
        assert banned not in chunk
    assert "محاكاة" in chunk or "illustrative" in chunk.lower()


def test_homepage_has_no_appointment_or_booking_wording():
    html = LANDING.read_text(encoding="utf-8")
    lowered = html.lower()
    for banned in (
        "تنظيم المواعيد",
        "الحجوزات",
        "احجز",
        "appointment",
        "booking",
        "book a diagnosis",
    ):
        assert banned.lower() not in lowered, banned


def test_first_screen_has_subscribe_and_whatsapp_ctas():
    html = LANDING.read_text(encoding="utf-8")
    hero = html[html.index('id="top"'):html.index('id="how"')]
    assert 'id="heroSubscribe"' in hero and 'href="#pricing"' in hero
    assert 'id="heroWhatsapp"' in hero and "wa.me/966552978753" in hero
    assert 'id="mbarSubscribe"' in html
