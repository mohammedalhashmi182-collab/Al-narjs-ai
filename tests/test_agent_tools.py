"""Agent tools: SAR limits, web search, data uploads, Salla/Zid, knowledge base."""
from __future__ import annotations

import io
from pathlib import Path

import httpx
import pytest
import yaml
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.owner_auth import make_session_token
from src.db.session import Base
from src.models import ClientProject
from src.models.automation import ReplyDraft
from src.services import agent_tools, smart_reply
from src.services.agent_tools import data_files, knowledge_base, store_connectors, web_search

TOOL_ENV = ("TAVILY_API_KEY", "BRAVE_SEARCH_API_KEY", "SERPER_API_KEY", "WEB_SEARCH_PROVIDER",
            "SALLA_ACCESS_TOKEN", "SALLA_CLIENT_ID", "SALLA_CLIENT_SECRET", "SALLA_REDIRECT_URI",
            "ZID_AUTHORIZATION_TOKEN", "ZID_MANAGER_TOKEN", "ZID_STORE_ID", "ZID_CLIENT_ID",
            "ZID_CLIENT_SECRET", "ZID_REDIRECT_URI")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in TOOL_ENV:
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _client(maker, owner=False):
    from src.main import app

    app.state.session_factory = maker
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                             cookies={"narjis_owner": make_session_token()} if owner else {})


async def _project(maker, status="active"):
    async with maker() as s:
        p = ClientProject(client_name="متجر الورد", phone="0555000000", package="team", status=status)
        s.add(p)
        await s.commit()
        return p


class _R:
    def __init__(self, body, code=200):
        self._b, self.status_code = body, code

    def json(self):
        return self._b

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("x", request=None, response=None)


# ---------------------------------------------------------------- SAR limits
def test_spending_limits_are_in_sar():
    for path in Path("agents/base").glob("*.yaml"):
        text = path.read_text()
        assert "micro_budget_usd" not in text and "amount_usd" not in text and "$250" not in text, path
    closer = yaml.safe_load(Path("agents/base/sales_closer.yaml").read_text())
    assert closer["x_tasami"]["micro_budget_sar"] == 950
    assert "ريال" in Path("agents/base/policy_guardian.yaml").read_text()


def test_legacy_usd_budget_converts():
    from src.core.architecture.registry.agent_catalog import _budget_sar

    assert _budget_sar({"micro_budget_usd": 250}) == 950
    assert _budget_sar({"micro_budget_usd": 100}) == 400
    assert _budget_sar({"micro_budget_sar": 500, "micro_budget_usd": 1}) == 500


# ---------------------------------------------------------------- web search
async def test_web_search_disabled_without_key():
    res = await web_search.search("عطور الرياض")
    assert res["enabled"] is False and "TAVILY_API_KEY" in res["message"]
    assert "TAVILY_API_KEY" in web_search.context_block(res)
    assert agent_tools.status()["web_search"]["enabled"] is False


async def test_web_search_tavily(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    seen = {}

    async def _post(self, url, *a, **k):
        seen["url"] = url
        return _R({"results": [{"title": "T", "url": "https://x.sa", "content": "snippet"}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", _post)
    res = await web_search.search("q")
    assert res["provider"] == "tavily" and res["results"][0]["url"] == "https://x.sa"
    assert "tavily" in seen["url"]


async def test_web_search_brave_and_errors_are_soft(monkeypatch):
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "k")

    async def _get(self, url, *a, **k):
        return _R({"web": {"results": [{"title": "B", "url": "u", "description": "d"}]}})

    monkeypatch.setattr(httpx.AsyncClient, "get", _get)
    assert (await web_search.search("q"))["results"][0]["title"] == "B"

    async def _boom(self, url, *a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx.AsyncClient, "get", _boom)
    res = await web_search.search("q")
    assert res["results"] == [] and "failed" in res["message"]


# ---------------------------------------------------------------- data files
def test_parse_csv_summary():
    data = "المنتج,الكمية,السعر\nعطر,3,150\nبخور,5,80\nعطر,1,150\n".encode()
    s = data_files.parse("sales.csv", data)
    assert s["rows"] == 3
    cols = {c["name"]: c for c in s["columns"]}
    assert cols["السعر"]["type"] == "number" and cols["السعر"]["sum"] == 380
    assert cols["المنتج"]["top"][0] == "عطر"
    assert "sales.csv" in data_files.context_block([{"filename": "sales.csv", "summary": s}])


def test_parse_xlsx():
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["month", "revenue"])
    ws.append(["jan", 1000])
    ws.append(["feb", 1500])
    buf = io.BytesIO()
    wb.save(buf)
    s = data_files.parse("r.xlsx", buf.getvalue())
    assert s["rows"] == 2 and s["columns"][1]["max"] == 1500


def test_upload_limits_and_types(monkeypatch):
    with pytest.raises(data_files.UploadError):
        data_files.parse("x.exe", b"abc")
    with pytest.raises(data_files.UploadError):
        data_files.parse("x.csv", b"")
    monkeypatch.setattr(data_files, "MAX_UPLOAD_BYTES", 10)
    with pytest.raises(data_files.UploadError):
        data_files.parse("x.csv", b"a,b\n1,2\n3,4\n")


async def test_portal_upload_endpoint_and_run_context(maker):
    p = await _project(maker)
    async with _client(maker) as c:
        r = await c.post(f"/api/portal/projects/{p.id}/files",
                         files={"file": ("s.csv", "a,b\n1,2\n3,4\n".encode(), "text/csv")})
        assert r.status_code == 200, r.text
        assert r.json()["rows"] == 2
        r = await c.post(f"/api/portal/projects/{p.id}/files", files={"file": ("s.exe", b"x", "x")})
        assert r.status_code == 400
        assert len((await c.get(f"/api/portal/projects/{p.id}/files")).json()["files"]) == 1
    async with maker() as s:
        ctx = await agent_tools.run_context(s, "data_analyst", p, {"q": "حلل"})
    assert "s.csv" in ctx and "TAVILY_API_KEY" in ctx  # data + disabled web search notice


async def test_portal_upload_requires_active_subscription(maker):
    p = await _project(maker, status="pending")
    async with _client(maker) as c:
        r = await c.post(f"/api/portal/projects/{p.id}/files", files={"file": ("s.csv", b"a\n1\n", "text/csv")})
    assert r.status_code == 402


# ---------------------------------------------------------------- stores
async def test_store_connectors_unconfigured_make_no_calls(monkeypatch):
    async def _never(*a, **k):
        raise AssertionError("no network without credentials")

    monkeypatch.setattr(httpx.AsyncClient, "get", _never)
    snaps = await store_connectors.snapshots()
    assert {s["platform"] for s in snaps} == {"salla", "zid"}
    assert all(not s["configured"] for s in snaps)
    assert "SALLA_ACCESS_TOKEN" in store_connectors.context_block(snaps)
    assert store_connectors.get("salla").authorize_url("s") is None


async def test_salla_read_only_fetch(monkeypatch):
    monkeypatch.setenv("SALLA_ACCESS_TOKEN", "tok")
    calls = []

    async def _get(self, url, params=None, headers=None, **k):
        calls.append(url)
        assert headers["Authorization"] == "Bearer tok"
        if url.endswith("/products"):
            return _R({"data": [{"id": 1, "name": "عطر", "price": {"amount": 150}, "quantity": 4, "status": "sale"}]})
        return _R({"data": [{"id": 9, "reference_id": "R9", "total": {"amount": 300}, "status": {"name": "مكتمل"},
                             "date": {"date": "2026-10-01"}}]})

    async def _no_post(*a, **k):
        raise AssertionError("connectors are read-only")

    monkeypatch.setattr(httpx.AsyncClient, "get", _get)
    monkeypatch.setattr(httpx.AsyncClient, "post", _no_post)
    snap = await store_connectors.get("salla").snapshot()
    assert snap["products"][0]["price"] == 150 and snap["orders"][0]["reference"] == "R9"
    assert all("api.salla.dev" in u for u in calls)


async def test_zid_read_only_fetch(monkeypatch):
    for k in ("ZID_AUTHORIZATION_TOKEN", "ZID_MANAGER_TOKEN", "ZID_STORE_ID"):
        monkeypatch.setenv(k, "v")

    async def _get(self, url, params=None, headers=None, **k):
        assert headers["X-Manager-Token"] == "v" and headers["Store-Id"] == "v"
        if "products" in url:
            return _R({"results": [{"id": 2, "name": "بخور", "price": 80, "quantity": 2, "is_published": True}]})
        return _R({"orders": [{"id": 3, "code": "Z3", "order_total": 80, "order_status": {"name": "new"}}]})

    monkeypatch.setattr(httpx.AsyncClient, "get", _get)
    snap = await store_connectors.get("zid").snapshot()
    assert snap["products"][0]["name"] == "بخور" and snap["orders"][0]["status"] == "new"


def test_oauth_authorize_url(monkeypatch):
    monkeypatch.setenv("SALLA_CLIENT_ID", "cid")
    monkeypatch.setenv("SALLA_REDIRECT_URI", "https://karmaai.online/cb")
    url = store_connectors.get("salla").authorize_url("st")
    assert url.startswith("https://accounts.salla.sa/oauth2/auth?") and "client_id=cid" in url


async def test_owner_tool_endpoints_are_gated(maker):
    async with _client(maker) as c:
        assert (await c.get("/api/owner/tools/status")).status_code in (401, 403)
        assert (await c.get("/api/owner/stores/salla/snapshot")).status_code in (401, 403)
    async with _client(maker, owner=True) as c:
        st = (await c.get("/api/owner/tools/status")).json()
        assert st["stores"]["salla"]["missing"] == ["SALLA_ACCESS_TOKEN"]
        assert (await c.get("/api/owner/stores/nope/snapshot")).status_code == 404


# ---------------------------------------------------------------- knowledge base
FAQ = """ساعات العمل
نعمل من السبت إلى الخميس من 9 صباحًا حتى 11 مساءً.

التوصيل
التوصيل داخل الرياض خلال 24 ساعة ورسوم التوصيل 25 ريال.

الاسترجاع
يمكن استرجاع المنتج خلال 7 أيام بشرط أن يكون مغلقًا."""


def test_kb_retrieval_picks_the_right_chunk(monkeypatch):
    monkeypatch.setattr(knowledge_base, "CHUNK_CHARS", 60)
    hits = knowledge_base.search_texts([("FAQ", FAQ)], "كم رسوم التوصيل للرياض؟")
    assert hits and "25 ريال" in hits[0]["text"]
    assert knowledge_base.search_texts([("FAQ", FAQ)], "سعر الذهب اليوم") == []


def test_kb_pdf_and_limits(monkeypatch):
    with pytest.raises(knowledge_base.KBError):
        knowledge_base.text_from_upload("x.docx", b"abc")
    monkeypatch.setattr(knowledge_base, "MAX_UPLOAD_BYTES", 2)
    with pytest.raises(knowledge_base.KBError):
        knowledge_base.text_from_upload("x.txt", b"abc")
    monkeypatch.setattr(knowledge_base, "MAX_UPLOAD_BYTES", 10_000)
    with pytest.raises(knowledge_base.KBError):
        knowledge_base.text_from_upload("x.pdf", b"not a pdf")


async def test_kb_portal_and_customer_service_context(maker):
    p = await _project(maker)
    async with _client(maker) as c:
        r = await c.post(f"/api/portal/projects/{p.id}/knowledge",
                         files={"file": ("faq.txt", FAQ.encode(), "text/plain")})
        assert r.status_code == 200, r.text
        assert len((await c.get(f"/api/portal/projects/{p.id}/knowledge")).json()["docs"]) == 1
    async with maker() as s:
        ctx = await agent_tools.run_context(s, "customer_service", p, {"x": "سياسة الاسترجاع"})
    assert "7 أيام" in ctx


async def test_owner_kb_feeds_smart_reply_as_review_draft(maker, monkeypatch):
    async def _never(*a, **k):
        raise AssertionError("review mode must not send")

    monkeypatch.setattr(smart_reply, "deliver", _never)
    async with _client(maker, owner=True) as c:
        r = await c.post("/api/owner/knowledge", data={"title": "FAQ", "text": FAQ})
        assert r.status_code == 200, r.text
    async with _client(maker) as c:
        assert (await c.post("/api/owner/knowledge", data={"text": FAQ})).status_code in (401, 403)
    async with maker() as s:
        d = await smart_reply.handle_inbound(s, channel="telegram", recipient="55",
                                             text="متى ساعات العمل عندكم؟")
    assert isinstance(d, ReplyDraft) and d.status == "pending"
    assert "السبت" in d.draft_text and d.meta.get("kb")
