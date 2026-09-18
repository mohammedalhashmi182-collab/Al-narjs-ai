"""Tests for the customer-acquisition pipeline.

Covers the pieces that turn the messy Excel export into a trustworthy,
explicitly-prioritized outreach list — and the single-source-of-truth wiring
that makes a publicly captured lead and an imported lead share one CRM pipeline.

Everything here is stdlib-only for file reading: the real ingestion path uses
``src/services/lead_ingest.py`` (a hand-written OOXML reader), never openpyxl.
"""

from __future__ import annotations

import inspect
import zipfile
from pathlib import Path
from uuid import UUID
from xml.sax.saxutils import escape

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.owner_auth import make_session_token
from src.db.session import Base
from src.models import AcquisitionLead, CampaignLead, LeadEvent
from src.services import (
    lead_campaigns,
    lead_importer,
    lead_normalize,
    lead_outreach,
    lead_priority,
    lead_segmentation,
)

# ---------------------------------------------------------------------------
# Stdlib XLSX fixture builder (no openpyxl anywhere)
# ---------------------------------------------------------------------------

_XL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def _col_name(index: int) -> str:
    name, index = "", index + 1
    while index:
        index, rem = divmod(index - 1, 26)
        name = chr(65 + rem) + name
    return name


def _sheet_xml(rows: list[list[object]]) -> str:
    parts = [_XL, f'<worksheet xmlns="{_MAIN_NS}"><sheetData>']
    for r, row in enumerate(rows, start=1):
        parts.append(f'<row r="{r}">')
        for c, value in enumerate(row):
            if value is None or value == "":
                continue
            ref = f"{_col_name(c)}{r}"
            if isinstance(value, (int, float)):
                parts.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                parts.append(
                    f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
                )
        parts.append("</row>")
    parts.append("</sheetData></worksheet>")
    return "".join(parts)


def write_xlsx(path: Path, sheets: dict[str, list[list[object]]]) -> Path:
    names = list(sheets)
    wb = [_XL, f'<workbook xmlns="{_MAIN_NS}"><sheets>']
    for i, name in enumerate(names, start=1):
        wb.append(
            f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}" '
            f'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>'
        )
    wb.append("</sheets></workbook>")
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("xl/workbook.xml", "".join(wb))
        for i, name in enumerate(names, start=1):
            zf.writestr(f"xl/worksheets/sheet{i}.xml", _sheet_xml(sheets[name]))
    return path


INVOICE_HEADER = ["Customer", "Name 1", "last ivoice date", "Op / Cl", "mobile #", "email "]


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0553078789", "+966553078789"),
        ("+966 55 307 8789", "+966553078789"),
        ("00966553078789", "+966553078789"),
        ("553078789", "+966553078789"),
        ("966543210987", "+966543210987"),
        ("0112345678", "+966112345678"),
        ("447911123456", "+447911123456"),
        ("٠٥٥٣٠٧٨٧٨٩", "+966553078789"),
    ],
)
def test_normalize_phone_accepts_real_numbers(raw: str, expected: str) -> None:
    assert lead_normalize.normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["", "0", "0000000", "4481122", "12345", "٠", None, "abc"])
def test_normalize_phone_rejects_ambiguous_or_junk(raw) -> None:
    # Ambiguous short values must never be padded into a fake number.
    assert lead_normalize.normalize_phone(raw) is None


def test_whatsapp_capability_is_mobile_only() -> None:
    assert lead_normalize.is_whatsapp_capable("0553078789")
    assert not lead_normalize.is_whatsapp_capable("0112345678")
    assert not lead_normalize.is_whatsapp_capable("447911123456")


def test_wa_me_number_has_no_plus_or_leading_zero() -> None:
    assert lead_normalize.wa_me_number("0553078789") == "966553078789"


def test_company_name_key_unifies_arabic_and_legal_words() -> None:
    # Same company written with different legal prefixes and Arabic letter
    # variants (ى/ي) must collapse to one key. Extra words like "لخدمات" are
    # meaningful and intentionally kept.
    a = lead_normalize.company_name_key("شركة ضواحى الخبر")
    b = lead_normalize.company_name_key("مؤسسة ضواحي الخبر")
    assert a == b == "ضواحي الخبر"

    # A genuinely different name must not collapse.
    assert lead_normalize.company_name_key("شركة ضواحى الخبر لخدمات") != b


def test_parse_date_handles_excel_datetimes_and_text() -> None:
    from datetime import datetime

    assert lead_normalize.parse_date(datetime(2025, 3, 1)).year == 2025
    assert lead_normalize.parse_date("2024-06-15").year == 2024
    assert lead_normalize.parse_date("15/06/2024").year == 2024
    assert lead_normalize.parse_date("") is None


def test_parse_date_handles_excel_serial_numbers() -> None:
    # A date cell read as a plain number (stdlib reader) must still resolve.
    parsed = lead_normalize.parse_date("45292")
    assert parsed is not None and parsed.year == 2024
    # A phone-like or out-of-window value must never be read as a date.
    assert lead_normalize.parse_date("0553078789") is None


# ---------------------------------------------------------------------------
# Segmentation + priority
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "segment"),
    [
        ("مطعم شاورما البلد للوجبات", "restaurant_food"),
        ("مؤسسة دروب الورد للوجبات السريعة", "restaurant_food"),
        ("شركة الحلول التقنية للاتصالات", "services"),
        ("مكتب المحامي والاستشارات القانونية", "professional_services"),
        ("مستشفى الملك فهد الطبي", "healthcare"),
        ("متجر الإلكتروني للتجارة", "ecommerce"),
    ],
)
def test_classify_segment(name: str, segment: str) -> None:
    assert lead_segmentation.classify(name)[0] == segment


def test_suggest_package_is_always_a_known_package() -> None:
    from src.services import catalog

    for seg in list(lead_segmentation.SEGMENT_LABELS_AR) + ["made-up"]:
        assert lead_segmentation.suggest_package(seg) in catalog.PACKAGES


def test_priority_rewards_whatsapp_quote_and_recency() -> None:
    hot = lead_priority.score_lead(
        historical_customer=True,
        quotation_without_purchase=True,
        last_activity="2025-02-01",
        phone="+966553078789",
        segment="restaurant_food",
    )
    cold = lead_priority.score_lead(company_name="شركة", segment="unknown")
    assert hot.priority == "HIGH"
    assert cold.priority == "LOW"
    assert hot.score > cold.score
    assert any("واتساب" in r for r in hot.reasons)


def test_priority_never_exceeds_bounds() -> None:
    result = lead_priority.score_lead(
        historical_customer=True,
        quotation_without_purchase=True,
        last_activity="2026-01-01",
        phone="+966553078789",
        email="a@b.com",
        contact_name="سالم",
        invoice_count=50,
        segment="retail",
    )
    assert 0 <= result.score <= 100


# ---------------------------------------------------------------------------
# Outreach
# ---------------------------------------------------------------------------


def test_generate_message_builds_arabic_draft_and_wa_link() -> None:
    draft = lead_outreach.generate_message(
        {
            "company_name": "مطعم الأصالة",
            "phone": "+966553078789",
            "segment": "restaurant_food",
            "historical_customer": True,
            "quotation_without_purchase": False,
            "suggested_package": "social",
        }
    )
    assert "مطعم الأصالة" in draft["message"]
    assert draft["wa_link"].startswith("https://wa.me/966553078789")
    assert draft["variant"] in lead_outreach.VARIANT_LABELS_AR


def test_generate_message_without_phone_has_no_wa_link() -> None:
    draft = lead_outreach.generate_message(
        {"company_name": "شركة بلا رقم", "phone": None, "segment": "unknown"}
    )
    assert draft["wa_link"] is None
    assert draft["message"]


# ---------------------------------------------------------------------------
# De-duplication
# ---------------------------------------------------------------------------


def _raw(name: str, phone: str, *, sheet: str = "2024", kind: str = "customer") -> dict:
    return {
        "company_name": name,
        "name_key": lead_normalize.company_name_key(name),
        "phone": lead_normalize.normalize_phone(phone),
        "phone_raw": phone,
        "email": None,
        "source_sheet": sheet,
        "kind": kind,
        "historical_customer": kind == "customer",
        "quotation_without_purchase": kind == "quotation",
        "last_activity": "2024-05-01T00:00:00",
        "invoice_count": 1,
        "source_customer_code": None,
        "raw": {},
    }


def test_merge_records_joins_on_shared_phone() -> None:
    records = [
        _raw("شركة الأمل", "0553078789", sheet="2023"),
        _raw("مؤسسة الامل التجارية", "0553078789", sheet="2024"),
    ]
    merged = lead_importer.merge_records(records)
    assert len(merged) == 1
    assert merged[0]["record_count"] == 2
    assert merged[0]["historical_customer"] is True


def test_merge_records_keeps_distinct_companies_separate() -> None:
    records = [
        _raw("شركة الأمل", "0553078789"),
        _raw("شركة أخرى", "0500000000"),
    ]
    assert len(lead_importer.merge_records(records)) == 2


# ---------------------------------------------------------------------------
# Stdlib sheet reading (openpyxl-free)
# ---------------------------------------------------------------------------


def test_importer_does_not_depend_on_openpyxl() -> None:
    source = inspect.getsource(lead_importer)
    assert "import openpyxl" not in source
    assert "from openpyxl" not in source


def test_read_xlsx_stops_after_trailing_blanks(tmp_path: Path) -> None:
    rows: list[list[object]] = [INVOICE_HEADER]
    for i in range(3):
        rows.append(["C%d" % i, "شركة رقم %d" % i, "45292", "✔", "055307870%d" % i, ""])
    rows.extend([[None, None, None, None, None, None] for _ in range(200)])
    path = write_xlsx(tmp_path / "book.xlsx", {"2024": rows})

    records = lead_importer.extract_records(path)
    assert len(records) == 3
    assert all(r["historical_customer"] for r in records)
    # Excel serial dates survive as real dates (not silently dropped).
    assert all(r["last_activity"].startswith("2024-01-01") for r in records)
    assert all(r["phone"] for r in records)


def test_read_csv_uses_the_same_pipeline(tmp_path: Path) -> None:
    csv_path = tmp_path / "leads.csv"
    csv_path.write_text(
        ",".join(INVOICE_HEADER) + "\n"
        + "C0,مطعم الأصالة,45292,✔,0553078789,\n"
        + "C1,شركة أخرى,45292,✖,0500000000,\n",
        encoding="utf-8",
    )
    records = lead_importer.extract_records(csv_path)
    assert len(records) == 2
    assert records[0]["historical_customer"] is True
    assert records[1]["quotation_without_purchase"] is True


def test_malformed_xlsx_raises_cleanly(tmp_path: Path) -> None:
    bad = tmp_path / "broken.xlsx"
    bad.write_bytes(b"this is not a zip file")
    with pytest.raises(zipfile.BadZipFile):
        lead_importer.extract_records(bad)


def test_extract_records_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        lead_importer.extract_records(tmp_path / "nope.xlsx")


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


async def _make_engine():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def session():
    engine, maker = await _make_engine()
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest.fixture
async def api():
    """Real app with its DB swapped for an in-memory one + owner cookie."""
    from src.main import app

    engine, maker = await _make_engine()
    app.state.session_factory = maker
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"narjis_owner": make_session_token()},
    ) as client:
        yield client, maker
    await engine.dispose()


# ---------------------------------------------------------------------------
# Ingestion → CRM (idempotent persistence)
# ---------------------------------------------------------------------------


async def test_persist_leads_is_idempotent(session) -> None:
    records = [_raw("مطعم الأصالة", "0553078789")]
    leads = lead_importer.build_leads(records)

    created, updated = await lead_importer.persist_leads(session, leads)
    assert (created, updated) == (1, 0)

    # Re-importing the same company must not create a duplicate.
    created, updated = await lead_importer.persist_leads(session, leads)
    assert (created, updated) == (0, 1)
    total = (await session.execute(select(func.count()).select_from(AcquisitionLead))).scalar_one()
    assert total == 1

    row = (await session.execute(select(AcquisitionLead))).scalar_one()
    assert row.source == "excel_import"
    assert row.lead_status == "NEW"
    assert row.priority in ("HIGH", "MEDIUM", "LOW")
    assert row.segment == "restaurant_food"


async def test_build_leads_enriches_from_real_sheet_record(tmp_path: Path) -> None:
    rows = [INVOICE_HEADER, ["C0", "مطعم الأصالة", "45292", "✔", "0553078789", ""]]
    path = write_xlsx(tmp_path / "book.xlsx", {"2024": rows})
    leads = lead_importer.build_leads(lead_importer.extract_records(path))
    assert len(leads) == 1
    lead = leads[0]
    assert lead["segment"] == "restaurant_food"
    assert lead["suggested_package"] in ("social", "ecommerce", "content", "growth")
    assert lead["historical_customer"] is True
    assert lead["priority_score"] > 0


async def test_build_campaign_only_picks_reachable_high_value_leads(session) -> None:
    session.add_all(
        [
            AcquisitionLead(
                company_name="عميل ساخن",
                phone="+966553078789",
                priority="HIGH",
                priority_score=70,
                lead_status="NEW",
                segment="restaurant_food",
            ),
            AcquisitionLead(
                company_name="عميل متوسط",
                phone="+966500000000",
                priority="MEDIUM",
                priority_score=40,
                lead_status="NEW",
                segment="services",
            ),
            AcquisitionLead(
                company_name="بدون رقم",
                phone=None,
                priority="HIGH",
                priority_score=80,
                lead_status="NEW",
                segment="retail",
            ),
            AcquisitionLead(
                company_name="عميل منخفض",
                phone="+966555555555",
                priority="LOW",
                priority_score=10,
                lead_status="NEW",
            ),
        ]
    )
    await session.commit()

    campaign = await lead_campaigns.build_campaign(session, size=10, batch_no=1)
    count = (
        await session.execute(select(func.count()).select_from(CampaignLead))
    ).scalar_one()
    # Only the two reachable HIGH/MEDIUM leads qualify; the unmailable lead and
    # the LOW-priority lead are left for later batches.
    assert count == 2

    rows = (await session.execute(select(CampaignLead))).scalars().all()
    assert all(row.message_text for row in rows)

    discarded = (
        await session.execute(
            select(AcquisitionLead).where(AcquisitionLead.company_name.in_(["بدون رقم", "عميل منخفض"]))
        )
    ).scalars().all()
    assert all(lead.lead_status == "NEW" for lead in discarded)
    assert campaign.batch_no == 1


# ---------------------------------------------------------------------------
# Single source of truth: public capture → CRM → dashboard
# ---------------------------------------------------------------------------


async def test_public_capture_writes_one_acquisition_lead(api) -> None:
    client, maker = api
    resp = await client.post(
        "/api/leads",
        json={
            "name": "مطعم الأصالة",
            "phone": "0553078789",
            "email": "owner@example.com",
            "package": "social",
            "message": "أريد عرض سعر",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    lead_id = body["lead_id"]
    assert lead_id

    async with maker() as session:
        lead = (
            await session.execute(select(AcquisitionLead).where(AcquisitionLead.id == UUID(lead_id)))
        ).scalar_one_or_none()
        assert lead is not None
        assert lead.source == "website"
        assert lead.phone == "+966553078789"
        assert lead.segment == "restaurant_food"
        assert lead.lead_status == "NEW"
        events = (
            await session.execute(select(LeadEvent).where(LeadEvent.lead_id == lead.id))
        ).scalars().all()
        assert any(e.event_type == "captured" for e in events)


async def test_captured_lead_is_visible_in_acquisition_api(api) -> None:
    client, _maker = api
    created = (await client.post("/api/leads", json={"name": "متجر الأناقة", "phone": "0551112223"})).json()
    lead_id = created["lead_id"]

    listing = await client.get("/api/acquisition/leads")
    assert listing.status_code == 200
    ids = [l["id"] for l in listing.json()["leads"]]
    assert lead_id in ids

    # The owner overview must count the same canonical record.
    overview = await client.get("/api/owner/overview")
    assert overview.status_code == 200
    assert overview.json()["leads"]["total"] >= 1


async def test_acquisition_workflow_message_demo_and_followup(api) -> None:
    client, _maker = api
    created = (await client.post("/api/leads", json={"name": "مطعم الأصالة", "phone": "0553078789"})).json()
    lead_id = created["lead_id"]

    detail = await client.get(f"/api/acquisition/leads/{lead_id}")
    assert detail.status_code == 200
    assert detail.json()["draft"]["message"]
    assert detail.json()["draft"]["wa_link"].startswith("https://wa.me/966553078789")

    message = await client.post(f"/api/acquisition/leads/{lead_id}/message", json={"variant": "cold_intro"})
    assert message.status_code == 200
    assert message.json()["draft"]["message"]

    status = await client.post(f"/api/acquisition/leads/{lead_id}/status", json={"status": "CONTACTED"})
    assert status.status_code == 200
    assert status.json()["lead"]["lead_status"] == "CONTACTED"

    followup = await client.post(f"/api/acquisition/leads/{lead_id}/followup", json={"days": 3})
    assert followup.status_code == 200
    assert followup.json()["lead"]["next_followup_at"]

    demo = await client.get(f"/acquisition/leads/{lead_id}/demo")
    assert demo.status_code == 200
    assert "مطعم الأصالة" in demo.text

    campaign = await client.post("/api/acquisition/campaigns", json={"size": 5})
    assert campaign.status_code == 200


async def test_owner_status_endpoint_validates_status(api) -> None:
    client, _maker = api
    created = (await client.post("/api/leads", json={"name": "شركة الاختبار", "phone": "0500000000"})).json()
    bad = await client.post(f"/api/leads/{created['lead_id']}/status", json={"status": "NOT_A_STATUS"})
    assert bad.status_code == 400
    good = await client.post(f"/api/leads/{created['lead_id']}/status", json={"status": "WON"})
    assert good.status_code == 200


async def test_acquisition_pages_require_owner() -> None:
    from src.main import app

    engine, maker = await _make_engine()
    app.state.session_factory = maker
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # No cookie → redirected away from the dashboard, 401 from the API.
        page = await client.get("/acquisition", follow_redirects=False)
        assert page.status_code in (302, 307)
        listing = await client.get("/api/acquisition/leads")
        assert listing.status_code == 401
    await engine.dispose()
