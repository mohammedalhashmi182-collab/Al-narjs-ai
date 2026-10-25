"""E: landing trust cleanup: no fake/zero counters, no fake proof, every link resolves."""

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.session import Base
from src.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(params=["/ar/", "/en/"])
def home(request, client):
    r = client.get(request.param)
    assert r.status_code == 200
    return request.param, r.text


def test_both_homes_keep_direction(client):
    ar, en = client.get("/ar/").text, client.get("/en/").text
    assert re.search(r'<html[^>]*lang="ar"[^>]*dir="rtl"', ar)
    assert re.search(r'<html[^>]*lang="en"[^>]*dir="ltr"', en)


def test_db_counters_are_hidden_and_never_dash_or_zero(home):
    _, page = home
    for key, el in (("leads_received", "pulseLeads"), ("projects", "pulseProjects")):
        assert f'<div data-pulse="{key}" hidden><b class="num" id="{el}"></b>' in page
    assert ">—</b>" not in page and 'class="num">0<' not in page
    # client script only reveals a counter for a real positive number
    assert "v > 0" in page


def test_no_fake_social_proof_or_forbidden_claims(home):
    _, page = home
    low = page.lower()
    for bad in (
        "aggregaterating",
        "ratingvalue",
        "★★★★",
        "testimonial-quote",
        "trusted by",
        "فاتورة ضريبية",
        "tax invoice",
        "tel:",
        "whatsapp support",
        "دعم عبر واتساب",
        "اتصل بنا",
    ):
        assert bad not in low, bad


def test_every_internal_link_on_home_resolves(home, client):
    _, page = home
    hrefs = set(re.findall(r'href="(/[^"#?]*)', page))
    assert hrefs, "no links found"
    broken = []
    for h in sorted(hrefs):
        r = client.get(h, follow_redirects=True)
        if r.status_code >= 400:
            broken.append((h, r.status_code))
    assert not broken, broken
    for anchor in set(re.findall(r'href="#([\w-]+)"', page)):
        if anchor == "assistant":  # opened by the site-assistant script
            assert 'a[href="#assistant"]' in page and 'id="saPanel"' in page
            continue
        assert f'id="{anchor}"' in page, anchor


async def test_pulse_counts_only_real_inbound_requests(monkeypatch):
    import httpx

    import src.models  # noqa: F401
    from src.models.crm import AcquisitionLead

    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        for i, src in enumerate(("website", "consult_assistant", "excel_import", "excel_import")):
            s.add(AcquisitionLead(company_name=f"n{i}", source=src))
        await s.commit()

    async def _factory():
        return maker

    monkeypatch.setattr("src.db.session.get_session_factory", _factory)
    monkeypatch.setattr(app.state, "public_pulse_cache", None, raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        d = (await c.get("/api/pulse")).json()
    assert d["leads_received"] == 2  # imported prospects are not "requests received"
    monkeypatch.setattr(app.state, "public_pulse_cache", None, raising=False)
    await engine.dispose()
