---
name: gsk-task-artifacts
version: 1.0.0
description: List a task's produced artifacts (files, rendered exports, generated
  media) as downloadable URLs with stable artifact ids — resolvable via `task artifact
  <artifact_id>`, consumable via `task create --artifact_refs` — plus the exportable
  formats for docs/slides/sheets deliverables.
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk task artifacts --help
---

# gsk-task-artifacts

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

List a task's produced artifacts (files, rendered exports, generated media) as downloadable URLs with stable artifact ids — resolvable via `task artifact <artifact_id>`, consumable via `task create --artifact_refs` — plus the exportable formats for docs/slides/sheets deliverables.

## Usage

```bash
gsk task artifacts [options]
```

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<project_id>` (positional) | Yes | The task's project_id (from the blocking run's response, or from `gsk task status <run_id>` once an async submit started executing). (string) |

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
