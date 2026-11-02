"""Arabic (and bilingual) business-document extraction.

Text-layer PDFs are read locally. Images stay unread unless
``OCR_VISION_ENABLED`` is on and ``GEMINI_API_KEY`` is set. Card numbers and
national IDs are replaced before the result is returned and are never written
to disk or to the database.
"""

from __future__ import annotations

import base64
import os
import re
from io import BytesIO

import httpx
from openpyxl import Workbook
from pypdf import PdfReader

from src.core.pii_mask import PATTERNS
from src.services.capabilities.config import ocr_max_bytes, ocr_vision_enabled

LOW_CONFIDENCE = 0.7
ALLOWED_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
}

_VENDOR = re.compile(
    r"(?:المورد|البائع|اسم\s+المنشأة|vendor|supplier|from)\s*[:：\-]?\s*(.+)",
    re.IGNORECASE,
)
_DATE = re.compile(
    r"(?:التاريخ|date)\s*[:：\-]?\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})",
    re.IGNORECASE,
)
_BARE_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_MONEY = r"([0-9][0-9\u0660-\u0669,\.]*)"
_SUBTOTAL = re.compile(
    rf"(?:الإجمالي\s*قبل(?:\s*الضريبة)?|قبل\s*الضريبة|المجموع\s*قبل|subtotal|amount\s*ex)\s*[:：\-]?\s*{_MONEY}",
    re.IGNORECASE,
)
# «قبل الضريبة» is the subtotal label, not the VAT amount.
_VAT = re.compile(
    rf"(?<!قبل\s)(?:ضريبة\s*القيمة\s*المضافة|القيمة\s*المضافة|vat)\s*(?:\d+(?:[.,]\d+)?\s*%)?\s*[:：\-]?\s*{_MONEY}",
    re.IGNORECASE,
)
_TOTAL = re.compile(
    rf"(?:الإجمالي\s*شامل(?:\s*الضريبة)?|الإجمالي|المجموع\s*النهائي|grand\s*total|total)\s*[:：\-]?\s*{_MONEY}",
    re.IGNORECASE,
)


class OcrError(ValueError):
    pass


def redact_sensitive(text: str) -> str:
    """Drop card numbers and national IDs. The original digits are not kept."""
    if not text:
        return ""
    for kind, pattern in PATTERNS:
        if kind in {"CARD", "NATIONAL_ID"}:
            text = pattern.sub(f"[REDACTED_{kind}]", text)
    return text


def _number(raw: str | None) -> float | None:
    if not raw:
        return None
    digits = raw.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    digits = digits.replace(",", "")
    try:
        return round(float(digits), 2)
    except ValueError:
        return None


def _field(value, confidence: float, source: str) -> dict:
    conf = round(max(0.0, min(1.0, confidence)), 2)
    return {
        "value": value,
        "confidence": conf,
        "low_confidence": conf < LOW_CONFIDENCE,
        "source": source,
    }


def parse_fields(text: str) -> dict:
    vendor_m = _VENDOR.search(text)
    vendor = vendor_m.group(1).strip().splitlines()[0][:160] if vendor_m else None
    date_m = _DATE.search(text) or _BARE_DATE.search(text)
    date = date_m.group(1) if date_m else None
    sub = _SUBTOTAL.search(text)
    vat = _VAT.search(text)
    total = _TOTAL.search(text)
    # A later "الإجمالي" can also match the subtotal label's tail. Prefer the
    # last total-like hit when several exist, and ignore values already redacted.
    total_hits = [m for m in _TOTAL.finditer(text) if "[REDACTED_" not in m.group(0)]
    total = total_hits[-1] if total_hits else total
    fields = {
        "vendor": _field(vendor, 0.9 if vendor else 0.3, "label" if vendor else "missing"),
        "date": _field(date, 0.92 if date_m and date_m.re is _DATE else (0.55 if date else 0.3), "label" if date else "missing"),
        "amount_ex_vat": _field(_number(sub.group(1)) if sub else None, 0.9 if sub else 0.25, "label" if sub else "missing"),
        "vat": _field(_number(vat.group(1)) if vat else None, 0.9 if vat else 0.25, "label" if vat else "missing"),
        "total": _field(_number(total.group(1)) if total else None, 0.88 if total else 0.25, "label" if total else "missing"),
    }
    low = [name for name, item in fields.items() if item["low_confidence"] or item["value"] in (None, "")]
    return {"fields": fields, "low_confidence_fields": low}


def extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts).strip()


async def vision_text(data: bytes, mime: str) -> str:
    """Optional Gemini vision. Returns "" when the switch or the key is absent."""
    if not ocr_vision_enabled():
        return ""
    key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not key:
        return ""
    model = (os.getenv("GEMINI_DEFAULT_MODEL") or "gemini-3.6-flash").strip()
    base = (os.getenv("GEMINI_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta/openai").rstrip("/")
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Extract the visible text of this Arabic or bilingual business "
                            "document. Return plain text only. Do not invent missing fields."
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"}},
                ],
            }
        ],
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json=payload,
        )
        response.raise_for_status()
        body = response.json()
    return str(((body.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()


def _xlsx(parsed: dict) -> str:
    wb = Workbook()
    sheet = wb.active
    sheet.title = "Extracted"
    sheet["A1"] = "Sensitive card numbers and national IDs were removed and were not stored."
    sheet["A2"] = "أُزيلت أرقام البطاقات والهويات الوطنية ولم تُخزَّن."
    for col, header in enumerate(["field", "value", "confidence", "low_confidence", "source"], 1):
        sheet.cell(4, col, header)
    for row, (name, item) in enumerate(parsed["fields"].items(), 5):
        sheet.cell(row, 1, name)
        sheet.cell(row, 2, "" if item["value"] is None else item["value"])
        sheet.cell(row, 3, item["confidence"])
        sheet.cell(row, 4, "yes" if item["low_confidence"] else "no")
        sheet.cell(row, 5, item["source"])
    buffer = BytesIO()
    wb.save(buffer)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


async def read_document(data: bytes, content_type: str) -> dict:
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    if mime not in ALLOWED_TYPES:
        raise OcrError("upload must be a PDF or an image")
    if not data:
        raise OcrError("empty file")
    if len(data) > ocr_max_bytes():
        raise OcrError("file exceeds the upload limit")

    warning = ""
    engine = "pdf-text"
    if mime == "application/pdf":
        try:
            text = extract_pdf_text(data)
        except Exception as exc:  # noqa: BLE001 - return a clean failure, keep no bytes
            raise OcrError("could not read this PDF") from exc
        if not text:
            warning = "pdf_has_no_text_layer"
    else:
        engine = "vision" if ocr_vision_enabled() else "unavailable"
        try:
            text = await vision_text(data, mime if mime != "image/jpg" else "image/jpeg")
        except Exception:  # noqa: BLE001 - vision is optional
            text = ""
            warning = "vision_failed"
        if not text and not warning:
            warning = "vision_disabled" if not ocr_vision_enabled() else "no_text"

    redacted = redact_sensitive(text)
    parsed = parse_fields(redacted)
    # The upload itself is not retained; only the redacted extraction is returned.
    return {
        "engine": engine,
        "warning": warning,
        "text": redacted,
        "fields": parsed["fields"],
        "low_confidence_fields": parsed["low_confidence_fields"],
        "sensitive_removed": "[REDACTED_CARD]" in redacted or "[REDACTED_NATIONAL_ID]" in redacted,
        "stored": False,
        "xlsx_base64": _xlsx(parsed),
    }
