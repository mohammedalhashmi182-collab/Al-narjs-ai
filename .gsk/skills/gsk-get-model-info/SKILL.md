---
name: gsk-get-model-info
version: 1.0.0
description: 'Detailed generation-model info: capabilities, params_schema, available
  speakers and prompting guides (audio/video/image/3d).'
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk model-info --help
---

# gsk-get-model-info

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

Detailed generation-model info: capabilities, params_schema, available speakers and prompting guides (audio/video/image/3d).

## Usage

```bash
gsk model-info [options]
```

**Aliases:** `model-info`

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<model_names>` (positional) | Yes | Array of model names/IDs to query. Each must be one of the available model names. (array) |

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
