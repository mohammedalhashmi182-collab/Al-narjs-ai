---
name: gsk-sharepoint
version: 1.0.0
description: 'SharePoint site, list, and file operations. Actions: list, list_items,
  search, read_content, read_file, upload.'
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk sharepoint --help
---

# gsk-sharepoint

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

> **Note:** a unified `gsk connector` flow is rolling out (see `../gsk-connector/SKILL.md`: `gsk connector tools <id>` / `gsk connector call <id> -t <tool>`) and may not be enabled for every account yet. THIS command remains fully supported — use it directly, and it stays the fallback whenever `gsk connector` is unavailable.

SharePoint site, list, and file operations. Actions: list, list_items, search, read_content, read_file, upload.

## Usage

```bash
gsk sharepoint [options]
```

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<action>` (positional) | Yes | Action to perform. 'list': List files in a site or library; 'list_items': Read the rows of a SharePoint list (Microsoft Lists) with all columns expanded; 'search': Search across sites; 'read_content': Read content from a list item or page; 'read_file': Read and extract content from a file; 'upload': Upload a file to a site or library (string, one of: list, list_items, search, read_content, read_file, upload) |
| `--sharepoint_url` | No | [list] A SharePoint URL to list files from. Can be a site URL, document library URL (AllItems.aspx), or a folder URL. Example: 'https://company.sharepoint.com/sites/TeamSite/Shared Documents/Forms/AllItems.aspx' \| [upload] Target folder URL on SharePoint. Example: 'https://company.sharepoint.com/sites/Team/Shared Documents/Reports'. The tool resolves this to a drive + folder. (string) |
| `--site_id` | No | [list] The SharePoint site ID. Use this to list the default document library of a specific site. Get site IDs from sharepoint_search results. \| [list_items] The SharePoint site ID that owns the list. Get it from sharepoint_search results. \| [read_content] Site ID from SharePoint search results siteInfo. Required for listItem content type. \| [upload] SharePoint site ID. The file is uploaded to the default document library; combine with ``folder_id`` to target a subfolder. (string) |
| `--drive_id` | No | [list] The document library (drive) ID. Use this to list files in a specific document library. \| [upload] Document library (drive) ID. Combine with ``folder_id`` to target a specific folder. (string) |
| `--folder_id` | No | [list] The folder item ID within a drive. Use this with drive_id to navigate into subfolders. Get folder IDs from previous sharepoint_list_files results. \| [upload] Folder item ID inside ``drive_id`` or the site's default drive. If omitted, the upload goes to the drive root. (string) |
| `--limit` | No | [list] Maximum number of items to return (1-200). Default: 50 \| [list_items] Maximum number of rows per page (1-200). Default: 50 (integer) |
| `--all_pages` | No | [list] List every page in this folder. Use for complete programmatic inventory; default false. \| [list_items] Read every page of the list. Use for complete programmatic inventory; default false. (boolean) |
| `--list_id` | No | [list_items] The list ID (GUID). Get it from sharepoint_search results of type 'list'. \| [read_content] List ID from SharePoint search results siteInfo. Required for listItem content type. (string) |
| `--list_url` | No | [list_items] A SharePoint list URL such as 'https://company.sharepoint.com/sites/Team/Lists/Requests/AllItems.aspx'. Alternative to site_id + list_id. (string) |
| `--query` | No | [search] The search query string using KQL syntax. **Query Behavior**: • Spaces = AND: 'project report' finds items with BOTH terms • OR operator: 'project OR report' finds items with EITHER term • Empty string: '*' returns all items • Mixed language: automatically optimized (e.g., 'プロジェクト project' → 'プロジェクト OR project') • Examples: 'budget 2024', 'meeting OR conference', 'from:john project', 'hasAttachment:true report' (string) |
| `--entity_types` | No | [search] Types of SharePoint content to search. Defaults to all types. (array, default: `['site', 'listItem', 'list', 'driveItem']`) |
| `--content_id` | No | [read_content] The ID of the SharePoint content to read. Can be a site ID, page ID, list ID, list item ID from SharePoint search results, or a SharePoint URL for direct file access. For Teams attachments, use the 'content_id' value from Teams search results onedrive_file_params. (string) |
| `--content_type` | No | [read_content] The type of SharePoint content to read. Use 'driveItem' for SharePoint files, 'listItem' for SharePoint pages/list items. (string, one of: site, page, list, listItem, driveItem) |
| `--question` | No | [read_content] The question to answer about the SharePoint content. \| [read_file] The question to answer about the file content. (string) |
| `--list_item_id` | No | [read_content] List item ID from SharePoint search results siteInfo. Required for listItem content type. (string) |
| `--file_id` | No | [read_file] The ID of the file OR the SharePoint URL to read from Microsoft OneDrive/SharePoint/Teams. Can be either a file ID (like '01W56PINYRO3...') or a full SharePoint URL (like 'https://domain.sharepoint.com/...'). (string) |
| `--raw_content` | No | [read_file] Return the complete converted document text (markdown) without question-answering. For programmatic consumers that need full fidelity; ignores 'question'. (boolean) |
| `--file_path` | No | [upload] Path or URL to the file to upload. Accepts any of: (1) a local server filesystem path (e.g. ``/tmp/report.xlsx`` — Claw VM use); (2) a Genspark file-wrapper URL (e.g. ``https://www.genspark.ai/api/files/s/<code>``) — canonical sandbox-to-server bridge, produced by calling ``UploadFileWrapper`` on a sandbox file first; or (3) an AI Drive path (e.g. ``/mnt/aidrive/path/to/file.xlsx``, ``/aidrive/...`` or ``aidrive://...``). Mutually exclusive with ``content``. (string) |
| `--content` | No | [upload] Text content to upload as the file body (encoded as UTF-8). Useful for creating .txt/.md/.json/.csv files without a local copy. Mutually exclusive with ``file_path``. (string) |
| `--file_name` | No | [upload] File name to create on SharePoint, including the extension (e.g. 'report.pdf'). Required when ``content`` is used; if omitted with ``file_path``, the basename of the local file is used. (string) |
| `--mime_type` | No | [upload] MIME type of the file. Auto-detected from the file extension if omitted. (string) |
| `--conflict_behavior` | No | [upload] How to handle a name conflict on SharePoint: 'rename' appends a suffix (default), 'replace' overwrites, 'fail' returns an error. (string, one of: rename, replace, fail) |

## Local File Support

Parameters that accept URLs (`--sharepoint_url`, `--list_url`) also accept local file paths. The CLI automatically uploads local files before sending to the API.

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
