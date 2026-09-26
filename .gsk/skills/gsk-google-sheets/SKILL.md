---
name: gsk-google-sheets
version: 1.0.0
description: 'Google Sheets spreadsheet operations. Actions: create, read, write,
  append, search, export.'
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk sheets --help
---

# gsk-google-sheets

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

> **Note:** a unified `gsk connector` flow is rolling out (see `../gsk-connector/SKILL.md`: `gsk connector tools <id>` / `gsk connector call <id> -t <tool>`) and may not be enabled for every account yet. THIS command remains fully supported — use it directly, and it stays the fallback whenever `gsk connector` is unavailable.

Google Sheets spreadsheet operations. Actions: create, read, write, append, search, export.

## Usage

```bash
gsk sheets [options]
```

**Aliases:** `sheets`

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<action>` (positional) | Yes | Action to perform. 'create': Create a new spreadsheet; 'read': Read data from a spreadsheet; 'write': Write data to a specific range; 'append': Append rows to a spreadsheet; 'search': Search spreadsheets by name; 'export': Export a spreadsheet to CSV or other format (string, one of: create, read, write, append, search, export) |
| `--title` | No | [create] Title of the new spreadsheet. (string) |
| `--sheet_names` | No | [create] Names of the sheets (tabs) to create, in order; initial_data lands in the first one. Default: ['Sheet1']. Via the gsk CLI pass one name per token: --sheet_names Summary Tasks (a single JSON array string, --sheet_names '["Summary","Tasks"]', is accepted too). (array) |
| `--initial_data` | No | [create] Optional inline initial data for the first sheet, as a 2D array where each inner array is a row. Via the gsk CLI, pass the whole array as ONE JSON string: --initial_data '[["Name","Age"],["Alice","30"]]'. Mutually exclusive with from_sandbox_path / from_aidrive_path / from_url. Prefer the from_* options when the data already exists as a file (CSV/TSV/XLSX/JSON), since 'initial_data' must round-trip through the LLM context. (array) |
| `--from_sandbox_path` | No | [create] Absolute path inside the workflow sandbox (e.g. '/home/user/result.csv'). When set, the file is read from the sandbox and parsed into a 2D array instead of using 'initial_data'. Supported formats: csv, tsv, xlsx, json. Legacy binary .xls (BIFF) is NOT supported — re-save as .xlsx first. Mutually exclusive with from_aidrive_path / from_url / initial_data. \| [write] Absolute path inside the workflow sandbox (e.g. '/home/user/result.csv'). When set, the file is read from the sandbox and parsed into a 2D array instead of using 'values'. Supported formats: csv, tsv, xlsx, json. Legacy binary .xls (BIFF) is NOT supported — re-save as .xlsx first. Mutually exclusive with from_aidrive_path / from_url / values. \| [append] Absolute path inside the workflow sandbox (e.g. '/home/user/result.csv'). When set, the file is read from the sandbox and parsed into a 2D array instead of using 'values'. Supported formats: csv, tsv, xlsx, json. Legacy binary .xls (BIFF) is NOT supported — re-save as .xlsx first. Mutually exclusive with from_aidrive_path / from_url / values. (string) |
| `--from_aidrive_path` | No | [create] Absolute path inside the user's AI-Drive (e.g. '/reports/sales.xlsx'). Read directly via the AI-Drive backend; the file is NOT loaded into the LLM context. Mutually exclusive with from_sandbox_path / from_url / initial_data. \| [write] Absolute path inside the user's AI-Drive (e.g. '/reports/sales.xlsx'). Read directly via the AI-Drive backend; the file is NOT loaded into the LLM context. Mutually exclusive with from_sandbox_path / from_url / values. \| [append] Absolute path inside the user's AI-Drive (e.g. '/reports/sales.xlsx'). Read directly via the AI-Drive backend; the file is NOT loaded into the LLM context. Mutually exclusive with from_sandbox_path / from_url / values. (string) |
| `--from_url` | No | [create] HTTPS URL of a CSV/TSV/XLSX/JSON file. Accepts AI-Drive readable URLs, file-wrapper URLs, or any HTTPS link. Plain http:// is rejected; redirects are not followed. Mutually exclusive with from_sandbox_path / from_aidrive_path / initial_data. \| [write] HTTPS URL of a CSV/TSV/XLSX/JSON file. Accepts AI-Drive readable URLs, file-wrapper URLs, or any HTTPS link. Plain http:// is rejected; redirects are not followed. Mutually exclusive with from_sandbox_path / from_aidrive_path / values. \| [append] HTTPS URL of a CSV/TSV/XLSX/JSON file. Accepts AI-Drive readable URLs, file-wrapper URLs, or any HTTPS link. Plain http:// is rejected; redirects are not followed. Mutually exclusive with from_sandbox_path / from_aidrive_path / values. (string) |
| `--sheet_name` | No | [create] For xlsx sources only: which sheet to read. Defaults to the first sheet if omitted. Ignored for csv/tsv/json sources. \| [write] For xlsx sources only: which sheet to read. Defaults to the first sheet if omitted. Ignored for csv/tsv/json sources. \| [append] For xlsx sources only: which sheet to read. Defaults to the first sheet if omitted. Ignored for csv/tsv/json sources. (string) |
| `--spreadsheet_id` | No | [read] The ID of the spreadsheet to read from. \| [write] The ID of the spreadsheet to write to. \| [append] The ID of the spreadsheet to append to. \| [export] The ID of the Google Sheets spreadsheet to export. (string) |
| `--range` | No | [read] The A1 notation range to read (e.g., 'Sheet1!A1:D10', 'A1:B5'). Default: reads first sheet entirely. \| [write] The A1 notation range to write to (e.g., 'Sheet1!A1:D10'). The range should match the size of the data. Only the cells inside this range are touched — pass the smallest sheet-qualified range that covers exactly the intended change, never a wider one 'to be safe'; a wider range is the only way this tool can overwrite a collaborator's untouched cells, formulas, or formatting on a shared spreadsheet. \| [append] The A1 notation of a range to search for data table. New rows will be appended after the last row in this table. Example: 'Sheet1!A:D' or 'Sheet1' (string) |
| `--values` | No | [write] Inline 2D array of values to write. Each inner array is a row. Example: [['Name', 'Age'], ['Alice', '30'], ['Bob', '25']]. Via the gsk CLI, pass the whole array as ONE JSON string: --values '[["Name","Age"],["Alice","30"]]'. Mutually exclusive with from_sandbox_path / from_aidrive_path / from_url. Prefer the from_* options when the data already exists as a file, to avoid sending it through the LLM context. \| [append] Inline 2D array of values to append. Each inner array is a row. Example: [['Alice', '30'], ['Bob', '25']]. Via the gsk CLI, pass the whole array as ONE JSON string: --values '[["Alice","30"],["Bob","25"]]'. Mutually exclusive with from_sandbox_path / from_aidrive_path / from_url. Prefer the from_* options when the data already exists as a file. (array) |
| `--query` | No | [search] Search query to find spreadsheets by name or content. (string) |
| `--limit` | No | [search] Maximum number of results to return (1-50). Default: 10 (integer) |
| `--filename` | No | [export] Optional custom filename for the exported file (without extension). If not provided, the original spreadsheet name will be used. (string) |

## Local File Support

Parameters that accept URLs (`--from_url`) also accept local file paths. The CLI automatically uploads local files before sending to the API.

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
