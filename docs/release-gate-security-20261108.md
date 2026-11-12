# Release gate — security, payments and customer journey (2026-11-08)

**Status: BLOCKED / NOT APPROVED FOR PRODUCTION.** This is a review record, not a claim that all checks passed. It is intentionally isolated from `main`. No customer data, live webhooks, real payments or production configuration were used.

## Evidence inspected (GitHub PR metadata and selected source/patches)

| Severity | Area | Evidence | Remaining gate |
|---|---|---|---|
| CRITICAL | Payment activation | PR #148 corrects annual selection copy; `src/web/templates/pricing.html` renders prices from `plans` and VAT via `vat_enabled()`. Neither establishes payment processor approval or verified live webhook. | Obtain provider contract/activation evidence through authorized owner workflow; test signed webhook, idempotent settlement and sandbox before enabling any live checkout. Keep activation copy conditional. |
| HIGH | OTP / magic link | PR #137 adds PostgreSQL row locking but explicitly reports no real concurrent PostgreSQL test; PR is currently conflicting with main. | Reproduce two concurrent token consumptions on a disposable PostgreSQL database, assert exactly one success, then test OTP issuance rate-limit race and proxy/IP trust. |
| HIGH | Telegram webhook | PR #137 authenticates before body read and bounds request size; not merged. | Test missing/invalid secret, oversized signed request, valid request and no secret/body logging. |
| HIGH | WhatsApp webhook | PR #138 checks signature before reading body, limits signed request to 1 MiB, removes signature prefixes from public diagnostics; patch inspected. | Run full CI, confirm compatibility with Meta's actual payload sizes using synthetic fixtures; test no body in logs; verify retries/idempotency and runtime configuration separately. |
| HIGH | Financial intent / invoice | PR #147 keeps WhatsApp payment-link drafts pending owner review but explicitly does not cover all financial auto-responses or Meta connectivity. | Prove every invoice/payment-link creation route is fail-closed pending owner approval; test retry, duplicate delivery, opt-out and permission to contact. |
| HIGH | Owner session | PR #124 rejects malformed/future timestamps, but CI is not reported as run on that PR. | Run regression tests; verify cookie rotation, expiry, CSRF and tenant/owner boundaries. |
| HIGH | Tenant isolation and document delivery | PR #150/#152 contain proposed QA and tenant gates, not production-proven. | Synthetic cross-account download tests, revoked/expired tokens, altered file hash, QA failure and restart recovery on real disposable PostgreSQL. |
| MEDIUM | Pricing UX | PR #148 reports local 1957 passed and browser checks at 320/390/1280px, but GitHub CI status is not proven by the metadata read. | Verify on latest head; test Arabic/English annual renewal/setup fee and catalog single-source parity. |
| MEDIUM | Company dashboard | PR #152 describes anonymous aggregated funnel separated from contactable leads; branch not merged. | Validate counts using synthetic events, permissions and no imported/customer data leaks. |
| MEDIUM | Resource budget | PR #153 describes 512 MB Render limits and bounded handoffs. | Benchmark peak RSS and concurrent jobs under 512 MB with realistic synthetic artifacts. |
| MEDIUM | Offsite backup | Separate scheduled backup exists, but this audit did not fetch a current verified restore report. | Require timestamped encrypted offsite artifact and recent successful restore report; never restore into production. |

## Source facts and important caveats

- On 2026-11-08, PRs #124, #137, #138, #147, #148 and #135 were open. #137, #147 and #135 reported merge conflicts. Open does not mean deployed.
- The combined commit-status API returned an empty `statuses` array for heads of #137 and #148. **This is not evidence of green CI**: GitHub Checks/Actions must be examined independently.
- A previous user report said Moyasar fees had been paid; that alone does not prove a signed contract, account activation or working webhook. Do not remove or enable payment providers based on that report alone.
- `src/web/templates/portal.html` currently includes external font and Font Awesome stylesheets; accessibility and brand consistency need a separate review, not an untested blanket removal.
- `README.md` claims 194 passing tests, which is inconsistent with later PR-reported suites above 1900. Documentation test counts must not be treated as current CI evidence.
- `src/web/catalog.py` was **not found** at the assumed path. Locate the actual canonical catalog before touching any price logic. No pricing values are approved for hardcoding.

## Reproducible non-production acceptance commands (NOT executed in this review)

```bash
python -m pytest -q --disable-socket --allow-unix-socket
python -m pytest -q tests/test_whatsapp_integration.py
```

Before running tests: install the project's locked dependencies in an isolated environment, select an ephemeral database, and confirm test fixtures cannot reach live providers. The test suite may require different flags depending on the installed pytest plugins. Run browser/Playwright CI workflows on the actual PR head; preserve run IDs, hashes and screenshots. For concurrency tests use disposable PostgreSQL, not SQLite or production Neon.

## Release decision

**NO-GO.** Required sequence: (1) reconcile conflicting security PRs into isolated reviewed branches; (2) run negative and concurrent tests; (3) verify pricing/portal and anonymous metrics with synthetic data; (4) establish provider activation and webhook evidence without changing live settings; (5) run full CI/browser and staging E2E, plus independent offsite restore evidence; (6) request explicit owner approval before merging any PR to `main` or triggering Render auto-deploy. Do not claim a security guarantee or payment readiness from code review alone.

References: [#124](../pull/124), [#137](../pull/137), [#138](../pull/138), [#147](../pull/147), [#148](../pull/148), [#135](../pull/135), [#150](../pull/150), [#152](../pull/152), [#153](../pull/153).
