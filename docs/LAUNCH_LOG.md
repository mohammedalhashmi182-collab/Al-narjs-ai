# Launch log: Al-Narjis AI (karmaai.online)

Running log. No secrets. Times are Asia/Riyadh (UTC+3).

## 2026-10-24: Phase 1

### Project state (verified)
- main @ e96da51: PR #91 (VAT read from settings; 0 for a non-registered operator).
- Branch `launch/readiness` was cut from origin/main in a separate worktree. The existing checkout (`fix/extra-agent-price`) has 24 uncommitted changes (deleted campaign creative files) plus `stash@{0}` (agent-knowledge WIP). Nothing was touched or discarded.
- Prices 790/1,490/2,990 SAR are pending the owner's decision and were not changed.

### Decisions
- D1: Fix visibility bugs first. They hide the plans the customer has to pick at the payment step.
- D2: Remove the bare `.grid{opacity:.25}` rule. No template renders an ambient `.grid` layer, so the rule only ever hit Tailwind's `.grid` utility (#pkg-grid).
- D3: Reveal-on-scroll is decoration. Content must become visible even if the IntersectionObserver never fires. Added: elements already in view reveal at once, `beforeprint` reveals everything, and a 3 s fail-safe reveals everything.

### Done (with evidence)
- /portal #pkg-grid computed opacity: live 0.25 → branch 1 (Playwright, 390 and 1440).
- Home `.rv`: live, 0 of 44 visible after 3.5 s without scrolling (full-page captures, some webviews). Branch: 44 of 44 visible after 3.5 s. Real scrolling reveals all 44 in both.
- Tests: new tests/test_visibility_regressions.py. Full suite: 1658 passed, 14 skipped, 1 failed. The failure is test_store_integrations::test_flag_defaults_off..., KeyError 'bay', and it also fails on clean main, so this branch did not cause it.
- Screenshots: /workspace/launch/shots/{before,after}_{home,portal}_{390,1440}.png (box only).

### Blockers
- Moyasar: no MOYASAR_* setting exists on the Render service, so card payment cannot collect yet (account not live-approved).
- No object-storage or email/SMTP settings found, so delivery files and email notifications are unproven.

### Next
See the PR description, "recommended order".
