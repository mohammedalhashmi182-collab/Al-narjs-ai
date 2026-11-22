"""Guards for the cinematic homepage layer: assets, fallback, and claims."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "src/web/templates/landing.html"
CSS = ROOT / "src/web/static/css/narjis-cinematic.css"
JS = ROOT / "src/web/static/js/narjis-cinematic.js"


def test_cinematic_assets_are_self_hosted():
    html = LANDING.read_text(encoding="utf-8")
    assert "/static/css/narjis-cinematic.css" in html
    assert "/static/js/narjis-cinematic.js" in html
    assert "/static/img/narcissus-fallback.svg" in html
    assert CSS.exists() and JS.exists()
    for name in ("three.module.min.js", "gsap.min.js", "ScrollTrigger.min.js", "lenis.min.js"):
        path = ROOT / "src/web/static/vendor" / name
        assert path.exists() and path.stat().st_size > 1000, name
        assert "cdn.jsdelivr" not in html
        assert "unpkg.com" not in html


def test_cinematic_boot_has_fallback_and_reduced_motion_gates():
    html = LANDING.read_text(encoding="utf-8")
    assert "cine-fallback" in html and "cine-on" in html
    assert "prefers-reduced-motion" in html
    assert "saveData" in html
    assert "webgl" in html
    js = JS.read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in js
    assert CSS.read_text(encoding="utf-8").count("prefers-reduced-motion") >= 1


def test_story_does_not_invent_proof_or_forbidden_offers():
    html = LANDING.read_text(encoding="utf-8")
    chunk = html[html.index("cine-missed"):html.index('id="how"')]
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
