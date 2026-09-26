---
name: gsk-batch-understand-videos
version: 1.0.0
description: 'Process multiple YouTube videos in parallel: fetch each transcript and
  answer per-video questions. Input: list of {video_id, questions_to_answer} jobs.'
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk batch-understand-videos --help
---

# gsk-batch-understand-videos

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

Process multiple YouTube videos in parallel: fetch each transcript and answer per-video questions. Input: list of {video_id, questions_to_answer} jobs.

## Usage

```bash
gsk batch-understand-videos [options]
```

**Aliases:** `batch-understand-videos`

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<jobs>` (positional) | Yes | Get the text of a youtube video by video id. (array) |

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
