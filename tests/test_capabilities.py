"""Forecast, Arabic OCR, style memory, evaluation loop, and the cron gate."""

from __future__ import annotations

import base64
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

import src.models  # noqa: F401  registers capability tables
from src.db.session import Base
from src.main import app
from src.services import catalog
from src.services.capabilities import eval_loop, forecast as forecast_mod
from src.services.capabilities import ocr as ocr_mod
from src.services.capabilities import style_memory
from src.services.capabilities.eval_loop import run_eval_loop
from src.services.capabilities.forecast import PlanInput, build_forecast
from src.services.capabilities.ocr import parse_fields, read_document, redact_sensitive


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _pdf(text: str) -> bytes:
    lines = text.split("\n")
    commands = ["BT", "/F1 12 Tf", "50 780 Td"]
    for index, line in enumerate(lines):
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if index:
            commands.append("0 -16 Td")
        commands.append(f"({safe}) Tj")
    commands.append("ET")
    stream = ("\n".join(commands) + "\n").encode("latin-1")
    bodies = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(bodies, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(bodies) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer << /Size {len(bodies) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return bytes(out)


def test_new_agents_are_in_the_catalog_and_yaml():
    for slug, number in (
        ("financial_forecast", "AG-036"),
        ("arabic_ocr", "AG-037"),
        ("style_memory", "AG-038"),
        ("evaluation_loop", "AG-039"),
    ):
        employee = catalog.EMPLOYEES[slug]
        assert employee["no"] == number
        assert employee["title_en"]
        assert employee["workspace"].startswith("/capabilities/")
    assert catalog.AGENT_COUNT == 39
    assert "client_style_profiles" in Base.metadata.tables
    assert "capability_eval_logs" in Base.metadata.tables


def test_forecast_three_scenarios_break_even_and_formula_workbook():
    payload = build_forecast(
        [PlanInput("Growth", 100, 10)],
        monthly_growth=0.0,
        monthly_churn=0.0,
        fixed_costs_sar=500,
        variable_cost_per_customer_sar=20,
        vat_rate=0.15,
        horizon_months=3,
    )
    assert payload["estimate"] is True
    assert "تقدير" in payload["note_ar"]
    assert "estimate" in payload["note_en"].lower()
    base = payload["scenarios"]["base"]
    assert base["break_even_month"] == 1
    assert base["months"][0]["vat_sar"] == 150
    assert base["months"][0]["profit_ex_vat_sar"] == 300
    assert set(payload["scenarios"]) == {"conservative", "base", "optimistic"}

    losing = build_forecast(
        [PlanInput("Growth", 100, 10)],
        monthly_growth=0.0,
        monthly_churn=0.0,
        fixed_costs_sar=5000,
        variable_cost_per_customer_sar=20,
        vat_rate=0.15,
        horizon_months=4,
    )
    assert losing["scenarios"]["base"]["break_even_month"] is None

    book = load_workbook(BytesIO(base64.b64decode(payload["xlsx_base64"])))
    assert book["Assumptions"]["B10"].value == 0.15
    assert book["Assumptions"]["C4"].value == "estimate"
    formula = book["Base"]["B4"].value
    assert formula.startswith("=MAX(0,Assumptions!$B$4*")
    assert "MIN(0.95" in formula
    assert str(book["Base"]["C4"].value).startswith("=B4*Assumptions!")


def test_forecast_rejects_a_horizon_past_the_configured_cap(monkeypatch):
    monkeypatch.setenv("CAPABILITY_FORECAST_MAX_HORIZON", "6")
    with pytest.raises(forecast_mod.ForecastError):
        build_forecast(
            [PlanInput("P", 10, 1)],
            monthly_growth=0,
            monthly_churn=0,
            fixed_costs_sar=0,
            variable_cost_per_customer_sar=0,
            horizon_months=12,
        )


def test_arabic_invoice_fields_flags_and_redaction():
    text = (
        "فاتورة ضريبية\n"
        "المورد: شركة النخيل للتجارة\n"
        "التاريخ: 2026-03-15\n"
        "الإجمالي قبل الضريبة: 1000\n"
        "ضريبة القيمة المضافة 15%: 150\n"
        "الإجمالي شامل الضريبة: 1150\n"
        "رقم الهوية: 1098765432\n"
        "بطاقة: 4111111111111111\n"
    )
    redacted = redact_sensitive(text)
    assert "1098765432" not in redacted
    assert "4111111111111111" not in redacted
    assert "[REDACTED_NATIONAL_ID]" in redacted
    assert "[REDACTED_CARD]" in redacted
    parsed = parse_fields(redacted)
    assert parsed["fields"]["vendor"]["value"] == "شركة النخيل للتجارة"
    assert parsed["fields"]["date"]["value"] == "2026-03-15"
    assert parsed["fields"]["amount_ex_vat"]["value"] == 1000
    assert parsed["fields"]["vat"]["value"] == 150
    assert parsed["fields"]["total"]["value"] == 1150
    assert parsed["fields"]["vendor"]["low_confidence"] is False
    missing = parse_fields("ملاحظة بلا حقول")
    assert "vendor" in missing["low_confidence_fields"]


@pytest.mark.asyncio
async def test_pdf_upload_redacts_and_does_not_keep_the_card():
    pdf = _pdf(
        "Vendor: Palm Trading\n"
        "Date: 2026-03-15\n"
        "Subtotal: 1000\n"
        "VAT 15%: 150\n"
        "Total: 1150\n"
        "ID: 1098765432\n"
        "Card: 4111111111111111\n"
    )
    result = await read_document(pdf, "application/pdf")
    blob = str(result)
    assert "4111111111111111" not in blob
    assert "1098765432" not in blob
    assert result["stored"] is False
    assert result["fields"]["vendor"]["value"] == "Palm Trading"
    assert result["fields"]["total"]["value"] == 1150
    sheet = load_workbook(BytesIO(base64.b64decode(result["xlsx_base64"])))["Extracted"]
    values = " ".join(str(cell.value) for row in sheet.iter_rows() for cell in row)
    assert "4111" not in values
    assert "1098765432" not in values


@pytest.mark.asyncio
async def test_image_without_vision_does_not_invent_fields(monkeypatch):
    monkeypatch.delenv("OCR_VISION_ENABLED", raising=False)
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
    )
    result = await read_document(png, "image/png")
    assert result["warning"] == "vision_disabled"
    assert result["fields"]["vendor"]["value"] is None
    assert result["stored"] is False


def test_style_memory_learns_and_renders_a_prompt():
    style_memory.clear_memory()
    profile = style_memory.StyleProfile(
        client_key="client-1",
        brand_ar="النخيل",
        brand_en="Nakheel",
        register="msa",
        tone="هادئ",
        colours="#000",
        fonts="Cairo",
        signature="مع التحية",
    )
    learned = style_memory.learn_from_edit(
        profile,
        "نكتب النخيل بشكل رسمي",
        "نكتب النخيل الحين بشكل ودي",
    )
    assert learned.register == "saudi"
    block = style_memory.render_block(style_memory.recall("client-1"))
    assert "النخيل" in block
    assert "Nakheel" in block
    assert "Saudi dialect" in block
    assert "Cairo" in block
    style_memory.clear_memory()


@pytest.mark.asyncio
async def test_style_block_is_injected_into_the_agent_prompt():
    style_memory.clear_memory()
    style_memory.remember(
        style_memory.StyleProfile(client_key="client-9", brand_ar="الواحة", brand_en="Alwaha", register="saudi")
    )

    class Provider:
        def __init__(self):
            self.request = None

        async def complete(self, spec, request):
            self.request = request
            return SimpleNamespace(content="تم إعداد المسودة حسب الأسلوب المطلوب للعميل.", model="m", tokens_used=1, latency_ms=1)

    from src.services import agent_runtime

    provider = Provider()
    agent = SimpleNamespace(slug="email_writer", category="content", default_model="fake:model", default_parameters={})
    result = await agent_runtime.execute(
        provider,
        agent,
        prompt="اكتب رسالة قصيرة",
        system_prompt="أنت كاتب بريد.",
        locale="ar",
        metadata={"client_key": "client-9"},
        quality_gate=False,
    )
    assert "الواحة" in provider.request.system_prompt
    assert "Alwaha" in provider.request.system_prompt
    assert result.content
    style_memory.clear_memory()


def test_eval_loop_revises_up_to_three_rounds_and_logs():
    eval_loop._LOGS.clear()
    good = (
        "اعتمد هذا النص على مدخلات العميل فقط، وهو تقدير وليس نتيجة فعلية.\n"
        "المصدر هو الأرقام التي أدخلها العميل، ولا توجد نسبة سوقية مخترعة.\n"
        "الخطوة التالية مراجعة الافتراض مع المحاسب قبل الاعتماد."
    )

    def fix(text, issues):
        del text, issues
        return good

    fixed = run_eval_loop("TODO أكمل لاحقاً", locale="ar", revise=fix, agent_slug="evaluation_loop", source="test")
    assert fixed.passed is True
    assert fixed.revisions == 1
    assert "TODO" not in fixed.text
    assert eval_loop.recent_logs()

    calls = {"n": 0}

    def never(text, issues):
        del issues
        calls["n"] += 1
        return text + str(calls["n"])

    stuck = run_eval_loop("x", locale="ar", revise=never, max_rounds=3, source="test")
    assert stuck.passed is False
    assert stuck.revisions == 3
    assert calls["n"] == 3


def test_passing_arabic_draft_is_not_rewritten():
    text = (
        "## تحليل مصحح\n"
        "اعتمد هذا التحليل فقط على بيانات العميل والمصادر المرفقة. "
        "لا توجد أرقام سوق مؤكدة في المدخلات، لذلك لن أختلق حجماً للسوق.\n"
        "الخطوة الأولى هي جمع حجم الطلب، المنافسين، الأسعار والقنوات من المصادر المتاحة، "
        "ثم فصل الحقائق عن الافتراضات وبناء توصيات قابلة للقياس."
    )
    outcome = run_eval_loop(text, locale="ar", source="test")
    assert outcome.passed is True
    assert outcome.revisions == 0
    assert outcome.text == text


def test_workspaces_render_in_arabic_and_english(client: TestClient):
    arabic = client.get("/ar/capabilities/forecast")
    english = client.get("/en/capabilities/forecast")
    assert arabic.status_code == 200
    assert english.status_code == 200
    assert "محلل التوقع المالي" in arabic.text
    assert "Financial Forecast Analyst" in english.text
    assert "كل السيناريوهات" not in english.text
    assert "tel:" not in english.text and "0540799266" not in english.text
    for path in ("/ar/capabilities/ocr", "/en/capabilities/ocr", "/ar/capabilities/style", "/en/capabilities/style", "/ar/capabilities/eval", "/en/capabilities/eval"):
        assert client.get(path).status_code == 200, path
    agent = client.get("/ar/ai-agent/financial_forecast")
    assert agent.status_code == 200
    assert "/ar/capabilities/forecast" in agent.text


def test_forecast_page_shows_the_estimate_table(client: TestClient):
    response = client.post(
        "/ar/capabilities/forecast",
        data={
            "plan_name": "Plan",
            "price_sar": "100",
            "customers": "10",
            "growth_percent": "0",
            "churn_percent": "0",
            "fixed_costs_sar": "500",
            "variable_cost_sar": "20",
            "vat_percent": "15",
            "horizon_months": "3",
        },
    )
    assert response.status_code == 200
    assert "تقدير" in response.text
    assert "capDownload" in response.text


def test_style_form_keeps_the_chosen_register(client: TestClient):
    response = client.post(
        "/ar/capabilities/style",
        data={"brand_ar": "النخيل", "brand_en": "Nakheel", "voice": "saudi"},
    )
    assert response.status_code == 200
    assert "Saudi dialect" in response.text
    assert "النخيل" in response.text


def test_style_save_requires_a_portal_session(client: TestClient):
    response = client.put(
        "/api/capabilities/style/not-a-project",
        json={"brand_en": "Nakheel", "register": "msa"},
    )
    assert response.status_code == 401


def test_cron_is_closed_without_a_secret_and_open_with_the_header(client: TestClient, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "")
    closed = client.post("/webhooks/cron/daily")
    assert closed.status_code == 503

    monkeypatch.setenv("CRON_SECRET", "cron-test-secret")
    denied = client.post("/webhooks/cron/daily", headers={"X-Cron-Secret": "wrong"})
    assert denied.status_code == 401
    allowed = client.post("/webhooks/cron/daily", headers={"X-Cron-Secret": "cron-test-secret"})
    assert allowed.status_code == 200
    body = allowed.json()
    assert body["agents_in_catalog"] == catalog.AGENT_COUNT
    assert "cron-test-secret" not in allowed.text
    bearer = client.get("/webhooks/cron/daily", headers={"Authorization": "Bearer cron-test-secret"})
    assert bearer.status_code == 200
