# Release notes — 1.0.0

Draft for the owner. Do not create the GitHub release or the `v1.0.0` tag from
the pull request. Publish this after `tests / pytest` is green and the pull
request is squash-merged.

**Tag:** `v1.0.0`
**Title:** Al-Narjis AI 1.0.0
**Target:** `main` after merge

## Summary

First numbered release of Al-Narjis AI, the Arabic-first platform at
https://karmaai.online. An AI CEO plus 39 agents, customer portal, and live
Moyasar card checkout (mada, Visa, Mastercard).

## What shipped before this version number

These are already on `main`. The dates are from git history.

- Live Moyasar guest checkout, and webhook verification (9 and 12 November 2026).
- Search work: per-agent pages, hreflang, `llms.txt`, English locale redirects
  (11 November 2026).
- Six public service pages (17 October 2026).
- The public roster is 39 agents.

## What this release adds

- Customer API reference at `/docs`, ReDoc at `/redoc`, spec at `/openapi.json`.
  Admin, owner, webhook, and payment-test routes are not in the spec.
- Status page (`/status`, `/ar/status`, `/en/status`) and `GET /api/status`.
- Changelog, draft service level, and partnerships (including white-label prices).
- `/signup` redirects to the customer portal.
- `CHANGELOG.md`, `CONTRIBUTING.md`, and the docs in this folder.

## Owner review before publish

- Service-level figures on `/sla` are a draft (`OWNER_REVIEW_REQUIRED` in
  `src/services/sla.py`). Confirm or edit the 99.5% target, the 8 business-hour
  reply on the 2,990 SAR plan, and the credit table before treating the page
  as a commitment.
- White-label prices are the ones requested for this page: hosted 4,900 SAR
  setup + 1,490 SAR/month, standalone 9,900 SAR setup + optional 1,000 SAR/month
  support.
- Salla, Zid, and WhatsApp Business are marked in development. No dates.

## Publish steps (owner)

1. Merge the pull request with squash only after `tests / pytest` is green.
2. On `main`, create tag `v1.0.0` and a GitHub release.
3. Paste this file as the release body, minus this "publish steps" section if
   you prefer a shorter note.
4. Optional: add the GitHub topics in `docs/github-topics.md`, and the
   UptimeRobot monitors in `docs/status-monitoring.md`.
