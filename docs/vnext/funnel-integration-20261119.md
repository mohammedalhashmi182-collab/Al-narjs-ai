# Revenue funnel integration status — 2026-11-19

Integration target: [PR #177](https://github.com/mohammedalhashmi182-collab/Al-narjs-ai/pull/177) into `main`, **draft only**.

- Base feature set: #175 Narjis vNext.
- Added from #173: canonical identity/aliases, lead callbacks, events, consent and message proof, daily owner metrics, signed payment lead linking, fixture-only Gmail reconciliation, migration `0019_revenue_funnel_tracking`, tests.
- Shared files merged explicitly: `src/main.py`, `src/interfaces/sales_routes.py`, and `src/services/company_task_runner.py`.
- Preserved vNext consent-based attribution from #174 and attached it to newly resolved canonical leads.
- Pending manual validation: original #171 voice and owner feature differences; PostgreSQL `0018 -> 0019` migration on staging; real browser/device voice; payment webhook staging; encrypted off-Neon backup and isolated restore; production SHA and hosting mapping.
- GitHub workflow runs on PRs whose base is `main`; PR #177 targets `main` to collect CI evidence. Green CI alone is **not** production authorization.
- All work remained on a review branch. No production DB migration, external message, real payment, merge or deployment.

## Gate checklist
- [ ] CI pytest + Chromium + ruff + security passes for the **final** PR head SHA
- [ ] Targeted tests verify no funnel hold task auto-executes
- [ ] Test staging PostgreSQL upgrade from `0018` to `0019` and restore/rollback
- [ ] Confirm billing and consent, duplicates, and tenant/owner access protections
- [ ] Validate customer path and mobile/RTL on isolated staging
- [ ] Record live deployment SHA, verified encrypted backup and rollback plan
- [ ] Obtain final release approval then merge/deploy and verify production

**Do not merge automatically; this document records work in progress.**
