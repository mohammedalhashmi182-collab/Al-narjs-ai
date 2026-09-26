---
name: gsk-google-contacts
version: 1.0.0
description: 'Google Contacts operations. Actions: search, get.'
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk contacts --help
---

# gsk-google-contacts

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

> **Note:** a unified `gsk connector` flow is rolling out (see `../gsk-connector/SKILL.md`: `gsk connector tools <id>` / `gsk connector call <id> -t <tool>`) and may not be enabled for every account yet. THIS command remains fully supported — use it directly, and it stays the fallback whenever `gsk connector` is unavailable.

Google Contacts operations. Actions: search, get.

## Usage

```bash
gsk contacts [options]
```

**Aliases:** `contacts`

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<action>` (positional) | Yes | Action to perform. 'search': Search contacts by name, email, or phone; 'get': Get details of a specific contact (string, one of: search, get) |
| `--query` | No | [search] Search query to find contacts. Searches across names, email addresses, phone numbers, and notes. (string) |
| `--limit` | No | [search] Maximum number of results to return (1-100). Default: 20 (integer) |
| `--account_id` | No | [search] Optional. The Gmail account ID to search (e.g., 'gmail-user@example.com'). If not provided, uses the default Gmail account. \| [get] Optional. The Gmail account ID (e.g., 'gmail-user@example.com'). If not provided, uses the default Gmail account. (string) |
| `--resource_name` | No | [get] The resource name of the contact to retrieve (e.g., 'people/c123456789'). This is returned from search results. (string) |

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
