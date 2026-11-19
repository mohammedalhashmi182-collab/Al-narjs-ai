# Narjis AI — release integration gate (19 November 2026)

**Status: BLOCKED pending code integration and production validation.** This is a work record, not proof of deployment.

## Verified GitHub evidence
- Main baseline observed: `519a49e50a60cc556fbffe2c5a114e76446501a2`; recheck before merging.
- [PR #175](https://github.com/mohammedalhashmi182-collab/Al-narjs-ai/pull/175) draft, open, unmerged; head `698b91e387fcea72b411ebb5d7e4a32f51368d37`. GitHub Actions run `44366122537`: pytest, ruff and security successful. Locally reported: 2108 Python and 42 Chromium tests.
- [PR #174](https://github.com/mohammedalhashmi182-collab/Al-narjs-ai/pull/174) draft, open, unmerged; Actions run `44253670919`: pytest failed, ruff and security successful. Some changes have been selectively reapplied in #175.
- [PR #173](https://github.com/mohammedalhashmi182-collab/Al-narjs-ai/pull/173) open, unmerged; Actions run `43913648207`: pytest, ruff and security successful.
- [PR #171](https://github.com/mohammedalhashmi182-collab/Al-narjs-ai/pull/171) open, unmerged, not mergeable; branding, voice and owner features overlap.

## Verified integration blocker: revenue funnel

The #175 release documentation still identifies **Alembic head 0018**. #173 adds `alembic/versions/0019_revenue_funnel_tracking.py` plus:
- Append-only funnel events, lead identity aliases, lead consent records, follow-up callbacks and signed payment-lead links.
- Message lifecycle semantics: drafts and accepted messages are **not** proof of sending; sent requires Message-ID; delivered requires independent delivery evidence.
- Consultation-to-follow-up scheduling and owner funnel metrics.
- Fixture-only read-only Gmail reconciliation; **no live Gmail reconciliation has occurred**.

**Do not claim #175 contains or has deployed #173's revenue tracking.** A simulated checkout in #175 does not prove live Moyasar or webhook reconciliation.

## Minimal integration tasks
1. Re-fetch main and PR head SHAs. Diff #173 against #175, especially `src/main.py`, `src/interfaces/sales_routes.py`, and `src/services/company_task_runner.py`.
2. Integrate only missing #173 features into a branch based on #175, with the associated tests and 0019 migration; avoid blindly merging PR #173 or #174.
3. Verify one linear Alembic head and an upgrade against an isolated, production-shaped database copy. Do not run migrations on production during testing.
4. Retest consultation → lead → consent → agent task → tracked message → reply → proposal → sandbox payment → owner dashboard, including duplicate callbacks and isolation/authorization.
5. Resolve PR #171 overlaps only after targeted comparison; do not overwrite newer voice/brand changes.
6. Review security findings, browser/mobile accessibility, realtime voice, backup encryption/SHA-256/restore evidence, and independent staging environment.
7. Record target deployment platform and currently live commit; do not assume Render or Vercel from repository config.
8. After all gates pass, merge reviewed PRs and deploy to the confirmed production service with a rollback record and post-deploy smoke tests. If an automatic main deployment is configured, merge itself is a production action.

## Production authorization boundaries
The owner has requested that successful, approved changes be **executed and deployed**, not merely documented. Still: never invent passing evidence; do not perform real payments, outbound messages, or potentially destructive production migrations without the necessary explicit transaction-specific confirmation and rollback readiness. Respect production secrets, customer data, and owner approval at each irreversible boundary.

## Unverified at this stage
Production deployment SHA, isolated staging environment, live Moyasar success, live voice vendor and browser performance, encrypted database backup outside Neon, completed restore test, and exact review/CI of a consolidated integration head.
