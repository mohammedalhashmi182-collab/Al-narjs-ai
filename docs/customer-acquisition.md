# Customer Acquisition (Karma AI / Al-Narjis)

How we turn the historical invoices/quotations workbook into the first paying
customers — safely, with a human approving every message.

## TL;DR

```bash
cd Al-narjs-ai

# 1. Analyze without touching the database
python scripts/import_leads.py --dry-run

# 2. Import + build the first outreach batch (200 leads)
python scripts/import_leads.py --campaign 200

# 3. Open the dashboard (owner login required) and work the `READY` leads
python -m uvicorn src.main:app --reload
#    → http://localhost:8000/acquisition
```

> There is one authoritative surface: `/acquisition` (backed by
> `AcquisitionLead` + `src/interfaces/sales_routes.py`). Public website form
> submissions (`POST /api/leads`) write into the same CRM as `source="website"`,
> so inbound and imported prospects share one pipeline and one dashboard.

Nothing is ever sent automatically. The system prepares prioritized, Arabic
drafts with a one-click `wa.me` link; a human pastes and sends from the company
WhatsApp number (`WHATSAPP_BUSINESS_NUMBER`, default `06552978753`).

## Data source

`last invoices in 5 Years.xlsx` (path set by `LEADS_EXCEL_PATH`). The workbook
mixes three kinds of sheets:

| Sheet | Meaning | Rows |
| --- | --- | --- |
| `2020`…`2025` | customers who purchased that year (`Op/Cl = ✔`) | 68 / 141 / 153 / 168 / 197 / 233 |
| `quotations without purchase` | quotes that never converted (`✖`) | 376 |
| `Sheet2` | master list containing **both** `✔` and `✖` rows | 1335 |

Key facts discovered in the data (do not assume otherwise):

* The `email ` column is **empty on every sheet** — email is not a usable channel.
* Customer names are truncated to ~25 characters in `Name 1`; that is all we have.
* Phone numbers are often stored without the leading `0` (e.g. `507577795`), and
  some are junk (`4481122`, `0`). The importer normalizes only what is real and
  **rejects ambiguous values rather than inventing digits**.
* `Op / Cl` is the per-row source of truth: `✔` = purchased, `✖` = no purchase.
  Year sheets are all `✔`; the quotations sheet is all `✖`; `Sheet2` is mixed.

## Pipeline

```
Excel ──► extract_records ──► merge_records ──► enrich_lead ──► persist_leads ──► build_campaign
             (read)            (dedupe)       (segment+score)     (SQLite)          (batch)
```

| Stage | File | Notes |
| --- | --- | --- |
| Read | `src/services/lead_ingest.py` → `lead_importer.py` | Stdlib OOXML reader (no `openpyxl`); bounded reader stops after 50 blank rows (the workbook reports ~1M phantom rows). |
| Normalize | `src/services/lead_normalize.py` | Arabic-aware name keys, conservative KSA-first phone/date parsing. |
| Dedupe | `src/services/lead_importer.py` | Union-find on shared phone/email; falls back to name only when a phone is missing. |
| Segment | `src/services/lead_segmentation.py` | Keyword classifier → `ecommerce`, `retail`, `restaurant_food`, `services`, … |
| Prioritize | `src/services/lead_priority.py` | Explainable 0–100 score; every point has an Arabic reason. |
| Outreach | `src/services/lead_outreach.py` | 3 Arabic-first templates + `wa.me` link. |
| Campaign | `src/services/lead_campaigns.py` | Prioritized batch of reachable leads → `READY`. |

### Priority score

`HIGH ≥ 55`, `MEDIUM ≥ 30`, otherwise `LOW`. Factors: open quotation (+25),
past customer (+15), recent activity (+12/+9/+5), valid WhatsApp mobile (+18) or
phone (+14), email (+6), contact name (+4), repeat purchases (+6/+3), targeted
segment (+10/+4), complete profile (+4). The dashboard shows the exact reasons.

## Result of the last full import

```
2670 raw rows → 1227 unique companies (1443 duplicates merged)
400 valid phones · 323 WhatsApp-capable · 0 emails
893 past customers · 699 companies with an unconverted quote
priority: 104 HIGH · 572 MEDIUM · 551 LOW
campaign batch #1: 200 leads marked READY
```

Secondary exports (PII — **gitignored**, never commit): `data/leads_normalized.csv`,
`data/leads_normalized.json`, `data/import_stats.json`, `data/campaigns/*.json`.

## Working a lead

`/acquisition` shows today's follow-ups, the pipeline, prioritized leads and
campaign batches. `/acquisition/leads/{id}` is the workbench:

1. Read *why* this company is prioritized.
2. Pick a variant → **توليد** (generate) → **نسخ** (copy) → **فتح واتساب** (send manually).
3. Update the stage: `CONTACTED → REPLIED → INTERESTED → DEMO → PROPOSAL → WON/LOST`.
4. Schedule the next follow-up (default 3 days) and log notes.
5. `DO_NOT_CONTACT` immediately and permanently opts a lead out.

Suggested cadence: day 0 first message, day 3 follow-up, day 7 value/demo,
day 14 final. Two no-replies → `LOST`.

## Guardrails

* Every `/acquisition` page and `/api/acquisition/*` route is owner-gated (`require_owner`).
* No automatic sending anywhere — click-to-chat only, always human-approved.
* `DO_NOT_CONTACT` is respected by re-imports (activity and opt-outs are never clobbered).
* The importer is idempotent: re-running it updates derived fields
  (`0 created, N updated`) and leaves sales activity untouched.

## Tests

```bash
python -m pytest -q          # 68 tests
python -m ruff check src scripts
```

`tests/test_lead_acquisition.py` covers phone/name normalization, segmentation,
priority bounds, message generation, dedupe, campaign batching, **stdlib** XLSX
and CSV reading (no openpyxl), malformed-file handling, idempotent persistence,
public capture → CRM, and the owner-gated acquisition API/workflow.
