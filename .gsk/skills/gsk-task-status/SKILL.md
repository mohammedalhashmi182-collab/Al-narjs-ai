---
name: gsk-task-status
version: 1.0.0
description: 'Look up an existing task: pass the run_id from an async submit (sb_task_run::…)
  for its durable lifecycle state, or the project_id for status, page URL (task_url),
  and extracted result artifacts. Use this — never a new create — when you need the
  link or outcome of a task you already created.'
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk task status --help
---

# gsk-task-status

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

Look up an existing task: pass the run_id from an async submit (sb_task_run::…) for its durable lifecycle state, or the project_id for status, page URL (task_url), and extracted result artifacts. Use this — never a new create — when you need the link or outcome of a task you already created.

## Usage

```bash
gsk task status [options]
```

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<project_id>` (positional) | Yes | The task's identifier: either the run_id from an async submit (sb_task_run::…) or the project_id from a finished/blocking run. (string) |
| `--detail` | No | Optional JSON object requesting task-type detail sections alongside the standard fields, e.g. '{"pages": true}' for slides page-level progress. Omit for the standard response. Keys are defined by the task type; unknown keys error with the supported list. (string) |

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
