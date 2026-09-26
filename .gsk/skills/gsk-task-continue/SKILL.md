---
name: gsk-task-continue
version: 1.0.0
description: Send a follow-up instruction to an existing task project — use this to
  edit, revise, extend, or converse with a task's deliverable (e.g. 'add a slide on
  pricing', 'shorten the intro') instead of `task create`, which mints and bills a
  brand-new task. Works for any task type (slides, docs, sheets, deep_research, website,
  super_agent, ...). The project must belong to you or be shared with you with edit
  (write) permission. Submits and returns immediately by default (poll `task status`);
  pass wait=true for the legacy blocking run.
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk task ask --help
---

# gsk-task-continue

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

Send a follow-up instruction to an existing task project — use this to edit, revise, extend, or converse with a task's deliverable (e.g. 'add a slide on pricing', 'shorten the intro') instead of `task create`, which mints and bills a brand-new task. Works for any task type (slides, docs, sheets, deep_research, website, super_agent, ...). The project must belong to you or be shared with you with edit (write) permission. Submits and returns immediately by default (poll `task status`); pass wait=true for the legacy blocking run.

## Usage

```bash
gsk task ask [options]
```

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<project_id>` (positional) | Yes | The task's project_id — from `gsk task status <run_id>` once an async submit started executing, or data.project_id of a blocking (--wait true) run. (string) |
| `-m`, `--message` | Yes | The follow-up instruction to send to the task agent — state concretely what to change, add, or redo. The agent already has the project's own history. For Design, pass NEW references in attachments (the CLI --image/--file flags build these automatically). (string) |
| `-last-seen-revision`, `--last_seen_revision` | No | Optional optimistic-concurrency token from task_status. For Design projects the update is rejected when it is already stale before the continuation starts. (string) |
| `--attachments` | No | Ordered new references for a Design continuation. They are appended only after last_seen_revision passes. (array) |
| `--wait` | No | Default false: the follow-up is SUBMITTED to the durable runtime and this call returns immediately with its run_id — poll `gsk task status <run_id>`. Pass true to block until the turn completes and get the full result inline (legacy behavior; can take minutes, so set your shell timeout to 1800000 ms). (boolean) |

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
