---
name: gsk-hub
version: 1.0.0
description: 'Genspark Hub (the user''s project spaces at genspark.ai/hub) — NOT HubSpot.
  Read-only actions: list_hubs, read_hub, read_file, read_long_line, grep_files, get_file_url,
  search_sessions, grep_session, read_session, read_long_line_session. When the user
  says ''my Hub'', use this; for HubSpot CRM use `hubspot`.'
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk hub --help
---

# gsk-hub

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

Genspark Hub (the user's project spaces at genspark.ai/hub) — NOT HubSpot. Read-only actions: list_hubs, read_hub, read_file, read_long_line, grep_files, get_file_url, search_sessions, grep_session, read_session, read_long_line_session. When the user says 'my Hub', use this; for HubSpot CRM use `hubspot`.

## Usage

```bash
gsk hub [options]
```

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<action>` (positional) | Yes | Action to perform. 'list_hubs': List the user's Genspark Hubs; 'read_hub': Read one hub's metadata, members, files, and projects; 'read_file': Read a hub file's extracted text (line numbers, limit/offset pagination); 'read_long_line': Read the full content of a truncated file line; 'grep_files': Regex-search hub file text (optional include file filter; 10 files per call, page with file_offset); 'get_file_url': Get a shareable URL for the original hub file (raw bytes, for download / binary analysis); 'search_sessions': Find previous sessions in a hub by keyword (empty query = recent sessions); also lists this session's own archived conversations; 'grep_session': Regex-search one hub session's conversation history; 'read_session': Read one hub session's conversation history (line numbers, limit/offset pagination); 'read_long_line_session': Read the full content of a truncated session line (string, one of: list_hubs, read_hub, read_file, read_long_line, grep_files, get_file_url, search_sessions, grep_session, read_session, read_long_line_session) |
| `--include_archived` | No | [list_hubs] Also include archived hubs. Default: false. (boolean) |
| `--hub_id` | No | [read_hub] Hub ID (from hub_list_hubs). Optional when the calling project belongs to a hub — defaults to that hub. \| [read_file] Hub ID (from hub_list_hubs). Optional when the calling project belongs to a hub — defaults to that hub. \| [read_long_line] Hub ID (from hub_list_hubs). Optional when the calling project belongs to a hub — defaults to that hub. \| [grep_files] Hub ID (from hub_list_hubs). Optional when the calling project belongs to a hub — defaults to that hub. \| [get_file_url] Hub ID (from hub_list_hubs). Optional when the calling project belongs to a hub — defaults to that hub. \| [search_sessions] Hub ID (from hub_list_hubs). Optional when the calling project belongs to a hub — defaults to that hub. \| [grep_session] Hub ID (from hub_list_hubs). Optional when the calling project belongs to a hub — defaults to that hub. \| [read_session] Hub ID (from hub_list_hubs). Optional when the calling project belongs to a hub — defaults to that hub. \| [read_long_line_session] Hub ID (from hub_list_hubs). Optional when the calling project belongs to a hub — defaults to that hub. (string) |
| `--file_name` | No | [read_file] Exact file name from hub_read_hub's files list. \| [read_long_line] Exact file name from hub_read_hub's files list. \| [get_file_url] Exact file name from hub_read_hub's files list. (string) |
| `--limit` | No | [read_file] Number of lines to read (default 100, max 2000). \| [read_session] Number of lines to read (default 100, max 1000). (integer) |
| `--offset` | No | [read_file] Starting line number (1-indexed), for pagination. \| [read_session] Starting line number (1-indexed), for pagination. (integer) |
| `--line_number` | No | [read_long_line] The line number (1-indexed) of the truncated line. \| [read_long_line_session] The line number (1-indexed) of the truncated line. (integer) |
| `--char_offset` | No | [read_long_line] Starting character position (0-indexed, default 0), for paginating through very long lines. \| [read_long_line_session] Starting character position (0-indexed, default 0), for paginating through very long lines. (integer) |
| `--pattern` | No | [grep_files] Regular expression to search for in file content. \| [grep_session] Regular expression to search for in the session. (string) |
| `--include` | No | [grep_files] Optional file name filter (e.g. '*.pdf', '*.docx'). (string) |
| `--file_offset` | No | [grep_files] Starting position within the searchable files only (skipped files do not consume positions; do not compute this from a file listing), 0-indexed, default 0. To search the next batch, re-run the same pattern/include with the file_offset suggested in the previous result. (integer) |
| `--query` | No | [search_sessions] Keywords, e.g. 'API error', 'brand guidelines'. Empty returns recent sessions. (string) |
| `--id` | No | [grep_session] Session ID (from hub_search_sessions). \| [read_session] Session ID (from hub_search_sessions). \| [read_long_line_session] Session ID (from hub_search_sessions). (string) |

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
