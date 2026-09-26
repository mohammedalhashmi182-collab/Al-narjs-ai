---
name: gsk-onedrive
version: 1.0.0
description: 'OneDrive file operations. Actions: list, search, read, upload, share.'
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk onedrive --help
---

# gsk-onedrive

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

> **Note:** a unified `gsk connector` flow is rolling out (see `../gsk-connector/SKILL.md`: `gsk connector tools <id>` / `gsk connector call <id> -t <tool>`) and may not be enabled for every account yet. THIS command remains fully supported — use it directly, and it stays the fallback whenever `gsk connector` is unavailable.

OneDrive file operations. Actions: list, search, read, upload, share.

## Usage

```bash
gsk onedrive [options]
```

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<action>` (positional) | Yes | Action to perform. 'list': List files in a folder; 'search': Search files; 'read': Read and extract content from a file; 'upload': Upload a file (local path, file-wrapper URL, AI Drive path, or text content) to OneDrive; 'share': Create a sharing link (view/edit/embed; anonymous or organization scope) for a file or folder. Confirmation-gated: on a CLI with client-side confirmation the command runs as a single call after the [y/N] prompt (or --yes). (string, one of: list, search, read, upload, share) |
| `--onedrive_url` | No | [list] A OneDrive URL to list files from. Can be a sharing link, folder link, or any OneDrive URL. (string) |
| `--folder_id` | No | [list] The folder item ID to list contents of. Get folder IDs from previous onedrive_list_files or onedrive_search results. \| [upload] Target folder item ID (from onedrive_list_files or onedrive_search). If omitted, ``folder_path`` is used; if both are omitted, the upload goes to the OneDrive root. (string) |
| `--folder_path` | No | [list] The folder path relative to OneDrive root. Example: 'Documents/Projects' to list files in that subfolder. \| [upload] Target folder path relative to the OneDrive root, e.g. 'Documents/Reports'. The folder must already exist. Ignored when ``folder_id`` is provided. (string) |
| `--limit` | No | [list] Maximum number of items to return (1-200). Default: 50 (integer) |
| `--all_pages` | No | [list] List every page in this folder. Use for complete programmatic inventory; default false. (boolean) |
| `--query` | No | [search] The search query string. **Query Behavior**: • Spaces = AND: 'project report' finds files with BOTH terms • OR operator: 'project OR report' finds files with EITHER term • Empty string: '*' lists all files • Wildcards: 'report*' finds files starting with 'report' • Examples: 'budget.xlsx', 'meeting OR conference', '*.pdf', 'project 2024' (string) |
| `--file_id` | No | [read] The ID of the file OR the OneDrive/SharePoint URL to read from OneDrive or SharePoint. Can be either a file ID (like '01W56PINYRO3...') or a full OneDrive/SharePoint URL (like 'https://domain-my.sharepoint.com/personal/user/Documents/file.pdf' or SharePoint driveItem IDs). For Teams attachments, use the 'file_id' value from Teams search results onedrive_file_params. \| [share] OneDrive item ID of the file or folder to share (from onedrive_list_files or onedrive_search). Mutually exclusive with ``file_path``. (string) |
| `--question` | No | [read] The question to answer about the file content. (string) |
| `--raw_content` | No | [read] Return the complete converted document text (markdown) without question-answering. For programmatic consumers that need full fidelity; ignores 'question'. (boolean) |
| `--file_path` | No | [upload] Path or URL to the file to upload. Accepts any of: (1) a local server filesystem path (e.g. ``/tmp/report.xlsx`` — Claw VM use); (2) a Genspark file-wrapper URL (e.g. ``https://www.genspark.ai/api/files/s/<code>``) — canonical sandbox-to-server bridge, produced by calling ``UploadFileWrapper`` on a sandbox file first; or (3) an AI Drive path (e.g. ``/mnt/aidrive/path/to/file.xlsx``, ``/aidrive/...`` or ``aidrive://...``). Mutually exclusive with ``content``. \| [share] Path of the item relative to the OneDrive root, e.g. 'Documents/report.pdf'. Ignored when ``file_id`` is provided. (string) |
| `--content` | No | [upload] Text content to upload as the file body (encoded as UTF-8). Useful for creating .txt/.md/.json/.csv files without a local copy. Mutually exclusive with ``file_path``. (string) |
| `--file_name` | No | [upload] File name to create on OneDrive, including the extension (e.g. 'report.pdf'). Required when ``content`` is used; if omitted with ``file_path``, the basename of the source file is used. (string) |
| `--mime_type` | No | [upload] MIME type of the file. Auto-detected from the file extension if omitted. (string) |
| `--conflict_behavior` | No | [upload] How to handle a name conflict on OneDrive: 'rename' appends a suffix (default), 'replace' overwrites, 'fail' returns an error. (string, one of: rename, replace, fail) |
| `--link_type` | No | [share] Kind of link to create: 'view' (read-only, default), 'edit', or 'embed'. (string, one of: view, edit, embed) |
| `--link_scope` | No | [share] Who the link works for: 'anonymous' (anyone with the link) or 'organization' (signed-in members of the user's org). Omitted, the account default applies. (string, one of: anonymous, organization) |

## Local File Support

Parameters that accept URLs (`--onedrive_url`) also accept local file paths. The CLI automatically uploads local files before sending to the API.

## Write Confirmation

Confirmation-gated actions: `share`. The CLI shows a preview and asks `[y/N]` on stderr before the single server call; pass `--yes` (`-y`) for unattended runs. `--no-input` (or `--args-file -`, which consumes stdin) makes a gated call exit 2 with no server call instead of hanging. Never re-run a command to 'confirm' it — every call is a real execution. `--skip_confirmation true` / `--auto_skip_confirmation` are deprecated on this CLI (still accepted, warn on stderr): use `--yes`.

Interactive-only actions: `share` (the action excludes the skip params, e.g. Marketplace policy on Slack) — `--yes` is ignored and a real `[y/N]` answer is required.

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
