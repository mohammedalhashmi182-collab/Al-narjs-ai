# Emergent experiment B — Standalone Al-Narjis AI prototype

## Goal
Build a separately deployable, isolated prototype to compare with the existing site. This experiment branch contains requirements, not a completed application.

## Isolation
- Build on `experiment/emergent-standalone` or on a separate repository once safely exported from Emergent.
- Separate environment, mock data and test accounts only; no production Neon connection, no Moyasar live credentials, no production webhook or Render deployment.
- Do not overwrite `main`, live domain, or existing app. No external customer messages.

## Product requirements
- Saudi Arabic-first RTL luxury visual language, palette: #12100D, #1C1915, #F4EEE2, #C9A27A, #FF5A36; avoid purple and gratuitous 3D gradients.
- Landing: floating luminous `النرجس` name; short clear proposition; real consultation CTA; responsive accessible mobile.
- Flow: consultation -> intelligent executive diagnosis -> select specialist agents -> auditable task steps -> review -> client deliverable.
- Client portal: authentication, projects, state, agent outputs, downloadable deliverables, tenant isolation.
- Owner console: anonymous visitor aggregates, lead funnel, project/agent activity, error logs, permissions.
- Voice experience: dark waveform, young friendly Arabic voice if supported, consent and fallback text UI; no provider promises without testing.
- Pricing: controlled by catalog, clearly marked estimates until verified; mock checkout only.

## Acceptance checklist
1. Functional journeys across RTL mobile/desktop and English fallback where included.
2. Automated tests including auth isolation, retries, failures, and accessibility.
3. Cost per conversation/project and infrastructure pricing, with assumptions disclosed.
4. Security and privacy review; no hardcoded credentials or customer data.
5. Side-by-side scoring vs current site: design, functionality, security, performance, accessibility, operating cost, maintainability.
6. Exportable source and reproducible deployment instructions.

## Decision gate
No production replacement until the owner reviews a demo, test evidence and rollback plan and explicitly approves.
