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

## Cost-aware DeepSeek onboarding (20 November 2026)

1. Open the official [DeepSeek Platform](https://platform.deepseek.com/) and generate an API key. Do not paste or commit it. **Do not purchase anything without reviewing the checkout and approving the amount.**
2. In the already-installed OpenCode, run `/connect` → DeepSeek, provide your key only in the secure OpenCode prompt; then `/models` → select **`deepseek-flash`** if offered. The official model/pricing docs use `deepseek-flash`, the current V4.1 Flash model ID. If the UI offers only an older name, inspect current provider model list before selecting it.
3. Keep the existing optional `genspark-llm-proxy` config untouched; no new token, provider, API key or service is configured in this PR.
4. Start with read-only questions; keep cost low by using small targeted context, not repeatedly dumping the entire repository. Prefer existing CI over optional paid QA platforms.
5. Suggested initial spend ceiling: **USD 5 total** only if the DeepSeek console actually supports a configurable cap or prepaid budget. If it does not, stop manually and monitor usage in the console. Do NOT claim that a cap was applied without an acknowledgment.
6. DeepSeek's official published model API rates on 2026-11-20 are [here](https://api-docs.deepseek.com/quick_start/pricing/). Flash input cache miss off-peak USD 0.15 / 1M tokens, peak 0.30; output off-peak 0.60 / 1M tokens, peak 1.20. Prices can change; cache-hit pricing differs. Use only official billing data to estimate cost.
7. Before requesting an MCP connector to Github, Google, Render, WhatsApp or an image/video service, verify authorization scopes, billing, webhook integrity, and data-access boundaries. Third-party image/video generation is not enabled by the DeepSeek key alone.

### First acceptance command to run in OpenCode

```text
Use narjis-deepseek. Read CLAUDE.md, docs/design-system.md, and docs/AGENT_TOOLS.md. Inspect PR #179 and agent roles. Perform a read-only inventory of lead funnel, queued tasks and Gmail CRM synchronization. List files, proof, integration gaps and estimated token cost. Do not edit files, send messages, publish, spend, or deploy.
```
