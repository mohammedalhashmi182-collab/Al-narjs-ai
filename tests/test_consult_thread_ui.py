"""The public consultant is a centered reading thread, still Al-Narjis.

Assistant replies stay open text. Visitor turns sit on the opposite side.
The composer is pinned. Nothing on the page borrows another product's name.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from src.main import app

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "src" / "web" / "templates" / "consult.html"
CSS = ROOT / "src" / "web" / "static" / "css" / "consult-thread.css"


def _css() -> str:
    return CSS.read_text(encoding="utf-8")


def _template() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def test_thread_css_is_a_reading_column() -> None:
    css = _css().lower()
    assert "body.consult-thread" in css
    assert "background: transparent" in css
    assert "align-self: flex-end" in css
    assert "position: sticky" in css
    assert "bottom: 0" in css
    assert "border-radius: 28px" in css
    assert "#ff5a36" in css
    assert "color: #000000" in css
    assert "prefers-reduced-motion: reduce" in css
    for foreign in ("grok", "x.ai", "grok.com"):
        assert foreign not in css


def test_template_keeps_the_consult_contract_without_a_foreign_brand() -> None:
    body = _template()
    lowered = body.lower()
    for foreign in ("grok", "x.ai", "grok.com", "xai"):
        assert foreign not in lowered
    assert "consult-thread.css" in body
    assert "/static/css/consult-tw.css" in body
    assert "narjis-luxury.css" in body
    assert "family=Cairo" in body
    assert 'class="luxury consult-thread"' in body
    assert 'id="chatBox"' in body
    assert 'id="msg"' in body
    assert 'id="send"' in body
    assert 'id="suggestions"' in body
    assert "/api/consult" in body
    assert "data-copy" in body
    assert "/static/logo-dark.svg" in body
    assert "innerHTML" not in body
    assert "منصة النرجس" in body
    assert "وثيقة عمل حر رقم FL-272182297" in body
    assert "Operated by Al-Narjs" in body
    assert "تحدث بحرية عن عملك" in body
    assert "Talk freely about your business" in body


def test_rendered_thread_switches_direction_and_copy_label() -> None:
    with TestClient(app) as client:
        arabic = client.get("/consult", cookies={"narjis_lang": "ar"})
        english = client.get("/en/consult")
    assert arabic.status_code == 200
    assert english.status_code == 200
    ar = arabic.text
    en = english.text
    assert re.search(r'<html[^>]*\blang="ar"[^>]*\bdir="rtl"', ar)
    assert re.search(r'<html[^>]*\blang="en"[^>]*\bdir="ltr"', en)
    assert 'data-copy="نسخ"' in ar and 'data-copied="تم النسخ"' in ar
    assert 'data-copy="Copy"' in en and 'data-copied="Copied"' in en
    assert "ct-composer" in ar and "ct-dock" in ar and "ct-avatar" in ar
    assert "Talk freely about your business" not in ar
    assert "تحدث بحرية عن عملك" not in en
    assert 'id="voiceLauncher"' in ar
    assert "goLang" in ar
