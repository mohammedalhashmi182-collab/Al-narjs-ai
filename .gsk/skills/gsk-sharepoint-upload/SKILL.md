---
name: gsk-sharepoint-upload
version: 1.0.0
description: Upload a file to a SharePoint document library.
metadata:
  category: sharepoint
  requires:
    bins:
    - gsk
  cliHelp: gsk sharepoint upload --help
---

# gsk-sharepoint-upload

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

> **Note:** a unified `gsk connector` flow is rolling out (see `../gsk-connector/SKILL.md`: `gsk connector tools <id>` / `gsk connector call <id> -t <tool>`) and may not be enabled for every account yet. THIS command remains fully supported — use it directly, and it stays the fallback whenever `gsk connector` is unavailable.

Upload a file to a SharePoint document library.

## Usage

```bash
gsk sharepoint upload [options]
```

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<file_path>` (positional) | No | Path or URL to the file to upload. Accepts any of: (1) a local server filesystem path (e.g. ``/tmp/report.xlsx`` — Claw VM use); (2) a Genspark file-wrapper URL (e.g. ``https://www.genspark.ai/api/files/s/<code>``) — canonical sandbox-to-server bridge, produced by calling ``UploadFileWrapper`` on a sandbox file first; or (3) an AI Drive path (e.g. ``/mnt/aidrive/path/to/file.xlsx``, ``/aidrive/...`` or ``aidrive://...``). Mutually exclusive with ``content``. (string) |
| `--content` | No | Text content to upload as the file body (encoded as UTF-8). Useful for creating .txt/.md/.json/.csv files without a local copy. Mutually exclusive with ``file_path``. (string) |
| `-n`, `--file_name` | No | File name to create on SharePoint, including the extension (e.g. 'report.pdf'). Required when ``content`` is used; if omitted with ``file_path``, the basename of the local file is used. (string) |
| `-u`, `--sharepoint_url` | No | Target folder URL on SharePoint. Example: 'https://company.sharepoint.com/sites/Team/Shared Documents/Reports'. The tool resolves this to a drive + folder. (string) |
| `-s`, `--site_id` | No | SharePoint site ID. The file is uploaded to the default document library; combine with ``folder_id`` to target a subfolder. (string) |
| `-d`, `--drive_id` | No | Document library (drive) ID. Combine with ``folder_id`` to target a specific folder. (string) |
| `-f`, `--folder_id` | No | Folder item ID inside ``drive_id`` or the site's default drive. If omitted, the upload goes to the drive root. (string) |
| `--mime_type` | No | MIME type of the file. Auto-detected from the file extension if omitted. (string) |
| `--conflict_behavior` | No | How to handle a name conflict on SharePoint: 'rename' appends a suffix (default), 'replace' overwrites, 'fail' returns an error. (string, one of: rename, replace, fail) |

## Local File Support

Parameters that accept URLs (`--sharepoint_url`) also accept local file paths. The CLI automatically uploads local files before sending to the API.

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
