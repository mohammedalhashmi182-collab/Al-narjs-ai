"""Import the historical invoice/quotations Excel into the lead database.

Usage (run from the project root so ``.env`` is picked up)::

    python scripts/import_leads.py --excel "C:/path/last invoices in 5 Years.xlsx"
    python scripts/import_leads.py --excel ... --campaign 200
    python scripts/import_leads.py --excel ... --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_EXCEL = Path.home() / "Downloads" / "last invoices in 5 Years.xlsx"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Karma AI lead ingestion")
    parser.add_argument("--excel", default=None, help="Path to the .xlsx workbook")
    parser.add_argument("--sheets", default=None, help="Comma-separated sheet names to import")
    parser.add_argument("--campaign", type=int, default=0, help="Build a campaign batch of N leads after import")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only; do not write to the database")
    return parser.parse_args()


def resolve_excel(args) -> Path:
    from src.config.settings import settings

    if args.excel:
        return Path(args.excel)
    if settings.leads_excel_path:
        return Path(settings.leads_excel_path)
    return DEFAULT_EXCEL


async def run(args) -> int:
    from src.services.lead_importer import (
        build_leads,
        compute_stats,
        export_outputs,
        extract_records,
        persist_leads,
    )

    excel = resolve_excel(args)
    if not excel.is_file():
        print(f"[x] Excel file not found: {excel}")
        print("    Pass --excel <path> or set LEADS_EXCEL_PATH in .env")
        return 2

    sheets = [s.strip() for s in args.sheets.split(",")] if args.sheets else None
    print(f"[*] Reading workbook: {excel}")
    raw = extract_records(excel, sheets=sheets)
    print(f"[*] Raw rows: {len(raw)}")

    leads = build_leads(raw)
    stats = compute_stats(raw, leads)

    print("\n=== Import statistics ===")
    print(json.dumps(stats, ensure_ascii=False, indent=2))

    if args.dry_run:
        print("\n[i] Dry run — database untouched.")
        return 0

    from src.db.session import async_session_factory, init_db

    await init_db()
    async with async_session_factory() as session:
        created, updated = await persist_leads(session, leads)
        paths = export_outputs(leads, stats)
        print(f"\n[+] Leads persisted: {created} created, {updated} updated")
        print(f"[+] Exports: {paths['csv']}")

        if args.campaign:
            from src.services.lead_campaigns import build_campaign, export_campaign_json

            campaign = await build_campaign(session, size=args.campaign)
            path = await export_campaign_json(session, campaign)
            print(f"[+] Campaign batch #{campaign.batch_no} ready ({args.campaign} target) → {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
