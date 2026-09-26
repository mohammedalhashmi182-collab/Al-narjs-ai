---
name: gsk-sb-brain
version: 1.0.0
description: 'Unified read-only access to the user''s Second Brain — notes, emails,
  meetings, and connected knowledge sources. Identify repos by source name (memo,
  gmail, outlook, meeting, notion) instead of repo IDs. Actions: list-repos, ls, read,
  grep, log. Typical flow: list-repos → see available sources; grep -q <pattern> →
  search across all sources (or -s <source> for one); read -s <hit.source> --repo_id
  <hit.repo_id> -p <hit.path> → open the exact file a grep or ls hit returned. list-repos
  also returns a content description and physical clone URL for each visible source.
  Read-only; does not modify files.'
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk sb-brain --help
---

# gsk-sb-brain

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

**THEN READ:** `../gsk-second-brain/SKILL.md` — it says what this command is part of and when to reach for it. This file keeps the flags.

Unified read-only access to the user's Second Brain — notes, emails, meetings, and connected knowledge sources. Identify repos by source name (memo, gmail, outlook, meeting, notion) instead of repo IDs. Actions: list-repos, ls, read, grep, log. Typical flow: list-repos → see available sources; grep -q <pattern> → search across all sources (or -s <source> for one); read -s <hit.source> --repo_id <hit.repo_id> -p <hit.path> → open the exact file a grep or ls hit returned. list-repos also returns a content description and physical clone URL for each visible source. Read-only; does not modify files.

## Usage

```bash
gsk sb-brain [options]
```

## What this command reads

`gsk sb-brain` opens the **Notes** half of the user's Second Brain — their
notes, archived mail, meeting notes, Notion import, and past Genspark
conversations. The map of the whole Second Brain (Notes + Drive, which door
opens which part, how to read, write and edit) is `../gsk-second-brain/SKILL.md`;
read it first. Two details that belong to this command alone:

- `grep` is a fixed string, case-insensitive — not a regex. Use a short
  distinctive keyword; a long phrase must match a single line exactly.
- `read` takes the hit's `repo_id` (`--repo_id <hit.repo_id>`); without it a
  source with several repos (two mailboxes) opens the first one.

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<action>` (positional) | Yes | Action to perform. (string, one of: list-repos, ls, read, grep, log) |
| `-s`, `--source` | No | Source name: memo, gmail, outlook, meeting, notion, team, custom, project_history. Required for ls, read, log. Optional for grep (omit to search ALL mounted sources). (string) |
| `-p`, `--path` | No | File or directory path within the source repo. Used by ls (optional, defaults to root), read (required) and grep (optional directory prefix that confines the search). (string) |
| `-q`, `--query` | No | Search text for grep (fixed string, case-insensitive; NOT a regex). Required for grep. Use a short distinctive keyword — a long phrase must match a single line exactly. (string) |
| `--ref` | No | Git ref (branch or commit SHA). Defaults to main. (string) |
| `--repo_id` | No | Disambiguate when a source has multiple repos (e.g. two Gmail accounts). Get from list-repos. Optional; defaults to first match. (string) |
| `--limit` | No | Max results for log (default 20). (integer) |

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
