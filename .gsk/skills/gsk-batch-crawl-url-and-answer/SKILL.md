---
name: gsk-batch-crawl-url-and-answer
version: 1.0.0
description: 'Crawl multiple URLs in parallel and answer specific questions from each.
  Returns extracted answers with quotes, NOT the original page text — use crawler
  when the original content is needed. Input: list of {url, questions_to_answer} jobs.'
metadata:
  category: general
  requires:
    bins:
    - gsk
  cliHelp: gsk crawl-and-answer --help
---

# gsk-batch-crawl-url-and-answer

**PREREQUISITE:** Read `../gsk-shared/SKILL.md` for auth, global flags, and security rules.

Crawl multiple URLs in parallel and answer specific questions from each. Returns extracted answers with quotes, NOT the original page text — use crawler when the original content is needed. Input: list of {url, questions_to_answer} jobs.

## Usage

```bash
gsk crawl-and-answer [options]
```

**Aliases:** `crawl-and-answer`, `batch-crawl`

## When to Use

Use this command when you need focused answers from two or more URLs. It crawls the jobs in parallel, so it is faster than serial `gsk crawler` calls. Use `gsk crawler` for one URL or when you need the full page rather than answers to specific questions.

Some sites block automated access. Prefer official or otherwise reliable sources, and do not retry an identical failed job repeatedly; switch source or report the URL as inaccessible.

## Example

```bash
gsk crawl-and-answer '[{"url":"https://openai.com/pricing","questions_to_answer":["What are the pricing tiers?"]},{"url":"https://www.anthropic.com/pricing","questions_to_answer":["Which models are listed?"]}]'
```

## Flags

| Flag | Required | Description |
|------|----------|-------------|
| `<jobs>` (positional) | Yes | A list of objects, each containing a URL to crawl and a list of questions to answer from that URL. (array) |

## See Also

- [gsk-shared](../gsk-shared/SKILL.md) — Authentication and global flags
