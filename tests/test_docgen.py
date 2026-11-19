"""DocPack: computed figures, a guarded narrative, and files that open."""

from __future__ import annotations

import io
import re
import time
from datetime import date
from types import SimpleNamespace

import httpx
import pandas as pd
import pytest
from docx import Document
from docx.oxml.ns import qn
from openpyxl import load_workbook
from pptx import Presentation
from pypdf import PdfReader
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.owner_auth import make_session_token
from src.core.portal_auth import COOKIE_NAME, make_session_token as portal_token
from src.db.session import Base
from src.models import ClientProject
from src.services import agent_profiles
from src.services.agent_tools import docpack_tool
from src.services.docgen import DESIGNED_SLIDE_COUNT, build_docpack
from src.services.docgen.analyze import linear_forecast_next
from src.services.docgen.guard import offending_numbers
from src.services.docgen.sample import FIXTURE_PATH, SAMPLE_PATH, build_sample_bytes, load_sample_bytes

FIXED_DAY = date(2026, 6, 15)
ARABIC = re.compile(r"[\u0600-\u06FF]")
_SUM = re.compile(r"^=SUM\('([^']+)'!([A-Z]+)(\d+):([A-Z]+)(\d+)\)$")


@pytest.fixture(autouse=True)
def _reset_docpack_limits():
    from src.services.docgen.store import PACKS
    from src.utils.rate_limit import docpack_api_limiter, docpack_demo_global_limiter, docpack_demo_limiter

    backups = {
        docpack_api_limiter: docpack_api_limiter.max_requests,
        docpack_demo_limiter: docpack_demo_limiter.max_requests,
        docpack_demo_global_limiter: docpack_demo_global_limiter.max_requests,
    }
    for limiter in backups:
        limiter.reset()
    PACKS.reset()
    yield
    for limiter, max_requests in backups.items():
        limiter.max_requests = max_requests
        limiter.reset()
    PACKS.reset()


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _client(maker, cookies=None):
    from src.main import app

    app.state.session_factory = maker
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        cookies=cookies or {},
    )


async def _project(maker, status="active"):
    async with maker() as session:
        project = ClientProject(
            client_name="متجر العيّنة",
            phone="0555123456",
            email="buyer@shop.sa",
            package="radd",
            status=status,
        )
        session.add(project)
        await session.commit()
        await session.refresh(project)
        return project


async def _pack(provider=None, *, formats=None, brief="", file_bytes=None, filename="sales.xlsx", agent_key="data_analyst"):
    payload = load_sample_bytes() if file_bytes is None else file_bytes
    return await build_docpack(
        brief=brief or "عيّنة توضيحية للمبيعات.",
        file_bytes=payload,
        filename=filename if payload else None,
        agent_key=agent_key,
        agent_name_ar="محلل البيانات",
        agent_name_en="Data Analyst",
        formats=formats or ["pdf", "xlsx", "pptx", "docx"],
        model_provider=provider,
        client_name="عيّنة توضيحية",
        today=FIXED_DAY,
    )


def _file(pack, fmt: str) -> bytes:
    return next(item.content for item in pack.files if item.format == fmt)


def _pdf_text(data: bytes) -> str:
    return "\n".join((page.extract_text() or "") for page in PdfReader(io.BytesIO(data)).pages)


def _docx_text(data: bytes) -> str:
    document = Document(io.BytesIO(data))
    chunks = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            chunks.extend(cell.text for cell in row.cells)
    return "\n".join(chunks)


def _pptx_text(data: bytes) -> str:
    presentation = Presentation(io.BytesIO(data))
    chunks = []
    for slide in presentation.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                chunks.append(shape.text_frame.text)
    return "\n".join(chunks)


def _eval_sum(workbook, formula: str) -> tuple[str, float]:
    match = _SUM.match(formula)
    assert match, formula
    sheet, col_a, row_a, col_b, row_b = match.groups()
    assert col_a == col_b
    header = workbook[sheet].cell(1, ord(col_a) - 64).value
    total = 0.0
    for row in workbook[sheet][f"{col_a}{row_a}:{col_b}{row_b}"]:
        for cell in row:
            if isinstance(cell.value, (int, float)):
                total += float(cell.value)
    return str(header), total


class _Scripted:
    def __init__(self, replies: list[str]):
        self.replies = list(replies)
        self.calls = 0

    async def complete_with_fallback(self, _chain, _request):
        self.calls += 1
        content = self.replies.pop(0) if self.replies else ""
        return SimpleNamespace(content=content)


def _sheet_rows(data: bytes) -> list[list]:
    workbook = load_workbook(io.BytesIO(data))
    return [[cell.value for cell in row] for row in workbook.active.iter_rows()]


def test_sample_fixture_matches_the_generator_and_is_bundled():
    generated = _sheet_rows(build_sample_bytes())
    assert SAMPLE_PATH.is_file() and FIXTURE_PATH.is_file()
    assert _sheet_rows(SAMPLE_PATH.read_bytes()) == generated
    assert _sheet_rows(FIXTURE_PATH.read_bytes()) == generated
    assert generated[0] == ["الشهر", "المنتج", "الكمية", "سعر الوحدة", "المبيعات"]
    assert len(generated) == 13


def test_the_five_agents_can_call_docpack_and_others_cannot():
    for slug in ("data_analyst", "market_analyst", "finance_pricing", "project_manager", "orchestrator"):
        assert "docpack" in agent_profiles.profile_for(slug).tools
    assert "docpack" not in agent_profiles.profile_for("customer_service", "support").tools
    assert docpack_tool.requested({"docpack": True})
    assert docpack_tool.requested({"docpack": "yes"})
    assert not docpack_tool.requested({"questions": "اكتب تقريراً عن المبيعات"})


async def test_sample_pack_opens_and_finishes_quickly():
    started = time.perf_counter()
    pack = await _pack()
    elapsed = time.perf_counter() - started
    assert elapsed < 60, elapsed
    assert {item.format for item in pack.files} == {"pdf", "xlsx", "pptx", "docx"}
    PdfReader(io.BytesIO(_file(pack, "pdf")))
    load_workbook(io.BytesIO(_file(pack, "xlsx")))
    Presentation(io.BytesIO(_file(pack, "pptx")))
    Document(io.BytesIO(_file(pack, "docx")))
    assert pack.narrative.source == "deterministic"
    assert not offending_numbers(pack.narrative.full_text(), pack.analysis.allowed_values())


async def test_docx_is_rtl_with_cairo():
    pack = await _pack(formats=["docx"])
    document = Document(io.BytesIO(_file(pack, "docx")))
    section = document.sections[0]._sectPr
    assert section.find(qn("w:bidi")) is not None
    rtl_paragraphs = [
        paragraph for paragraph in document.paragraphs
        if paragraph._p.pPr is not None and paragraph._p.pPr.find(qn("w:bidi")) is not None
    ]
    assert rtl_paragraphs
    xml = document.element.xml
    assert "Cairo" in xml
    assert 'w:ascii="Cairo"' in xml or "w:ascii=\"Cairo\"" in xml
    assert ARABIC.search(_docx_text(_file(pack, "docx")))


async def test_xlsx_totals_are_formulas_that_match_pandas():
    frame = pd.read_excel(io.BytesIO(load_sample_bytes()), engine="openpyxl")
    pack = await _pack(formats=["xlsx"])
    workbook = load_workbook(io.BytesIO(_file(pack, "xlsx")))
    summary = workbook["الملخص"]
    formulas = [
        cell.value for row in summary.iter_rows() for cell in row
        if isinstance(cell.value, str) and cell.value.startswith("=SUM(")
    ]
    assert len(formulas) >= 3
    seen = {}
    for formula in formulas:
        header, total = _eval_sum(workbook, formula)
        seen[header] = total
        assert header in frame.columns
        assert total == pytest.approx(float(pd.to_numeric(frame[header], errors="coerce").sum()))
    assert "المبيعات" in seen
    monthly = frame.groupby("الشهر")["المبيعات"].sum().sort_index()
    assert pack.analysis.growth_pct == pytest.approx(
        (float(monthly.iloc[-1]) - float(monthly.iloc[0])) / float(monthly.iloc[0]) * 100
    )
    assert pack.analysis.forecast == pytest.approx(linear_forecast_next([float(value) for value in monthly.tolist()]))
    forecast_cells = [
        cell.value for row in summary.iter_rows() for cell in row
        if isinstance(cell.value, str) and cell.value.startswith("=FORECAST.LINEAR(")
    ]
    assert forecast_cells
    growth_cells = [
        cell.value for row in summary.iter_rows() for cell in row
        if isinstance(cell.value, str) and "B2" in cell.value and "*100" in cell.value
    ]
    assert growth_cells


async def test_pptx_has_the_designed_slide_count():
    pack = await _pack(formats=["pptx"])
    presentation = Presentation(io.BytesIO(_file(pack, "pptx")))
    assert len(presentation.slides) == DESIGNED_SLIDE_COUNT == 7
    assert ARABIC.search(_pptx_text(_file(pack, "pptx")))


async def test_pdf_text_contains_arabic():
    pack = await _pack(formats=["pdf"])
    text = _pdf_text(_file(pack, "pdf"))
    assert "النرجس" in text
    assert ARABIC.search(text)
    assert "97183" in text.replace(",", "") or "97,183" in text


async def test_invented_numbers_are_rejected_then_dropped():
    invented = (
        '{"headline_ar":"حجم السوق 999999","summary_ar":"الرقم 999999","insights_ar":["999999"],'
        '"recommendations_ar":[],"headline_en":"999999","summary_en":"999999"}'
    )
    still_bad = invented.replace("999999", "888888")
    provider = _Scripted([invented, still_bad])
    pack = await _pack(provider)
    assert provider.calls == 2
    assert pack.narrative.source == "dropped"
    blob = "\n".join([
        _pdf_text(_file(pack, "pdf")),
        _docx_text(_file(pack, "docx")),
        _pptx_text(_file(pack, "pptx")),
        _file(pack, "xlsx").decode("latin-1", "ignore"),
    ])
    assert "999999" not in blob
    assert "888888" not in blob
    assert not offending_numbers(pack.narrative.full_text(), pack.analysis.allowed_values())


async def test_a_narrative_that_copies_facts_is_kept():
    frame = pd.read_excel(io.BytesIO(load_sample_bytes()), engine="openpyxl")
    total = int(frame["المبيعات"].sum())
    reply = (
        '{"headline_ar":"إجمالي المبيعات ' + str(total) + '","summary_ar":"الإجمالي ' + str(total) + '",'
        '"insights_ar":["عدد الصفوف 12"],"recommendations_ar":["راجع الجدول."],'
        '"headline_en":"Total ' + str(total) + '","summary_en":"Total ' + str(total) + '"}'
    )
    provider = _Scripted([reply])
    pack = await _pack(provider, formats=["docx"])
    assert provider.calls == 1
    assert pack.narrative.source == "model"
    assert str(total) in _docx_text(_file(pack, "docx"))
    assert "راجع الجدول." in _docx_text(_file(pack, "docx"))


async def test_brief_without_numbers_cannot_invent_a_market_size():
    invented = (
        '{"headline_ar":"حجم السوق 5000000","summary_ar":"5000000","insights_ar":[],'
        '"recommendations_ar":[],"headline_en":"5000000","summary_en":""}'
    )
    provider = _Scripted([invented, invented])
    pack = await build_docpack(
        brief="نريد وصفاً للتوسع في الرياض دون أرقام.",
        file_bytes=None,
        filename=None,
        agent_key="market_analyst",
        agent_name_ar="محلل السوق",
        agent_name_en="Market Analyst",
        formats=["pdf"],
        model_provider=provider,
        today=FIXED_DAY,
    )
    assert pack.narrative.source == "dropped"
    assert "5000000" not in _pdf_text(_file(pack, "pdf"))
    assert ARABIC.search(_pdf_text(_file(pack, "pdf")))


async def test_csv_brief_series_total_is_a_formula():
    pack = await build_docpack(
        brief="",
        file_bytes="القيمة\n100\n150\n180\n".encode(),
        filename="series.csv",
        agent_key="finance_pricing",
        agent_name_ar="المالية والتسعير",
        agent_name_en="Finance and Pricing",
        formats=["xlsx"],
        today=FIXED_DAY,
    )
    workbook = load_workbook(io.BytesIO(_file(pack, "xlsx")))
    formulas = [
        cell.value for row in workbook["الملخص"].iter_rows() for cell in row
        if isinstance(cell.value, str) and cell.value.startswith("=SUM(")
    ]
    assert formulas
    _header, total = _eval_sum(workbook, formulas[0])
    assert total == pytest.approx(430)


async def test_api_requires_portal_or_owner_and_holds_unreviewed_customer_files(maker, monkeypatch):
    sent = {}

    async def _send(to, subject, body, html=None, attachments=None):
        sent["to"] = to
        sent["attachments"] = attachments
        sent["body"] = body
        return True

    monkeypatch.setattr("src.services.email_service.send_email", _send)
    async with _client(maker) as client:
        anonymous = await client.post("/api/docpack", data={"brief": "100 ثم 150", "agent_key": "data_analyst"})
    assert anonymous.status_code == 401

    project = await _project(maker, status="pending")
    async with _client(maker, {COOKIE_NAME: portal_token(project)}) as client:
        inactive = await client.post("/api/docpack", data={"brief": "100 ثم 150", "agent_key": "data_analyst"})
    assert inactive.status_code == 402

    project = await _project(maker, status="active")
    async with _client(maker, {COOKIE_NAME: portal_token(project)}) as client:
        refused = await client.post(
            "/api/docpack",
            data={"brief": "100 ثم 150", "agent_key": "customer_service"},
        )
        assert refused.status_code == 400
        built = await client.post(
            "/api/docpack",
            data={"brief": "المبيعات 100 ثم 150 ثم 180", "agent_key": "project_manager", "formats": "pdf,xlsx"},
        )
    assert built.status_code == 202, built.text
    body = built.json()
    assert body["status"] == "review_required"
    assert body["emailed"] is False and body["files"] == []
    assert sent == {}  # no review => no email, even when the client has an email

    async with _client(maker, {"narjis_owner": make_session_token()}) as client:
        owner = await client.post(
            "/api/docpack",
            files={"file": ("sales.xlsx", load_sample_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"agent_key": "orchestrator", "brief": "عيّنة للمالك"},
        )
    assert owner.status_code == 200, owner.text
    assert owner.json()["emailed"] is False
    assert len(owner.json()["files"]) == 3


async def test_demo_page_sample_and_rate_limit(maker):
    from src.utils.rate_limit import docpack_demo_limiter

    async with _client(maker) as client:
        arabic = await client.get("/ar/docpack")
        english = await client.get("/en/docpack")
        plain = await client.get("/docpack", follow_redirects=False)
    assert arabic.status_code == english.status_code == 200
    assert 'lang="ar"' in arabic.text and 'dir="rtl"' in arabic.text
    assert 'lang="en"' in english.text and 'dir="ltr"' in english.text
    assert 'href="#"' not in arabic.text and 'href="#"' not in english.text
    assert "/api/docpack/demo" in arabic.text
    assert plain.status_code == 301 and plain.headers["location"].endswith("/ar/docpack")

    async with _client(maker) as client:
        demo = await client.post("/api/docpack/demo", data={"sample": "1", "lang": "ar"})
    assert demo.status_code == 200, demo.text
    files = demo.json()["files"]
    assert [item["format"] for item in files] == ["pdf", "xlsx", "pptx"]
    async with _client(maker) as client:
        for item in files:
            downloaded = await client.get(item["url"])
            assert downloaded.status_code == 200
            assert downloaded.headers["content-type"].startswith(item["media_type"])
            assert len(downloaded.content) > 500

    docpack_demo_limiter.max_requests = 1
    docpack_demo_limiter.reset()
    async with _client(maker) as client:
        first = await client.post("/api/docpack/demo", data={"brief": "100 و 200"})
        second = await client.post("/api/docpack/demo", data={"brief": "100 و 200"})
    assert first.status_code == 200
    assert second.status_code == 429


def test_upload_over_ten_megabytes_is_refused():
    from src.services.docgen.analyze import MAX_UPLOAD_BYTES, load_table
    from src.services.docgen.schema import DocGenError

    assert MAX_UPLOAD_BYTES == 10 * 1024 * 1024
    with pytest.raises(DocGenError):
        load_table("big.csv", b"x" * (MAX_UPLOAD_BYTES + 1))
