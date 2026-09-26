---
name: gsk-task-stop
version: 1.0.0
description: 'Stop a running task: pass the run_id from the submit response (preferred)
  or the task''s project_id. Aborts the in-flight run; safe when nothing is running.
  Requires edit (write) permission.'
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk task stop --help
---

# gsk-task-stop

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

Stop a running task: pass the run_id from the submit response (preferred) or the task's project_id. Aborts the in-flight run; safe when nothing is running. Requires edit (write) permission.

## Usage

```bash
gsk task stop [options]
```

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<id>` (positional) | Yes | The run_id from the submit response (sb_task_run::…), or the task's project_id. (string) |

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
