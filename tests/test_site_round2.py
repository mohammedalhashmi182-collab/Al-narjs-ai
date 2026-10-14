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
            assert "قريباً" not in line and "coming soon" not in line.lower(), (key, line)
        assert len(p.get("coming", [])) == len(p.get("coming_en", []))
    assert catalog.PACKAGES["bay"]["coming"]


def test_pricing_page_splits_now_and_coming(client):
    html = client.get("/ar/pricing").text
    assert "متاح الآن" in html and "قادم قريباً" in html and "feat-coming" in html
    en = client.get("/en/pricing").text
    assert "Available now" in en and "Coming soon" in en


def test_portal_api_exposes_features_and_coming(client):
    pk = client.get("/api/portal/packages").json()["packages"]
    bay = next(p for p in pk if p["key"] == "bay")
    assert bay["features"] and bay["coming"] and bay["coming_en"]


def test_refund_policy_available_features_only(client):
    assert "الميزات المتاحة فقط" in client.get("/ar/refund-policy").text
    assert "available features only" in client.get("/en/terms").text


@pytest.mark.parametrize("path", ["/terms", "/privacy", "/blog", "/consult", "/refund-policy", "/about",
                                  "/pricing", "/contact", "/home", "/data-deletion", "/dpa", "/subprocessors"])
@pytest.mark.parametrize("lang", ["ar", "en"])
def test_assistant_on_public_pages(client, path, lang):
    r = client.get(f"/{lang}{path}")
    assert r.status_code == 200, path
    assert 'id="siteAssistant"' in r.text, path


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
    for s in ("كريم", "مؤسسة ذا أريبيان كونفو", "31332495263", "حي الرمال", "رؤية", "الفرنسية", "/static/logo.svg"):
        assert s in html, s


def test_scripted_demo_replaces_fake_clinic(client):
    html = client.get("/ar/home").text
    assert 'id="chat-demo"' in html and "مثال توضيحي" in html
    assert 'id="live-demo"' not in html and "/api/live-demo/chat" not in html


def test_internal_tests_section_labelled(client):
    html = client.get("/ar/home").text
    assert "اختبارات داخلية من فريق النرجس — ليست آراء عملاء" in html
    assert 'id="tryAssistant"' in html
    assert "Internal tests by the Al-Narjis team — not customer reviews" in client.get("/en/home").text


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


def test_ticket_rate_limited(client, monkeypatch):
    async def fake_notify(t):
        return {}

    monkeypatch.setattr(tickets, "_notify", fake_notify)
    codes = [client.post("/api/support/ticket", json={"name": "علي", "email": "ali@example.com", "question": "سؤال",
                                                       "consent": True}).status_code for _ in range(5)]
    assert 429 in codes
