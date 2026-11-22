"""Guards for the v5/v6 homepage layers: self-hosted motion, fallbacks, brand mark and claims."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "src/web/templates/landing.html"
CSS = ROOT / "src/web/static/css/narjis-v5.css"
CSS6 = ROOT / "src/web/static/css/narjis-v6.css"
ORB = ROOT / "src/web/static/css/narjis-v6-orb.css"
JS = ROOT / "src/web/static/js/narjis-v6.js"
LOGO = ROOT / "src/web/templates/partials/_v5_logo.html"


def test_motion_assets_are_self_hosted():
    html = LANDING.read_text(encoding="utf-8")
    for asset in ("/static/css/narjis-v5.css", "/static/css/narjis-v6.css", "/static/css/narjis-v6-orb.css", "/static/js/narjis-v6.js",
                  "/static/vendor/gsap.min.js", "/static/vendor/ScrollTrigger.min.js", "/static/vendor/lenis.min.js"):
        assert asset in html, asset
    for name in ("gsap.min.js", "ScrollTrigger.min.js", "lenis.min.js"):
        path = ROOT / "src/web/static/vendor" / name
        assert path.exists() and path.stat().st_size > 1000, name
    for banned in ("cdn.jsdelivr", "unpkg.com", "three.module", "narjis-cinematic.js", "narjis-gsap.js", "narjis-v5.js"):
        assert banned not in html
    assert CSS.exists() and CSS6.exists() and JS.exists() and ORB.exists()
    assert ORB.stat().st_size < 70_000  # first-paint orb posters + the blurred room only


def test_glass_has_a_fallback_and_readable_tokens():
    css = CSS6.read_text(encoding="utf-8")
    assert "backdrop-filter" in css and "@supports not" in css
    assert "--v6-cta-a: #D93A46" in css and "--v6-cta-b: #B8285A" in css  # white CTA text >= 4.5:1


def test_boot_has_reduced_motion_and_save_data_gates():
    html = LANDING.read_text(encoding="utf-8")
    assert "v5-static" in html and "v5-motion" in html
    assert "prefers-reduced-motion" in html and "saveData" in html
    js = JS.read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in js and "pin:" in js
    css = CSS6.read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in css
    assert "html.v5-static .v6-orb-video" in css


def test_hero_clip_is_muted_inline_and_lazy():
    html = LANDING.read_text(encoding="utf-8")
    tag = html[html.index('<video'):html.index('</video>')]
    for attr in ("muted", "playsinline", "loop", 'preload="none"', 'aria-hidden="true"'):
        assert attr in tag, attr
    assert "autoplay" not in tag  # played from JS only in motion mode


def test_logo_is_a_living_svg_wordmark_without_the_old_mark():
    logo = LOGO.read_text(encoding="utf-8")
    assert "<path" in logo and "v5-dot" in logo and "AL-NARJIS AI" in logo
    assert "<image" not in logo and "base64" not in logo
    css = CSS.read_text(encoding="utf-8")
    for anim in ("v5-breathe", "v5-heart", "v5-sweep"):
        assert f"@keyframes {anim}" in css
    html = LANDING.read_text(encoding="utf-8")
    assert html.count("v5_logo(") == 2  # header and footer
    assert "/static/logo.svg" not in html
    assert "narcissus" not in html.lower()
    assert (ROOT / "src/web/static/logo.svg").exists()


def test_story_does_not_invent_proof_or_forbidden_offers():
    html = LANDING.read_text(encoding="utf-8")
    chunk = html[html.index('id="top"'):html.index('id="ceo-desk"')]
    for banned in ("24/7", "مجان", "خصم", "ضريبة", "أفضل متجر", "عميل سعيد", "★★", "موثوق به", "free", "discount"):
        assert banned not in chunk, banned
    assert "محاكاة" in chunk


def test_homepage_has_no_appointment_or_booking_wording():
    lowered = LANDING.read_text(encoding="utf-8").lower()
    for banned in ("تنظيم المواعيد", "الحجوزات", "احجز", "appointment", "booking", "book a diagnosis"):
        assert banned.lower() not in lowered, banned


def test_first_screen_has_subscribe_and_whatsapp_ctas():
    html = LANDING.read_text(encoding="utf-8")
    hero = html[html.index('id="top"'):html.index('id="how"')]
    assert 'id="heroSubscribe"' in hero and 'href="#pricing"' in hero
    assert 'id="heroWhatsapp"' in hero and "wa.me/966552978753" in hero
    assert 'id="mbarSubscribe"' in html


def test_agent_network_uses_the_live_catalogue():
    html = LANDING.read_text(encoding="utf-8")
    team = html[html.index('id="team"'):html.index('id="ceo-desk"')]
    assert "catalog_employees" in team and "/ai-agent/" in team
    for name in ("تحليل", "تطوير", "تصميم", "مبيعات", "تسويق"):
        assert name in team
    assert 'id="pulse-live"' in team
