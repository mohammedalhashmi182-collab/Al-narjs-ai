---
name: gsk-inbox-contacts
version: 1.0.0
description: 'Unified contact lookup across all connected email accounts (Gmail +
  Outlook). Searches synced address-book contacts AND people the user has emailed
  before (email-history fallback). Actions: search.'
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk find-contact --help
---

# gsk-inbox-contacts

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

Unified contact lookup across all connected email accounts (Gmail + Outlook). Searches synced address-book contacts AND people the user has emailed before (email-history fallback). Actions: search.

## Usage

```bash
gsk find-contact [options]
```

**Aliases:** `find-contact`, `known-contacts`

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<action>` (positional) | Yes | Action to perform. 'search': Search known contacts across all connected accounts (synced + email history) (string, one of: search) |
| `--query` | No | [search] Search query — name, partial name, email, or company. Case-insensitive. (string) |
| `--limit` | No | [search] Maximum number of results to return (1-100). Default: 20. (integer) |
| `--account_ids` | No | [search] Optional. Restrict the search to specific accounts (e.g. ['gmail-alice@x.com', 'outlook-alice@x.com']). If omitted, searches all connected accounts. (array) |

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
