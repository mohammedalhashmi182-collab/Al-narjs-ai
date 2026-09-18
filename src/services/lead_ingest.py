from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import xml.etree.ElementTree as ET

_XLSX_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# Gulf + common dialing codes we can confidently resolve.
_KNOWN_CC = {
    "966", "971", "973", "968", "965", "974", "962", "961", "964", "963",
    "967", "970", "972", "212", "213", "216", "218", "249", "20", "92",
    "91", "90", "880", "44", "1", "33", "49", "39", "34", "7", "994",
    "995", "998", "975",
}

HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "phone": ("caller id", "mobile (account)", "mobile", "phone", "phone number", "whatsapp", "tel", "جوال", "الهاتف", "رقم الجوال"),
    "email": ("email", "e-mail", "email address", "البريد", "البريد الإلكتروني"),
    "company": ("account", "company", "company name", "business", "business name", "store", "store name", "brand", "الشركة", "المؤسسة", "النشاط"),
    "contact_name": ("contact", "contact name", "name", "person", "full name", "customer", "الاسم", "اسم العميل"),
    "website": ("website", "url", "site", "domain", "web", "الموقع", "الرابط"),
    "industry": ("industry", "category", "sector", "type", "vertical", "المجال", "القطاع", "التصنيف"),
    "location": ("location", "city", "country", "region", "area", "address", "المدينة", "المنطقة", "الدولة", "العنوان"),
    "message": ("service request", "request", "message", "note", "notes", "comment", "details", "الطلب", "الملاحظات", "الرسالة"),
}

_INDUSTRY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ecommerce": ("store", "shop", "shopify", "salla", "متجر", "تجارة", "ecommerce", "e-commerce", "product", "منتج", "order", "طلب"),
    "social": ("instagram", "tiktok", "social", "سوشيال", "انستقرام", "إنستغرام", "تيك", "snapchat", "marketing", "تسويق", "ad", "إعلان"),
    "content": ("content", "article", "blog", "seo", "محتوى", "مقال", "مدونة", "كتابة", "copywriting"),
    "growth": ("consult", "growth", "strategy", "startup", "نمو", "استشار", "مشروع", "خطة", "business", "أعمال"),
}


# --------------------------------------------------------------------------
# Readers (stdlib only: xlsx = zipped XML, plus csv)
# --------------------------------------------------------------------------


@dataclass
class SheetData:
    sheet: str
    rows: list[list[str]] = field(default_factory=list)

    def iter_rows(self, values_only: bool = True):
        """Yield rows as tuples (openpyxl-compatible) so this stdlib reader can
        back the canonical importer without a third-party Excel dependency."""
        for row in self.rows:
            yield tuple(row)


def _col_index(ref: str) -> int:
    match = re.match(r"([A-Z]+)", ref or "")
    if not match:
        return 0
    value = 0
    for ch in match.group(1):
        value = value * 26 + (ord(ch) - 64)
    return value - 1


def _shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except (KeyError, ET.ParseError):
        return []
    out = []
    for si in root.findall(f"{_XLSX_NS}si"):
        out.append("".join(t.text or "" for t in si.iter(f"{_XLSX_NS}t")))
    return out


def _read_sheet_xml(zf: zipfile.ZipFile, path: str, shared: list[str]) -> list[list[str]]:
    root = ET.fromstring(zf.read(path))
    rows: list[list[str]] = []
    for row in root.iter(f"{_XLSX_NS}row"):
        cells: dict[int, str] = {}
        for cell in row.findall(f"{_XLSX_NS}c"):
            ctype = cell.get("t")
            vtag = cell.find(f"{_XLSX_NS}v")
            if ctype == "s" and vtag is not None and vtag.text is not None:
                idx = int(vtag.text)
                value = shared[idx] if 0 <= idx < len(shared) else ""
            elif ctype == "inlineStr":
                value = "".join(t.text or "" for t in cell.iter(f"{_XLSX_NS}t"))
            else:
                value = vtag.text if vtag is not None and vtag.text is not None else ""
            cells[_col_index(cell.get("r") or "")] = value.strip()
        if cells:
            width = max(cells) + 1
            rows.append([cells.get(i, "") for i in range(width)])
    return rows


def read_xlsx(path: str | Path) -> list[SheetData]:
    with zipfile.ZipFile(path) as zf:
        shared = _shared_strings(zf)
        try:
            workbook = ET.fromstring(zf.read("xl/workbook.xml"))
            names = [s.get("name") or f"sheet{i}" for i, s in enumerate(workbook.iter(f"{_XLSX_NS}sheet"))]
        except (KeyError, ET.ParseError):
            names = []
        sheets = sorted(
            (n for n in zf.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n)),
            key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[-1]).group(1)),
        )
        result: list[SheetData] = []
        for i, sheet_path in enumerate(sheets):
            name = names[i] if i < len(names) else sheet_path.rsplit("/", 1)[-1]
            result.append(SheetData(sheet=name, rows=_read_sheet_xml(zf, sheet_path, shared)))
        return result


def read_csv(path: str | Path) -> list[SheetData]:
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - latin-1 never fails
        text = raw.decode("latin-1", "ignore")
    reader = csv.reader(io.StringIO(text))
    rows = [[(c or "").strip() for c in row] for row in reader]
    return [SheetData(sheet="csv", rows=[r for r in rows if any(r)])]


def read_table(path: str | Path) -> list[SheetData]:
    suffix = Path(path).suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        return read_xlsx(path)
    if suffix in (".csv", ".txt"):
        return read_csv(path)
    raise ValueError(f"Unsupported lead file type: {suffix!r} (use .xlsx or .csv)")


# --------------------------------------------------------------------------
# Normalization helpers (pure, deterministic)
# --------------------------------------------------------------------------


def phone_digits(raw: str) -> str:
    return re.sub(r"\D", "", raw or "")


def normalize_phone(raw: str, default_cc: str = "966") -> Optional[str]:
    digits = phone_digits(raw)
    if not digits:
        return None
    if raw.strip().startswith("+"):
        return f"+{digits}" if len(digits) >= 8 else None
    if digits.startswith("00"):
        rest = digits[2:]
        return f"+{rest}" if len(rest) >= 8 else None
    if digits.startswith(default_cc) and len(digits) >= len(default_cc) + 8:
        return f"+{digits}"
    if digits.startswith("0"):
        stripped = digits.lstrip("0")
        if len(stripped) == 9 and stripped.startswith("5"):
            return f"+{default_cc}{stripped}"
        for cc in _KNOWN_CC:
            if stripped.startswith(cc) and len(stripped) >= len(cc) + 7:
                return f"+{stripped}"
        return None
    if len(digits) == 9 and digits.startswith("5"):
        return f"+{default_cc}{digits}"
    for cc in sorted(_KNOWN_CC, key=len, reverse=True):
        if digits.startswith(cc) and len(digits) >= len(cc) + 7:
            return f"+{digits}"
    return None


def normalize_email(raw: str) -> Optional[str]:
    value = (raw or "").strip().lower()
    if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
        return value
    return None


def normalize_website(raw: str) -> Optional[str]:
    value = (raw or "").strip()
    if not value or " " in value:
        return None
    if not re.match(r"^(https?://)?[a-z0-9.-]+\.[a-z]{2,}", value, re.IGNORECASE):
        return None
    return value if value.startswith("http") else f"https://{value}"


def looks_like_phone(value: str) -> bool:
    digits = phone_digits(value)
    return 8 <= len(digits) <= 15 and bool(re.match(r"^[\d+\s()\-]+$", value or ""))


def classify_industry(*texts: str) -> Optional[str]:
    haystack = " ".join(t.lower() for t in texts if t)
    for industry, keywords in _INDUSTRY_KEYWORDS.items():
        if any(k in haystack for k in keywords):
            return industry
    return None


def _canonical(header: str) -> Optional[str]:
    key = (header or "").strip().lower()
    if not key:
        return None
    for canonical, aliases in HEADER_ALIASES.items():
        if key in aliases:
            return canonical
    for canonical, aliases in HEADER_ALIASES.items():
        if any(alias in key for alias in aliases):
            return canonical
    return None


def detect_header_row(rows: list[list[str]]) -> Optional[int]:
    for i, row in enumerate(rows[:10]):
        if any(_canonical(c) for c in row):
            return i
    return None


def map_columns(header: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(header):
        canonical = _canonical(cell)
        if canonical and canonical not in mapping:
            mapping[canonical] = idx
    # Heuristic pass over sample values when headers are absent/generic.
    return mapping


def _map_by_values(rows: list[list[str]], width: int) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for col in range(width):
        samples = [r[col] for r in rows[:50] if col < len(r)]
        nonempty = [s for s in samples if s]
        if not nonempty:
            continue
        phone_ratio = sum(looks_like_phone(s) for s in nonempty) / len(nonempty)
        email_ratio = sum(bool(normalize_email(s)) for s in nonempty) / len(nonempty)
        if phone_ratio >= 0.6 and "phone" not in mapping:
            mapping["phone"] = col
        elif email_ratio >= 0.6 and "email" not in mapping:
            mapping["email"] = col
    return mapping


@dataclass
class NormalizedLead:
    company: Optional[str]
    contact_name: Optional[str]
    phone: Optional[str]
    phone_raw: str
    email: Optional[str]
    website: Optional[str]
    industry: Optional[str]
    location: Optional[str]
    message: Optional[str]
    source: str
    source_ref: str
    row_index: int
    raw: dict

    @property
    def dedupe_key(self) -> str:
        if self.phone:
            return f"phone:{self.phone}"
        if self.email:
            return f"email:{self.email}"
        basis = f"{self.company or ''}|{self.contact_name or ''}|{self.phone_raw}".lower()
        return "hash:" + hashlib.sha256(basis.encode()).hexdigest()[:32]

    @property
    def display_name(self) -> str:
        return self.company or self.contact_name or self.phone or self.email or "Unknown lead"


def normalize_sheet(sheet: SheetData, source: str, source_ref: str) -> list[NormalizedLead]:
    rows = [r for r in sheet.rows if any((c or "").strip() for c in r)]
    if not rows:
        return []
    width = max(len(r) for r in rows)

    header_idx = detect_header_row(rows)
    if header_idx is not None:
        header = rows[header_idx]
        mapping = map_columns(header)
        data_rows = rows[header_idx + 1:]
    else:
        mapping = {}
        data_rows = rows

    mapping = {**mapping, **_map_by_values(data_rows, width)}

    # Positional fallback for the common "Account, <id>, Mobile, Request" layout.
    if "phone" not in mapping:
        for col in range(width):
            samples = [r[col] for r in data_rows[:50] if col < len(r)]
            if samples and sum(looks_like_phone(s) for s in samples) / max(1, len([s for s in samples if s])) >= 0.6:
                mapping["phone"] = col
                if "company" not in mapping and col > 0:
                    mapping["company"] = 0
                break

    out: list[NormalizedLead] = []
    for offset, row in enumerate(data_rows):
        cells = [(row[i] if i < len(row) else "").strip() for i in range(width)]
        get = lambda name: cells[mapping[name]] if name in mapping and mapping[name] < len(cells) else ""

        phone_raw = get("phone")
        phone = normalize_phone(phone_raw)
        email = normalize_email(get("email"))
        company = get("company") or None
        contact = get("contact_name") or None
        message = get("message") or None

        if not any([phone, email, company, contact, message]):
            continue

        industry = get("industry") or classify_industry(company or "", message or "")

        out.append(NormalizedLead(
            company=company,
            contact_name=contact,
            phone=phone,
            phone_raw=phone_raw,
            email=email,
            website=normalize_website(get("website")),
            industry=industry,
            location=get("location") or None,
            message=message,
            source=source,
            source_ref=source_ref,
            row_index=header_idx + 1 + offset if header_idx is not None else offset,
            raw={f"col{i}": c for i, c in enumerate(cells) if c},
        ))
    return out


def normalize_file(path: str | Path, source: Optional[str] = None) -> list[NormalizedLead]:
    p = Path(path)
    origin = source or p.name
    records: list[NormalizedLead] = []
    for sheet in read_table(p):
        records.extend(normalize_sheet(sheet, source=origin, source_ref=f"{p.name}#{sheet.sheet}"))
    return records
