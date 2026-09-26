---
name: gsk-google-slides
version: 1.0.0
description: 'Google Slides presentation operations. Actions: search, read, create,
  batch_update, export.'
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk slides --help
---

# gsk-google-slides

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

> **Note:** a unified `gsk connector` flow is rolling out (see `../gsk-connector/SKILL.md`: `gsk connector tools <id>` / `gsk connector call <id> -t <tool>`) and may not be enabled for every account yet. THIS command remains fully supported — use it directly, and it stays the fallback whenever `gsk connector` is unavailable.

Google Slides presentation operations. Actions: search, read, create, batch_update, export.

## Usage

```bash
gsk slides [options]
```

**Aliases:** `slides`

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<action>` (positional) | Yes | Action to perform. 'search': Search presentations by name; 'read': Read a presentation's slides and text elements; 'create': Create a new empty presentation; 'batch_update': Apply Slides API batchUpdate requests (add/edit slides, shapes, text, styles); 'export': Export a presentation to PPTX or PDF (string, one of: search, read, create, batch_update, export) |
| `--query` | No | [search] Search query to find presentations by name. (string) |
| `--limit` | No | [search] Maximum number of results to return (1-50). Default: 10 (integer) |
| `--presentation_id` | No | [read] The ID of the presentation to read. \| [batch_update] The ID of the presentation. \| [export] The ID of the Google Slides presentation to export. (string) |
| `--slide_ids` | No | [read] Optional: restrict the read to specific slide objectIds. (array) |
| `--include_raw` | No | [read] If true, also include the raw page elements (verbose). Default: false. (boolean) |
| `--title` | No | [create] Title of the new presentation. (string) |
| `--requests` | No | [batch_update] Array of batchUpdate request objects. Each object has one request type key. Common types: createSlide, deleteObject, duplicateObject, createShape, createImage, createTable, insertText, deleteText, updateTextStyle, updateParagraphStyle, updatePageElementTransform, updateShapeProperties, replaceAllText. Load the appropriate guide first. (array) |
| `--format` | No | [export] Export format. Default: 'pptx'. (string, one of: pptx, pdf) |
| `--filename` | No | [export] Optional custom filename (without extension). If not provided, the original presentation name is used. (string) |

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
