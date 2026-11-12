# Changelog

All notable changes to Al-Narjis AI are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The public copy of these notes is [https://karmaai.online/changelog](https://karmaai.online/changelog)
(Arabic at `/ar/changelog`, English at `/en/changelog`).

1.0.0 is the first numbered release. The notes below are taken from git history
on `main`. The owner publishes the GitHub release after this pull request is merged.
Do not tag it from a pull request.

## [1.0.0] - 2026-11-12

### Added

- Public API reference at `/docs` and the spec at `/openapi.json`. The document
  lists customer routes only. Admin, owner, webhook, and payment-test routes are excluded.
- Public status page at `/status` and a cached JSON feed at `/api/status`
  (site, `/health`, the customer portal, and the agent registry).
- What's-new page, a draft service-level page (figures need the owner's approval),
  and a partnerships page with the white-label offer.
- `/signup` redirects to signup in the customer portal at `/portal`.

### Changed

- Guest checkout is live Moyasar card payment (mada, Visa, and Mastercard).
  Guest bank transfer is removed. Moyasar webhook verification is accepted.
  (9 November 2026, #160; 12 November 2026, #164.)
- Search improvements: one public page per agent, hreflang alternates, `llms.txt`,
  and a fix for English locale redirects. (11 November 2026, #163 and #162.)
- Six public service pages shipped on 17 October 2026 (#78): automation, chatbots,
  graphic design, UI/UX, content writing, and translation.
- The public roster is 39 agents, led by the AI CEO. The count comes from the
  live catalog (`src/services/catalog.py`), not from a hard-coded list.

[1.0.0]: https://github.com/mohammedalhashmi182-collab/Al-narjs-ai/releases/tag/v1.0.0
