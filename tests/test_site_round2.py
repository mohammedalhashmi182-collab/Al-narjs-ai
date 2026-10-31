"""Round-2 owner review items."""
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services import catalog, tickets


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_no_empty_testimonials_box(client):
    html = client.get("/ar/home").text
    assert "فارغة عمداً" not in html and 'data-placeholder="testimonials"' not in html


def test_coming_features_not_listed_as_included():
    for key, p in catalog.PACKAGES.items():
        for line in p["scope"] + p["scope_en"]:
            lowered = line.lower()
            if any(w in line for w in ("سلة", "زد")) or "salla" in lowered or "zid" in lowered:
                assert "قريباً" in line or "coming soon" in lowered, (key, line)
                continue
            assert "قريباً" not in line and "coming soon" not in lowered, (key, line)
        assert len(p.get("coming", [])) == len(p.get("coming_en", []))
    assert catalog.PACKAGES["numuw"]["coming"]


def test_pricing_page_splits_now_and_coming(client):
    html = client.get("/ar/pricing").text
    assert "متاح الآن" in html and "قادم قريباً" in html and "feat-coming" in html
    en = client.get("/en/pricing").text
    assert "Available now" in en and "Coming soon" in en


def test_portal_api_exposes_features_and_coming(client):
    pk = client.get("/api/portal/packages").json()["packages"]
    growth = next(p for p in pk if p["key"] == "numuw")
    assert growth["features"] and growth["coming"] and growth["coming_en"]
    assert all(p["key"] not in {"radd", "bay", "tashgheel"} for p in pk)


def test_refund_policy_available_features_only(client):
    assert "الميزات المتاحة فقط" in client.get("/ar/refund-policy").text
    assert "available features only" in client.get("/en/terms").text


@pytest.mark.parametrize("path", ["/terms", "/privacy", "/blog", "/consult", "/refund-policy", "/about",
                                  "/pricing", "/contact", "/home", "/data-deletion", "/dpa", "/subprocessors"])
@pytest.mark.parametrize("lang", ["ar", "en"])
def test_no_floating_assistant_on_public_pages(client, path, lang):
    r = client.get(f"/{lang}{path}")
    assert r.status_code == 200, path
    assert 'id="siteAssistant"' not in r.text, path


def test_no_tailwind_cdn_and_moyasar_in_csp(client):
    r = client.get("/ar/home")
    csp = r.headers["content-security-policy"]
    assert "cdn.tailwindcss.com" not in csp
    for d in ("https://api.moyasar.com", "https://cdn.moyasar.com", "https://*.moyasar.com"):
        assert d in csp
    form_action = next(p for p in csp.split("; ") if p.startswith("form-action"))
    assert "moyasar.com" in form_action
    for path in ("/portal", "/login"):
        assert "cdn.tailwindcss.com" not in client.get(path).text


def test_about_has_story_facts(client):
    html = client.get("/ar/about").text
    for s in ("كريم", "منصة النرجس", "FL-272182297", "رؤية", "الفرنسية", "/static/logo.svg"):
        assert s in html, s


def test_scripted_demo_replaces_fake_clinic(client):
    html = client.get("/ar/home").text
    assert 'id="chat-demo"' in html and "مثال توضيحي" in html
    assert 'id="live-demo"' not in html and "/api/live-demo/chat" not in html


def test_internal_tests_section_hidden_by_default(client, monkeypatch):
    monkeypatch.delenv("INTERNAL_TESTS_ENABLED", raising=False)
    for path in ("/ar/home", "/en/home"):
        html = client.get(path).text
        assert 'id="tested"' not in html and "جرّبناها بأنفسنا" not in html


def test_internal_tests_section_labelled_when_enabled(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_TESTS_ENABLED", "1")
    html = client.get("/ar/home").text
    assert 'id="tested"' in html
    assert "اختبارات داخلية من فريق النرجس — ليست آراء عملاء" in html
    assert 'id="tryAssistant"' not in html
    assert "Internal tests by the Al-Narjis team — not customer reviews" in client.get("/en/home").text


def test_deleted_sample_clinic_name_gone_everywhere(client, monkeypatch):
    import pathlib as _p
    from src.services import internal_tests, live_demo
    monkeypatch.setenv("INTERNAL_TESTS_ENABLED", "1")
    data = _p.Path(internal_tests._PATH).read_text(encoding="utf-8")
    assert "الياسمين" not in data and "Yasmin" not in data
    assert "الياسمين" not in live_demo.DEMO_NAME and "Yasmin" not in live_demo.DEMO_NAME_EN
    assert all("الياسمين" not in a for _, a in live_demo.KB)
    for path in ("/ar/home", "/en/home"):
        t = client.get(path).text
        assert "الياسمين" not in t and "Yasmin" not in t


def test_no_zatca_phase2_claim(client):
    for path in ("/ar/home", "/en/home", "/ar/pricing", "/ar/about"):
        t = client.get(path).text
        assert "المرحلة الثانية" not in t and "Phase 2" not in t and "phase 2" not in t


def test_ticket_validation():
    with pytest.raises(tickets.TicketError) as e:
        tickets.validate("كريم", "bad@", "سؤال", True)
    assert e.value.field == "email"
    with pytest.raises(tickets.TicketError) as e:
        tickets.validate("كريم", "a@b.co", "سؤال", False)
    assert e.value.field == "consent"
    assert tickets.validate(" كريم ", "A@B.co", "سؤال؟", True) == ("كريم", "a@b.co", "سؤال؟")


def test_ticket_endpoint_reference_and_owner_list(client, monkeypatch):
    from src.utils import rate_limit
    rate_limit.ticket_limiter._hits.clear() if hasattr(rate_limit.ticket_limiter, "_hits") else None
    sent = []

    async def fake_notify(t):
        sent.append(t.reference)
        return {"telegram": False, "email": False}

    monkeypatch.setattr(tickets, "_notify", fake_notify)
    bad = client.post("/api/support/ticket", json={"name": "كريم", "email": "x", "question": "مرحبا", "consent": True})
    assert bad.status_code == 422 and bad.json()["field"] == "email"
    r = client.post("/api/support/ticket", json={"name": "سارة", "email": "sara@example.com",
                                                 "question": "أبي أكلم موظف", "consent": True, "page": "/ar/home"})
    d = r.json()
    assert r.status_code == 200 and d["ok"] and d["reference"].startswith("NRJ-") and len(d["reference"]) == 10
    assert d["response_time"] == "خلال يوم عمل"
    assert sent == [d["reference"]]
    assert client.get("/api/owner/tickets").status_code == 401


def test_ticket_language_follows_page_not_stale_cookie(client, monkeypatch):
    from src.utils import rate_limit
    rate_limit.ticket_limiter._hits.clear() if hasattr(rate_limit.ticket_limiter, "_hits") else None

    async def fake_notify(t):
        return {"telegram": False, "email": False}

    monkeypatch.setattr(tickets, "_notify", fake_notify)
    client.get("/en/home")  # leaves an English locale cookie behind
    r = client.post("/api/support/ticket", json={"name": "سارة", "email": "sara@example.com",
                                                 "question": "سؤال", "consent": True, "page": "/ar/pricing"})
    assert r.json()["response_time"] == "خلال يوم عمل"
    r = client.post("/api/support/ticket", json={"name": "Sara", "email": "sara@example.com",
                                                 "question": "Question", "consent": True, "page": "/en/pricing"})
    assert r.json()["response_time"] == "within one business day"
    if hasattr(rate_limit.ticket_limiter, "_hits"):
        rate_limit.ticket_limiter._hits.clear()


def test_ticket_rate_limited(client, monkeypatch):
    async def fake_notify(t):
        return {}

    monkeypatch.setattr(tickets, "_notify", fake_notify)
    codes = [client.post("/api/support/ticket", json={"name": "علي", "email": "ali@example.com", "question": "سؤال",
                                                       "consent": True}).status_code for _ in range(5)]
    assert 429 in codes


def test_about_service_cards_set_dark_text_on_light_background(client):
    # Cards are a black field with white text and grey secondary copy.
    import re as _re
    for path in ("/ar/about", "/en/about"):
        html = client.get(path).text
        rule = _re.search(r"\.ab-card\{[^}]*\}", html).group(0)
        assert "background:#0b0b0b" in rule and "color:#ffffff" in rule
        assert _re.search(r"\.ab-card p\{[^}]*color:#b3b3b3", html)
