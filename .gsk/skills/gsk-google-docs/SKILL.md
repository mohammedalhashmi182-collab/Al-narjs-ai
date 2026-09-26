---
name: gsk-google-docs
version: 1.0.0
description: 'Google Docs document operations. Actions: create, read, append, batch_update,
  export, search.'
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk docs --help
---

# gsk-google-docs

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

> **Note:** a unified `gsk connector` flow is rolling out (see `../gsk-connector/SKILL.md`: `gsk connector tools <id>` / `gsk connector call <id> -t <tool>`) and may not be enabled for every account yet. THIS command remains fully supported — use it directly, and it stays the fallback whenever `gsk connector` is unavailable.

Google Docs document operations. Actions: create, read, append, batch_update, export, search.

## Usage

```bash
gsk docs [options]
```

**Aliases:** `docs`

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<action>` (positional) | Yes | Action to perform. 'create': Create a new document; 'read': Read content from a document; 'append': Append content to a document; 'batch_update': Advanced edits via the batchUpdate API: text insertion/deletion at indices, formatting, paragraph styles, images, tables, find/replace; 'export': Export a document (PDF, DOCX, ...); 'search': Search documents by name (string, one of: create, read, append, batch_update, export, search) |
| `--title` | No | [create] Title of the new document. (string) |
| `--content` | No | [create] Optional initial text content for the document. \| [append] The text content to append to the document. (string) |
| `--document_id` | No | [read] The ID of the document to read. \| [append] The ID of the document to append to. \| [batch_update] The ID of the document. \| [export] The ID of the Google Docs document to export. (string) |
| `--requests` | No | [batch_update] Array of batchUpdate request objects. Each object has one request type key. Common types: insertText, deleteContentRange, updateTextStyle, updateParagraphStyle, insertInlineImage, insertTable, replaceAllText, insertPageBreak, createParagraphBullets, deleteParagraphBullets. Load the formatting/images/tables guide for detailed examples. (array) |
| `--format` | No | [export] Export format. Default: 'docx'. (string, one of: docx, pdf) |
| `--filename` | No | [export] Optional custom filename (without extension). If not provided, the original document name is used. (string) |
| `--query` | No | [search] Search query to find documents by name or content. (string) |
| `--limit` | No | [search] Maximum number of results to return (1-50). Default: 10 (integer) |

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
