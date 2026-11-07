"""Landing intro regression: the hero must be immediately usable, not covered."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_home_removes_fullscreen_intro_and_keeps_small_brand_signature():
    html = (ROOT / "src/web/templates/landing.html").read_text(encoding="utf8")
    css = (ROOT / "src/web/static/css/narjis-najdi.css").read_text(encoding="utf8")
    assert 'id="njIntro"' not in html
    assert "nj-intro-on" not in html
    assert "narjis-intro.js" not in html
    assert "narjis-intro.css" not in html
    assert '<div class="nj-wordmark" lang="ar" dir="rtl" aria-hidden="true"><span>النرجس</span></div>' in html
    assert "clamp(25px,3.2vw,37px)" in css
    assert "@media(prefers-reduced-motion:reduce)" in css
    assert 'id="heroCeo"' in html


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_home_compact_wordmark_on_both_languages(lang):
    from fastapi.testclient import TestClient
    from src.main import app

    with TestClient(app) as client:
        response = client.get(f"/{lang}/home")
    assert response.status_code == 200
    assert response.text.count('class="nj-wordmark"') == 1
    assert 'id="njIntro"' not in response.text
    assert "nj-intro-on" not in response.text
    assert 'href="/consult" id="heroCeo"' in response.text
