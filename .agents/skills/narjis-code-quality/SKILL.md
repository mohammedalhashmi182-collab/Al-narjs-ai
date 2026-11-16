---
name: narjis-code-quality
description: Use for any Al-Narjis code change, bug fix, UI redesign, security review, pull request, or release readiness check. Enforce isolated branches, real tests, secure review, and honest verification.
license: MIT
---

# Al-Narjis AI — code quality and release gate

1. Read `CLAUDE.md`, `docs/design-system.md`, affected tests, and recent relevant PRs. Confirm current architecture before proposing new frameworks.
2. Reproduce the defect or write acceptance criteria with evidence. Identify the smallest viable change. For design, preserve the repository's current Arabic/RTL brand contract, accessibility, responsive behavior, and reduced-motion support.
3. Work on a new branch/worktree only. Never commit directly to `main`. Never modify production secrets, payment behavior, pricing, lead status, migrations, or deployment configuration without owner approval.
4. For executable changes: write focused tests where feasible, implement the fix, run `python -m pytest` from the repository root, and inspect CI. Do not claim a test passed if it was not run. Do not weaken tests or skip security checks to get green CI.
5. Review auth, input validation, injection, SSRF, data leakage, cross-tenant isolation, logging, retry/idempotency, external API failures, and failure-safe behavior where applicable.
6. For frontend changes, inspect actual screenshots/browser behavior at desktop and mobile sizes; optionally use Replica to compare a reference with legally reusable assets. A generated screenshot is not a live verification.
7. Prepare a draft PR with changed files, before/after behavior, tests and their actual results, residual risks, and owner decisions. No auto-merge or deploy.
8. When an external GitHub skill/tool is suggested, inspect its repository, license, dependency scripts, install hooks, network access, and permissions first. Pin an audited version before executing third-party code.

Quality is proven by evidence, not by a model's confidence or the number of agents involved.
