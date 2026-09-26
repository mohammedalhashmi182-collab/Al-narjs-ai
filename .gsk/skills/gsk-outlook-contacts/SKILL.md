---
name: gsk-outlook-contacts
version: 1.0.0
description: 'Outlook Contacts operations. Actions: search.'
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk outlook_contacts --help
---

# gsk-outlook-contacts

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

> **Note:** a unified `gsk connector` flow is rolling out (see `../gsk-connector/SKILL.md`: `gsk connector tools <id>` / `gsk connector call <id> -t <tool>`) and may not be enabled for every account yet. THIS command remains fully supported — use it directly, and it stays the fallback whenever `gsk connector` is unavailable.

Outlook Contacts operations. Actions: search.

## Usage

```bash
gsk outlook_contacts [options]
```

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<action>` (positional) | Yes | Action to perform. 'search': Search Outlook contacts (string, one of: search) |
| `--query` | No | [search] Search query to find contacts. Searches across names, email addresses, phone numbers, and notes. (string) |
| `--limit` | No | [search] Maximum number of results to return (1-100). Default: 20 (integer) |
| `--account_id` | No | [search] Optional. The Outlook account ID to search (e.g., 'outlook-user@example.com'). If not provided, uses the default Outlook account. (string) |

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
