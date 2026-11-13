# Emergent experiment A — Existing Al-Narjis AI

## Goal
Safely assess and improve the existing site at karmaai.online without production changes.

## Safety boundaries
- Work only on `experiment/emergent-existing-site`; do not commit to or merge into `main`.
- Do not trigger Render deployments, database migrations, payment transactions, or production API calls.
- Do not expose secrets, production databases, customer details, WhatsApp numbers, or live Moyasar keys to external builders.
- Require owner approval before any merge, release, external message, or connector write beyond this branch.

## Baseline
- Read `README.md`, `src/main.py`, `src/services/catalog.py`, templates, automated tests, and open pull requests.
- Treat README claims as documentation until confirmed by tests or runtime evidence.
- Record test baseline and defects with reproduction steps.

## Workstreams
1. Audit production-adjacent risk: authentication, tenancy, payments, webhooks, idempotency, rate limits and async jobs.
2. Improve Arabic RTL responsive customer experience and the premium Najdi visual identity; no purple, no misleading claims.
3. Prototype the floating `النرجس` hero and refined voice assistant UI with accessible reduced-motion fallback.
4. Review owner dashboard metrics, visitor anonymity, agent execution log, and customer delivery flow.
5. Keep payment integrations behind sandbox/mocks, and never change live endpoints.

## Validation & deliverables
- Tests: unit, integration, browser mobile/desktop, security regression, accessibility.
- Report: before/after screenshots, verified results, cost estimates, blockers, rollback strategy.
- Submit a draft PR into `main` only after code review, but never merge without explicit owner approval.
