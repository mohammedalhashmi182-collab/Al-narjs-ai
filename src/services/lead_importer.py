"""Excel ingestion for the customer-acquisition system.

Reads the historical invoice/quotations workbook, normalizes every row,
deduplicates companies conservatively, enriches with segment + explainable
priority, and persists to the existing SQLAlchemy database.

The original row is always preserved in ``raw_data``; imports are idempotent and
re-importing updates derived fields without destroying sales activity.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Optional

from src.services.lead_normalize import (
    clean_text,
    company_name_key,
    is_valid_email,
    is_valid_phone,
    is_whatsapp_capable,
    normalize_company_name,
    normalize_email,
    normalize_phone,
    parse_date,
    parse_int,
)
from src.services.lead_priority import score_lead
from src.services.lead_segmentation import classify, suggest_package
from src.utils.logger import get_logger

logger = get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CAMPAIGN_DIR = DATA_DIR / "campaigns"

# The workbook mixes three sheet types:
#   * year sheets (2020-2025)      -> companies that purchased that year (all ✔)
#   * "quotations without purchase"-> quotes that never converted (all ✖)
#   * "Sheet2"                     -> a master list that holds *both* ✔ and ✖ rows
# The Op/Cl marker (✔ = purchased, ✖ = no purchase) is the per-row source of
# truth; the sheet only supplies a fallback when the marker is missing.
QUOTATION_SHEETS = {"quotations without purchase"}
MASTER_SHEETS = {"sheet2"}
CUSTOMER_SHEETS = {"2020", "2021", "2022", "2023", "2024", "2025", "2026"}

MAX_EMPTY_RUN = 50
MAX_RAW_ROWS_PER_LEAD = 8


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

def _resolve_columns(header: Iterable[Any]) -> dict[str, Any]:
    cols: dict[str, Any] = {
        "name": None,
        "code": None,
        "date": None,
        "opcl": None,
        "mobile": [],
        "email": None,
        "invoices": None,
        "salesman": None,
        "customer_count": None,
    }
    for idx, raw in enumerate(header or []):
        h = clean_text(raw).lower()
        if not h:
            continue
        if "name" in h and cols["name"] is None:
            cols["name"] = idx
        elif "customer" in h and "count" not in h and "of customers" not in h and "عدد" not in h and cols["code"] is None:
            cols["code"] = idx
        elif ("date" in h) and cols["date"] is None:
            cols["date"] = idx
        elif h.startswith("op") and cols["opcl"] is None:
            cols["opcl"] = idx
        elif "mobile" in h:
            cols["mobile"].append(idx)
        elif "email" in h and cols["email"] is None:
            cols["email"] = idx
        elif "invoice" in h and ("number" in h) and cols["invoices"] is None:
            cols["invoices"] = idx
        elif "salesman" in h and cols["salesman"] is None:
            cols["salesman"] = idx
        elif ("count" in h or "عدد" in h) and cols["customer_count"] is None:
            cols["customer_count"] = idx
    return cols


def _cell(row: tuple, idx: Optional[int]) -> Any:
    if idx is None or idx >= len(row):
        return None
    return row[idx]


_PURCHASED_MARKS = {"✔", "✓", "v"}
_DECLINED_MARKS = {"✖", "✕", "x"}


def sheet_kind(sheet_name: str) -> str:
    name = sheet_name.strip().lower()
    if name in QUOTATION_SHEETS:
        return "quotation"
    if name in MASTER_SHEETS:
        return "mixed"
    return "customer"


def _read_marker(opcl: str) -> Optional[bool]:
    """Return True when purchased, False when declined, None when unknown."""
    value = (opcl or "").strip().lower()
    if not value:
        return None
    if value in _PURCHASED_MARKS or value.startswith("op"):
        return True
    if value in _DECLINED_MARKS or value.startswith("cl"):
        return False
    return None


def read_sheet(ws, sheet_name: str) -> list[dict]:
    """Read one worksheet into normalized raw records, stopping at trailing blanks."""
    rows = ws.iter_rows(values_only=True)
    try:
        header = next(rows)
    except StopIteration:
        return []

    cols = _resolve_columns(header)
    kind = sheet_kind(sheet_name)
    records: list[dict] = []
    empty_run = 0
    seen_data = False

    for row in rows:
        if not any(v not in (None, "") for v in row):
            empty_run += 1
            if seen_data and empty_run >= MAX_EMPTY_RUN:
                break
            continue
        empty_run = 0
        seen_data = True

        company_name = normalize_company_name(_cell(row, cols["name"]))
        if not company_name:
            continue

        # Consider every mobile column; prefer a WhatsApp-capable number and
        # never accept a fabricated one. The raw value is kept for audit.
        phone_candidates = []
        for midx in cols["mobile"]:
            candidate = clean_text(_cell(row, midx))
            if candidate and set(re.sub(r"\D", "", candidate) or "0") != {"0"}:
                phone_candidates.append(candidate)

        phone_raw = phone_candidates[0] if phone_candidates else ""
        phone = None
        for wanted in (True, False):
            for candidate in phone_candidates:
                normalized = normalize_phone(candidate)
                if normalized and is_whatsapp_capable(normalized) == wanted:
                    phone, phone_raw = normalized, candidate
                    break
            if phone:
                break

        email_raw = clean_text(_cell(row, cols["email"]))
        email = normalize_email(email_raw)

        opcl = clean_text(_cell(row, cols["opcl"]))
        purchased = _read_marker(opcl)
        is_open = purchased is True

        if kind == "quotation":
            has_purchased, has_quote = False, True
        elif kind == "mixed":
            has_purchased = purchased is True
            has_quote = purchased is False
        else:
            has_purchased, has_quote = True, purchased is False

        last_date = parse_date(_cell(row, cols["date"]))
        invoice_count = parse_int(_cell(row, cols["invoices"]))
        sales_rep = clean_text(_cell(row, cols["salesman"]))
        customer_count = parse_int(_cell(row, cols["customer_count"]))
        code = clean_text(_cell(row, cols["code"]))

        records.append({
            "company_name": company_name,
            "name_key": company_name_key(company_name),
            "contact_name": None,
            "phone": phone,
            "phone_raw": phone_raw,
            "email": email or None,
            "email_raw": email_raw,
            "source": "excel_import",
            "source_sheet": sheet_name,
            "kind": kind,
            "source_customer_code": code,
            "historical_customer": has_purchased,
            "quotation_without_purchase": has_quote,
            "last_activity": last_date.isoformat() if last_date else None,
            "invoice_count": invoice_count,
            "customer_count": customer_count,
            "sales_representative": sales_rep,
            "op_cl": opcl,
            "is_open": is_open,
            "raw": {
                "sheet": sheet_name,
                "code": code,
                "name": company_name,
                "date": last_date.isoformat() if last_date else None,
                "op_cl": opcl,
                "phone_raw": phone_raw,
                "email_raw": email_raw,
                "invoices": invoice_count,
                "salesman": sales_rep,
            },
        })

    return records


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def merge_records(records: list[dict]) -> list[dict]:
    """Conservatively merge duplicate rows into unique companies.

    Merges on identical phone or email. Falls back to company-name matching only
    when at least one side has no valid phone — never merging two records that
    carry different valid phones.
    """
    n = len(records)
    if n == 0:
        return []

    uf = _UnionFind(n)
    phone_first: dict[str, int] = {}
    email_first: dict[str, int] = {}
    name_first: dict[str, int] = {}

    for i, rec in enumerate(records):
        phone = rec.get("phone")
        if phone:
            if phone in phone_first:
                uf.union(i, phone_first[phone])
            else:
                phone_first[phone] = i
        email = rec.get("email")
        if email and is_valid_email(email):
            if email in email_first:
                uf.union(i, email_first[email])
            else:
                email_first[email] = i

    for i, rec in enumerate(records):
        key = rec.get("name_key") or ""
        if len(key) < 3:
            continue
        if key in name_first:
            j = name_first[key]
            if not records[i].get("phone") or not records[j].get("phone"):
                uf.union(i, j)
        else:
            name_first[key] = i

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[uf.find(i)].append(i)

    return [_merge_group([records[i] for i in idxs]) for idxs in groups.values()]


def _better_phone(candidates: list[str]) -> Optional[str]:
    ranked = sorted(
        {p for p in candidates if p},
        key=lambda p: (is_whatsapp_capable(p), is_valid_phone(p), p),
        reverse=True,
    )
    return ranked[0] if ranked else None


def _merge_group(group: list[dict]) -> dict:
    company_name = max((r["company_name"] for r in group), key=len)
    phones = [r.get("phone") for r in group]
    phone = _better_phone(phones)
    valid_emails = [r.get("email") for r in group if is_valid_email(r.get("email"))]
    email = valid_emails[0] if valid_emails else next((r.get("email") for r in group if r.get("email")), None)

    dates = [parse_date(r.get("last_activity")) for r in group]
    dates = [d for d in dates if d]
    last_activity = max(dates) if dates else None

    sales_reps = [r.get("sales_representative") for r in group if r.get("sales_representative")]
    sheets = sorted({r["source_sheet"] for r in group})
    codes = sorted({r["source_customer_code"] for r in group if r.get("source_customer_code")})
    order = sorted(group, key=lambda r: r.get("source_sheet", ""))
    phone_raw = next((r["phone_raw"] for r in order if r.get("phone_raw")), None)

    return {
        "company_name": company_name,
        "name_key": company_name_key(company_name),
        "contact_name": None,
        "phone": phone,
        "phone_raw": phone_raw,
        "email": email,
        "source": "excel_import",
        "source_sheets": sheets,
        "source_sheet": sheets[-1] if sheets else None,
        "source_customer_codes": codes,
        "historical_customer": any(r.get("historical_customer") for r in group),
        "quotation_without_purchase": any(r.get("quotation_without_purchase") for r in group),
        "last_activity": last_activity.isoformat() if last_activity else None,
        "invoice_count": max((r.get("invoice_count") or 0) for r in group),
        "sales_representative": sales_reps[0] if sales_reps else None,
        "record_count": len(group),
        "raw_rows": [r["raw"] for r in group[:MAX_RAW_ROWS_PER_LEAD]],
    }


def enrich_lead(lead: dict) -> dict:
    segment, reason = classify(lead.get("company_name"))
    result = score_lead(
        company_name=lead.get("company_name", ""),
        contact_name=lead.get("contact_name"),
        phone=lead.get("phone"),
        email=lead.get("email"),
        historical_customer=bool(lead.get("historical_customer")),
        quotation_without_purchase=bool(lead.get("quotation_without_purchase")),
        last_activity=lead.get("last_activity"),
        invoice_count=lead.get("invoice_count") or 0,
        segment=segment,
    )
    lead.update({
        "segment": segment,
        "segment_reason": reason,
        "suggested_package": suggest_package(segment),
        "priority": result.priority,
        "priority_score": result.score,
        "priority_reason": result.reasons,
        "lead_status": "NEW",
        "outreach_status": "NOT_STARTED",
    })
    return lead


def dedup_key(lead: dict) -> str:
    if lead.get("phone") and is_valid_phone(lead["phone"]):
        return f"p:{lead['phone']}"
    if is_valid_email(lead.get("email")):
        return f"e:{lead['email']}"
    return f"n:{lead.get('name_key') or lead.get('company_name', '')}"


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def compute_stats(raw_records: list[dict], leads: list[dict]) -> dict:
    # Only the year sheets represent annual customer activity; Sheet2 duplicates
    # those dates and the quotations sheet has none, so counting every raw row
    # would double the totals.
    by_year: dict[str, int] = defaultdict(int)
    for rec in raw_records:
        if rec.get("kind") != "customer":
            continue
        year = (rec.get("last_activity") or "")[:4]
        if year.isdigit():
            by_year[year] += 1

    phones = [l["phone"] for l in leads if l.get("phone")]
    valid_phones = [p for p in phones if is_valid_phone(p)]
    wa = [p for p in phones if is_whatsapp_capable(p)]
    emails = [l["email"] for l in leads if is_valid_email(l.get("email"))]

    segments: dict[str, int] = defaultdict(int)
    priorities: dict[str, int] = defaultdict(int)
    for lead in leads:
        segments[lead.get("segment", "unknown")] += 1
        priorities[lead.get("priority", "LOW")] += 1

    return {
        "total_raw_records": len(raw_records),
        "unique_companies": len(leads),
        "duplicate_records": len(raw_records) - len(leads),
        "unique_phones": len(set(phones)),
        "valid_phones": len(valid_phones),
        "whatsapp_capable_numbers": len(wa),
        "emails": len(emails),
        "historical_customers": sum(1 for l in leads if l.get("historical_customer")),
        "quotations_without_purchase": sum(1 for l in leads if l.get("quotation_without_purchase")),
        "records_by_year": dict(sorted(by_year.items())),
        "by_segment": dict(sorted(segments.items(), key=lambda kv: -kv[1])),
        "by_priority": dict(priorities),
    }


# ---------------------------------------------------------------------------
# Pipeline + persistence
# ---------------------------------------------------------------------------

def extract_records(path: str | Path, sheets: Optional[list[str]] = None) -> list[dict]:
    """Read every worksheet with the stdlib reader (no third-party Excel dep).

    ``lead_ingest.read_xlsx`` parses the OOXML zip directly, so the canonical
    importer works in environments where ``openpyxl`` is not installed.
    """
    from src.services.lead_ingest import read_table

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Excel file not found: {path}")

    all_records: list[dict] = []
    for sheet in read_table(path):
        name = sheet.sheet
        if sheets and name not in sheets:
            continue
        try:
            all_records.extend(read_sheet(sheet, name))
        except Exception as exc:  # noqa: BLE001 - one bad sheet must not kill the import
            logger.warning("Skipping sheet %r: %s", name, exc)
    return all_records


def build_leads(records: list[dict]) -> list[dict]:
    merged = merge_records(records)
    for lead in merged:
        enrich_lead(lead)
        lead["dedup_key"] = dedup_key(lead)
    merged.sort(key=lambda l: (-l["priority_score"], l["company_name"]))
    return merged


async def persist_leads(session, leads: list[dict]) -> tuple[int, int]:
    """Idempotently upsert leads. Returns ``(created, updated)``."""
    from sqlalchemy import select

    from src.models import AcquisitionLead

    created = updated = 0
    existing_rows = (await session.execute(select(AcquisitionLead))).scalars().all()
    existing = {row.dedup_key: row for row in existing_rows if row.dedup_key}

    for lead in leads:
        row = existing.get(lead["dedup_key"])
        payload = _to_model_fields(lead)
        if row is None:
            session.add(AcquisitionLead(**payload))
            created += 1
            continue

        # Refresh import-derived fields; never clobber sales activity or opt-outs.
        for field_name, value in payload.items():
            if field_name in ("lead_status", "outreach_status"):
                continue
            setattr(row, field_name, value)
        if row.lead_status not in ("DO_NOT_CONTACT",):
            row.priority = payload["priority"]
            row.priority_score = payload["priority_score"]
        updated += 1

    await session.commit()
    return created, updated


def _to_model_fields(lead: dict) -> dict:
    last_activity = lead.get("last_activity")
    return {
        "company_name": (lead.get("company_name") or "")[:512],
        "contact_name": lead.get("contact_name"),
        "phone": lead.get("phone"),
        "phone_raw": (lead.get("phone_raw") or None),
        "email": (lead.get("email") or None),
        "source": "excel_import",
        "source_sheet": lead.get("source_sheet"),
        "source_customer_code": ",".join(lead.get("source_customer_codes") or [])[:64] or None,
        "historical_customer": bool(lead.get("historical_customer")),
        "quotation_without_purchase": bool(lead.get("quotation_without_purchase")),
        "last_activity": parse_date(last_activity),
        "invoice_count": lead.get("invoice_count") or 0,
        "sales_representative": lead.get("sales_representative"),
        "segment": lead.get("segment") or "unknown",
        "segment_reason": lead.get("segment_reason"),
        "suggested_package": lead.get("suggested_package"),
        "lead_status": lead.get("lead_status") or "NEW",
        "priority": lead.get("priority") or "LOW",
        "priority_score": lead.get("priority_score") or 0,
        "priority_reason": lead.get("priority_reason") or [],
        "outreach_status": lead.get("outreach_status") or "NOT_STARTED",
        "followup_count": 0,
        "dedup_key": lead.get("dedup_key"),
        "record_count": lead.get("record_count") or 1,
        "raw_data": {
            "sheets": lead.get("source_sheets"),
            "codes": lead.get("source_customer_codes"),
            "rows": lead.get("raw_rows"),
        },
    }


def export_outputs(leads: list[dict], stats: dict, out_dir: Path = DATA_DIR) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "leads_normalized.json"
    csv_path = out_dir / "leads_normalized.csv"
    stats_path = out_dir / "import_stats.json"

    exportable = []
    for lead in leads:
        exportable.append({
            "company_name": lead.get("company_name"),
            "phone": lead.get("phone"),
            "email": lead.get("email"),
            "segment": lead.get("segment"),
            "suggested_package": lead.get("suggested_package"),
            "priority": lead.get("priority"),
            "priority_score": lead.get("priority_score"),
            "priority_reason": lead.get("priority_reason"),
            "historical_customer": lead.get("historical_customer"),
            "quotation_without_purchase": lead.get("quotation_without_purchase"),
            "last_activity": lead.get("last_activity"),
            "invoice_count": lead.get("invoice_count"),
            "source_sheets": lead.get("source_sheets"),
            "record_count": lead.get("record_count"),
        })

    json_path.write_text(json.dumps(exportable, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "company_name", "phone", "email", "segment", "suggested_package",
                "priority", "priority_score", "historical_customer",
                "quotation_without_purchase", "last_activity", "invoice_count",
            ],
        )
        writer.writeheader()
        for lead in exportable:
            writer.writerow({
                "company_name": lead["company_name"],
                "phone": lead["phone"] or "",
                "email": lead["email"] or "",
                "segment": lead["segment"],
                "suggested_package": lead["suggested_package"],
                "priority": lead["priority"],
                "priority_score": lead["priority_score"],
                "historical_customer": lead["historical_customer"],
                "quotation_without_purchase": lead["quotation_without_purchase"],
                "last_activity": lead["last_activity"] or "",
                "invoice_count": lead["invoice_count"],
            })
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"json": str(json_path), "csv": str(csv_path), "stats": str(stats_path)}
