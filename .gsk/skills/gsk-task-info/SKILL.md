---
name: gsk-task-info
version: 1.0.0
description: 'Read a task''s execution output: recent activity (messages including
  tool usage), current state, and extracted result artifacts — mid-run or after completion.
  Use `task status` for cheap polling; use this when you need the content.'
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk task info --help
---

# gsk-task-info

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

Read a task's execution output: recent activity (messages including tool usage), current state, and extracted result artifacts — mid-run or after completion. Use `task status` for cheap polling; use this when you need the content.

## Usage

```bash
gsk task info [options]
```

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<project_id>` (positional) | Yes | The task's project_id (from the blocking run's response, or from `gsk task status <run_id>` once an async submit started executing). (string) |
| `-n`, `--limit` | No | How many recent activity entries to return (default 10, max 50). (integer) |

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
