# Al-Narjis AI: agent skills for the first real customers

## What this PR does
Adds three portable `SKILL.md` instructions to `.agents/skills/`:
- `narjis-first-customers`: qualify existing prospects, verify marketing permission, prepare owner-approved outreach, measure real conversions.
- `narjis-chief-of-staff`: choose and complete one highest-impact task per authorized run, coordinate existing agents, report evidence.
- `narjis-code-quality`: branch/PR/test/security gate before any code change.

These skills **do not** deploy a daemon, send messages, change a database, install third-party dependencies, or modify production. The current product's `agents/base/*.yaml` are runtime agent definitions; these Markdown files are **developer coding-agent instructions**, not new customer-facing agents.

## Where they work
OpenCode discovers project skills in `.agents/skills/<id>/SKILL.md`. Start OpenCode from the repository root, then request `@narjis-first-customers` or `@narjis-chief-of-staff`; verify the agent actually loaded the skill. Other compatible coding agents may discover this standard layout; **Grok Bot compatibility must be tested separately**. Do not assume the Grok Windows bot is the same as Grok Build CLI.

## External repositories worth evaluating (not installed by this PR)
- https://github.com/obra/superpowers — disciplined TDD, review, branch workflow; supports OpenCode and Grok Build CLI.
- https://github.com/garrytan/gstack — CEO/product/design/security/QA review roles; mainly a Claude Code workflow; test before adapting.
- https://github.com/albertirgi/replica — measurable visual parity for web UI; requires Node/Playwright and respects asset rights.
- https://github.com/open-gsd/gsd-core — milestone state, fresh-context execution, verification; overlaps with Superpowers, **choose one primary planning framework**.
- https://github.com/vercel-labs/agent-skills — web interface/accessibility/performance checks, stack-dependent.
- https://github.com/unclecode/crawl4ai — optional public-web research; follow site terms, privacy law, and rate limits.
- https://github.com/msitarzewski/agency-agents — reusable sales and marketing role templates; adapt to the existing Al-Narjis agents, do not duplicate the whole roster.

Security rule: no `curl | bash`, `npx ...@latest`, or `--trust` against production credentials before reviewing and pinning a version.

## Owner-visible rollout and acceptance
1. Read-only snapshot: acquisition funnel, Gmail sent/reply/bounce activity and actual payment outcomes, without leaking contact details. Gmail may show outbound sales emails even when CRM has zero `last_contacted_at`; investigate the discrepancy instead of claiming no outreach.
2. Verify consent, relevance and contact freshness for the first five eligible prospects.
3. Prepare five personalized drafts for owner approval; **no auto-send**.
4. After approved contact, record delivery acknowledgements, replies, discovery, proposal and payment through existing services.
5. Check the dashboard against DB counts; repair any discrepancy on a separate branch with tests and a draft PR.
6. To run without repeated chat prompts, configure an explicit scheduler/worker and scoped access separately. Skills alone are not autonomous processes.

No change to `main`, pricing, Moyasar, CRM state, production data, or deployment is part of this PR.
