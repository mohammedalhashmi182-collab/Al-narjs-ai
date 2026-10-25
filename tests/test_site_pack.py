"""Owner site pack (karmaai-fixes 01-12): newsletter API, about counts,
blog, and the honesty rules (no «معتمد», no star/rating schema)."""

import os
import re
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services import catalog, newsletter
from src.utils import rate_limit

TEMPLATES = Path(__file__).resolve().parents[1] / "src" / "web" / "templates"
URL = "/api/newsletter/subscribe"


def _db_path() -> str:
    url = os.environ["DATABASE_URL"]
    assert url.startswith("sqlite"), "these tests drive the sqlite test database"
    return url.split("///", 1)[1]


def _drop_table() -> None:
    con = sqlite3.connect(_db_path(), timeout=30)
    con.execute("DROP TABLE IF EXISTS newsletter_subscribers")
    con.commit()
    con.close()
    newsletter.reset_cache()


def _create_table() -> None:
    """The same shape as the reviewed 0018 migration."""
    _drop_table()
    con = sqlite3.connect(_db_path(), timeout=30)
    con.execute(
        "CREATE TABLE newsletter_subscribers ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " email VARCHAR(254) NOT NULL UNIQUE,"
        " lang VARCHAR(2) NOT NULL DEFAULT 'ar',"
        " consent_version VARCHAR(20) NOT NULL,"
        " consent_at DATETIME NOT NULL,"
        " ip_hash VARCHAR(32),"
        " unsubscribed_at DATETIME,"
        " created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
    )
    con.commit()
    con.close()
    newsletter.reset_cache()


def _rows() -> list[tuple]:
    con = sqlite3.connect(_db_path(), timeout=30)
    rows = con.execute("SELECT email, consent_version, ip_hash FROM newsletter_subscribers").fetchall()
    con.close()
    return rows


@pytest.fixture
def client():
    rate_limit.newsletter_limiter.reset()
    with TestClient(app) as c:
        yield c
    rate_limit.newsletter_limiter.reset()
    _drop_table()


@pytest.fixture
def with_table(client):
    _create_table()
    return client


def test_fails_closed_without_migration(client):
    _drop_table()
    assert client.get("/api/newsletter/status").json() == {"available": False}
    r = client.post(URL, json={"email": "a@example.com", "consent": True})
    assert r.status_code == 503
    body = r.json()
    assert body["ok"] is False and body["error"] == "unavailable"
    assert body["message"] == newsletter.UNAVAILABLE_AR


def test_status_reports_available_once_table_exists(with_table):
    assert with_table.get("/api/newsletter/status").json() == {"available": True}


@pytest.mark.parametrize("bad", ["", "no-at-sign", "a@b", "a b@example.com", "a@@example.com", "x" * 250 + "@example.com", None, 42])
def test_invalid_email_rejected(with_table, bad):
    r = with_table.post(URL, json={"email": bad, "consent": True})
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_email"
    assert _rows() == []


@pytest.mark.parametrize("consent", [None, False, "true", 1, "yes"])
def test_consent_must_be_explicit_true(with_table, consent):
    payload = {"email": "a@example.com"}
    if consent is not None:
        payload["consent"] = consent
    r = with_table.post(URL, json=payload)
    assert r.status_code == 422
    assert r.json()["error"] == "consent_required"
    assert _rows() == []


def test_subscribe_persists_and_dedupes(with_table):
    r = with_table.post(URL, json={"email": " Owner@Example.COM ", "consent": True, "lang": "en"})
    assert r.status_code == 200 and r.json()["status"] == "created"
    r2 = with_table.post(URL, json={"email": "owner@example.com", "consent": True})
    assert r2.status_code == 200 and r2.json()["status"] == "exists"
    rows = _rows()
    assert len(rows) == 1
    email, version, iphash = rows[0]
    assert email == "owner@example.com"
    assert version == newsletter.CONSENT_VERSION
    assert iphash and "127.0.0.1" not in iphash and "testclient" not in iphash


def test_honeypot_stores_nothing(with_table):
    r = with_table.post(URL, json={"email": "bot@example.com", "consent": True, "website": "http://spam"})
    assert r.status_code == 200
    assert _rows() == []


def test_rate_limited_per_ip(with_table):
    codes = [with_table.post(URL, json={"email": f"u{i}@example.com", "consent": True}).status_code for i in range(7)]
    assert codes[:5] == [200] * 5
    assert codes[5] == 429 and codes[6] == 429


def test_storage_error_is_503_not_fake_success(with_table, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(newsletter, "subscribe", boom)
    r = with_table.post(URL, json={"email": "a@example.com", "consent": True})
    assert r.status_code == 503 and r.json()["ok"] is False


def test_popup_carries_the_exact_consent_text():
    html = (TEMPLATES / "partials" / "_newsletter_popup.html").read_text(encoding="utf-8")
    assert "أوافق على استلام النشرة ويمكنني إلغاء الاشتراك في أي وقت وفق" in html
    assert newsletter.CONSENT_AR.startswith("أوافق على استلام النشرة ويمكنني إلغاء الاشتراك في أي وقت وفق")
    assert re.search(r'id="njNewsletter"[^>]*\bhidden\b', html), "popup must start hidden"


def test_about_shows_real_catalog_counts(client):
    html = client.get("/ar/about").text
    assert f">{len(catalog.EMPLOYEES)}<" in html
    assert f">{catalog.DIVISION_COUNT}<" in html
    assert "5+" not in html
    assert "إن لم يعمل الوكيل خلال 10 أيام عمل نسترد رسوم الإعداد فقط" in html
    assert "وفق نظام PDPL" in html
    en = client.get("/en/about").text
    assert f">{len(catalog.EMPLOYEES)}<" in en and f">{catalog.DIVISION_COUNT}<" in en


@pytest.mark.parametrize("path", ["/blog", "/ar/blog", "/en/blog"])
def test_blog_ok_with_coming_soon_cards(client, path):
    r = client.get(path)
    assert r.status_code == 200
    assert "دراسة مقارنة" not in r.text
    assert "مدوّبة" not in r.text
    assert r.text.count("is-soon") >= 6


def test_landing_has_the_pack_sections(client):
    html = client.get("/ar/home").text
    for marker in ('class="nj-trust', 'id="examples"', 'id="sample-stories"', 'id="referral"', "data-theme-toggle", 'id="njNewsletter"'):
        assert marker in html, marker
    assert "أمثلة توضيحية وليست آراء موثّقة" in html
    assert "NRJ-YOUR-CODE" not in html
    assert html.index('id="how"') < html.index('id="examples"') < html.index('id="results"')
    assert html.index('id="team"') < html.index('id="sample-stories"')
    assert html.index('id="referral"') < html.index('id="site-footer"')


PUBLIC_PAGES = ["/ar/home", "/en/home", "/ar/about", "/en/about", "/blog", "/en/blog", "/privacy", "/terms"]


@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_no_certified_wording(client, path):
    """No certification claim («معتمد» / «معتمدة من» / "certified"). The
    adjective «المعتمدة» meaning "your approved information" is not a claim."""
    html = client.get(path).text
    assert not re.search(r"(?<![\w])معتمد(?:ة|ون|ين)?(?![\w])", html)
    assert "معتمدة من" not in html and "معتمد من" not in html
    assert not re.search(r"\bcertified\b", html, re.I)


@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_no_star_or_rating_schema(client, path):
    html = client.get(path).text
    assert "aggregateRating" not in html
    assert '"Review"' not in html and '"ratingValue"' not in html
    assert "★" not in html and "☆" not in html


def test_pack_partials_have_no_emoji_or_fabricated_claims():
    emoji = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")
    for name in ("_trust_bar", "_case_studies", "_sample_quotes", "_referral_soon", "_newsletter_popup", "_theme_toggle"):
        text = (TEMPLATES / "partials" / f"{name}.html").read_text(encoding="utf-8")
        assert not emoji.search(text), name
        for banned in ("نتائج حقيقية", "آراء حقيقية", "الأرقام من النظام مباشرة", "معتمد"):
            assert banned not in text, (name, banned)
