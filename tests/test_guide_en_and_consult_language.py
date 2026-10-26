"""/en/guide is English LTR, and the consult reply follows the visitor's language."""

import re

import httpx
import pytest
from fastapi.testclient import TestClient

from src.core.karma_persona import enforce_reply_policy, reply_locale
from src.main import app

_AR = re.compile(r"[\u0600-\u06FF]")


async def _get(path):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", follow_redirects=True
    ) as client:
        r = await client.get(path)
    assert r.status_code == 200
    return r.text


async def test_en_guide_is_english_ltr():
    html = await _get("/en/guide")
    assert '<html lang="en" dir="ltr"' in html
    page = html
    for tag in ("title", "h1", "h2", "label", "button", "footer"):
        for inner in re.findall(rf"<{tag}[^>]*>(.*?)</{tag}>", page, flags=re.S):
            assert not _AR.search(inner), (tag, inner[:80])
    assert 'A <span class="grad">30-day</span>' in html
    assert "Salla/Zid store connection is coming soon" in html
    assert "محمد الهاشمي" not in html


async def test_ar_guide_stays_arabic_rtl():
    html = await _get("/ar/guide")
    assert '<html lang="ar" dir="rtl"' in html
    assert "للذكاء الاصطناعي</h1>" in html
    assert "ربط سلة أو زد قريباً" in html
    assert "محمد الهاشمي" not in html


def test_reply_locale_follows_the_visitor():
    assert reply_locale("I want a bot for my Salla store", "ar") == "en"
    assert reply_locale("أبغى بوت لمتجري", "en") == "ar"
    assert reply_locale("790?", "en") == "en"


def test_salla_misspelling_is_corrected_without_touching_other_words():
    out = enforce_reply_policy("متجر سِلا ومتجر سلا والسلام وإسلامي", locale="ar")
    assert "سِلا" not in out and " سلا " not in out
    assert out.count("سلة") == 2 and "والسلام" in out and "إسلامي" in out


class _Capture:
    def __init__(self, content):
        self.content, self.system = content, ""

    async def complete_with_fallback(self, chain_name, request):
        self.system = request.system_prompt
        return type("R", (), {"content": self.content})()


@pytest.fixture()
def client(monkeypatch):
    import src.utils.rate_limit as rl

    monkeypatch.setattr(rl.consult_limiter, "reset", lambda: None, raising=False)
    with TestClient(app) as c:
        yield c


def test_english_question_gets_english_prompt_and_never_an_arabic_reply(client, monkeypatch):
    prov = _Capture("متجر سِلا (Salla) نظام غير مؤكد دعم رسمياً")
    monkeypatch.setattr(app.state, "model_provider", prov, raising=False)
    client.cookies.set("narjis_lang", "ar")
    r = client.post(
        "/api/consult",
        json={
            "messages": [{"role": "user", "content": "I want a bot for my Salla store"}],
            "lang": "en",
        },
    )
    assert r.status_code == 200
    assert not _AR.search(r.json()["reply"])
    assert "Respond ONLY in clear, fluent business English" in prov.system
    assert "coming soon" in prov.system and "«سلة»" in prov.system

