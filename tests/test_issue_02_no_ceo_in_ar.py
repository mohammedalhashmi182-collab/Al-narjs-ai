import re
from http import HTTPStatus
from pathlib import Path

from fastapi.testclient import TestClient
from src.main import app

LANDING = Path(__file__).resolve().parents[1] / "src/web/templates/landing.html"
LINES = LANDING.read_text(encoding="utf-8").split("\n")


def _find(needle):
    hits = [l for l in LINES if needle in l]
    assert hits, needle
    return hits


def test_arabic_cta_has_no_ceo() -> None:
    with TestClient(app) as client:
        response = client.get("/ar/home")
    assert response.status_code == HTTPStatus.OK
    html = response.text
    actions = re.findall(r'<a\b[^>]*href="#start-ceo"[^>]*>(.*?)</a>', html, re.S)
    assert actions
    assert any("الرئيس التنفيذي" in action for action in actions)
    assert all(not re.search(r"\bCEO\b", action) for action in actions)
    for element_id in ("team", "consult"):
        section = re.search(rf'<section\b[^>]*id="{element_id}"[^>]*>(.*?)</section>', html, re.S)
        assert section
        text = re.sub(r"<[^>]+>", "", section.group(1))
        assert "الرئيس التنفيذي" in text
        assert not re.search(r"\bCEO\b", text)


def test_stage_label_arabic():
    l = _find("تكليف الفريق")[0]
    assert "تشخيص الرئيس التنفيذي" in l and "تشخيص CEO" not in l


def test_avatar_uses_the_glass_mark():
    l = _find('class="ceo-avatar"')[0]
    assert "glass_mark" in l
    assert ">CEO<" not in l


def test_diagnosis_line():
    l = _find("ceo-online")[0]
    assert "An initial diagnosis" in l and "فوري" not in l
