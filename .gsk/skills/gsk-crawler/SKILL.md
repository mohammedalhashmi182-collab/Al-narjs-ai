---
name: gsk-crawler
version: 1.0.0
description: Crawl and extract content from web pages. Supports HTML, PDF, and documents.
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk crawl --help
---

# gsk-crawler

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

Crawl and extract content from web pages. Supports HTML, PDF, and documents.

## Usage

```bash
gsk crawl [options]
```

**Aliases:** `crawl`

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<url>` (positional) | Yes | http/https url (string) |
| `--render_js` | No | Enable JavaScript rendering to bypass anti-bot protection (Cloudflare, 403 errors, dynamically loaded content). Use only when the site blocks plain HTTP crawlers or returns no content — this costs significantly more credits than the default crawler. Ignored when raw=true. Default: false. (boolean) |
| `--raw` | No | Return the original response body as decoded text (no markdown conversion). Use when you need raw HTML, meta tags, JSON, or other unprocessed content. Text-only: requests with a binary Content-Type (image/video/audio/pdf/zip/Office) are refused — use the sandbox bash tool with curl/wget for those. Returns at most 10000 bytes per call — pass offset to fetch the next chunk. Default: false. (boolean) |
| `--offset` | No | Byte offset to start reading from when raw=true. Use to fetch subsequent chunks of the raw body (e.g. offset=10000 for bytes 10000-19999). Maximum 1048576 (1 MiB) — beyond that, switch to the sandbox bash tool with curl/wget. Ignored when raw=false. Default: 0. (integer, default: `0`) |

## Local File Support

Parameters that accept URLs (`<url>`) also accept local file paths. The CLI automatically uploads local files before sending to the API.

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
