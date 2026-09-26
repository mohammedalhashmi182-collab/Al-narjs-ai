---
name: gsk-scholar-search
version: 1.0.0
description: Search scholarly articles and academic papers. Returns matching papers
  with titles, authors, venues, and citation counts.
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk scholar-search --help
---

# gsk-scholar-search

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

Search scholarly articles and academic papers. Returns matching papers with titles, authors, venues, and citation counts.

## Usage

```bash
gsk scholar-search [options]
```

**Aliases:** `scholar-search`

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<query>` (positional) | Yes | The query to search for scholarly articles. (string) |

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
