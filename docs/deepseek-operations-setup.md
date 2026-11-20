# DeepSeek + OpenCode for Al-Narjis AI — safe setup

This is an **agent configuration**, not proof that any third-party account, MCP, video provider or production integration is connected.

## Baseline
- Source-of-truth repo: `CLAUDE.md`, `docs/design-system.md`, `docs/AGENT_TOOLS.md`.
- Existing backend: FastAPI/Jinja/async SQLAlchemy, **not** a Next.js project.
- Agents: `.opencode/agents/narjis-deepseek.md` and scoped subagents.
- No new paid dependencies or production changes in this PR.

## Operator steps (local OpenCode, not GitHub)
1. Update OpenCode to a compatible version. In OpenCode enter `/connect`, select the **DeepSeek** provider and authenticate securely in the provider UI; do not put credentials in repository files.
2. Enter `/models`, choose the DeepSeek model available to the account. Use the **narjis-deepseek** agent from the agent picker. DeepSeek API use can incur charges and chat subscription access does not imply API entitlement.
3. Verify in a **read-only** task: “Inspect the current repo and return the current production commit, relevant routes and missing integrations; do not edit or send.”
4. Grant write access to a **feature branch/worktree only** after review. Keep external actions approval-gated. For independent audit, select `narjis-qa-security`.
5. Configure GitHub access using OpenCode built-in Git/credential manager or an approved MCP server with repo-scoped least-privilege tokens. Never store MCP auth keys in committed JSON. Do not enable arbitrary filesystem outside project.
6. Only then add **optional** service connectors individually, test read-only and record provider-acknowledged results. Do not infer “connected” from config or code.
7. Before any release, check CI, PostgreSQL migration rehearsal where relevant, staged E2E, backup restore evidence and explicit owner approval.

## Capability matrix
| Feature | Implemented in this PR | Requires external setup |
| --- | --- | --- |
| DeepSeek orchestration instructions | Yes | DeepSeek authenticated in OpenCode |
| Code editing | Role/instructions only | OpenCode + Git branch permissions |
| Review/testing | Role/instructions only | Runtime/CI and approved read-only checks |
| Images/video | Script/coordination only | Configured image/video API and spending authorization |
| Vision | Request/route by supported external model | Gemini or other vision API access |
| Google mail/calendar/drive | Audit guidance | OAuth/account permission, API integration to Narjis |
| Salla/Zid/WhatsApp/Telegram | Audit guidance | Credentials, permissions, webhook and staged tests |
| Moyasar | Audit guidance | Authorized sandbox/read-only setup |
| Deploy | **Not enabled** | Separate approval + rollback gate |

## No-cost policy
Do not auto-install TestSprite, premium video APIs, cloud services or paid MCPs. Use existing pytest/E2E/CI first. Free tiers and trial balances are not assumed. Run an approved tiny test only after pricing/limits are confirmed.

## Acceptance checks
- Agent picker displays primary agent and four subagents.
- DeepSeek successfully reads `CLAUDE.md` using OpenCode.
- Engineer creates an isolated change + draft PR without touching main.
- QA flags false connectivity claims.
- Integration auditor reports accurate VERIFIED/UNVERIFIED/BLOCKED statuses.
- Media director prepares a real storyboard without triggering paid generation.
- Production/marketing/payment actions remain blocked pending explicit approval.

## First assignment
Audit why queued lead discovery, Gmail sent messages, CRM and company task runner do not form a provider-acknowledged revenue pipeline. Review PRs #170, #174, #175 and #177, document conflicts, and propose isolated tests and the smallest possible corrective branch. Do not merge or deploy.
