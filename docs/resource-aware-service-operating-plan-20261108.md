# Resource-aware operating plan — Al-Narjis AI

Date: 2026-11-08. Status: engineering plan, not a production approval.

## Verified current resources
- Render web service Al-narjs-ai-1: single Docker instance, 0.5 CPU and 512 MB memory, Frankfurt; auto-deploys main; PR previews disabled.
- Memory used in observed Render samples November 7–8: approximately 169–187 MB. Average CPU readings around 0.0017–0.0020 cores. These represent current sampled load, not peak demand or a load test.
- One Uvicorn process; current workflow state is in-memory. PR #150 contains a collaborative team pilot and fail-closed DocPack review. PR #151 removes the oversize homepage intro. Neither PR is merged.
- Payment, Moyasar and IBAN are explicitly excluded until the owner separately authorizes integration.

## Decision: keep the production site lightweight
Keep FastAPI and the existing database for customer interfaces and future durable jobs. Run no Ollama model, OpenHands instance, permanently running browser, or broad scraped-data worker on the 512 MB website. Use external model endpoints through the existing model abstraction and isolate heavy jobs only after measuring their need.

## Executive-team workflow
1. Capture the client's actual objective, project identity, scope and required deliverables.
2. The chief executive creates typed task graph, dependencies, tool permissions and acceptance criteria.
3. Specialists work concurrently only when dependency and provider quotas permit; dependent handoffs contain only their predecessors' approved results.
4. Handoffs are bounded by size; if final QA cannot inspect all required evidence, fail closed instead of truncating and pretending it reviewed the whole job.
5. All lasting commitments must move from in-process tasks into database-backed journal, with versioned transitions, leases, retries, idempotency and a transactional outbox for any external message.
6. Each deliverable is independently checked against the client's original requirements, source provenance and SHA-256 of exact files, then held in encrypted tenant-isolated storage until authorized delivery.
7. An unknown payment status, unapproved outbound action, failed review or expired lease enters a supervised exception queue.

## Tool adoption decisions
| Tool | Decision | Reason |
| --- | --- | --- |
| OpenHands | Dev-only sandbox outside production | Official legacy setup recommends at least 4 GB RAM; current production has 512 MB. Build/test PRs with no live credentials. |
| Awesome LLM Apps | Reference and selective sample review | Reuse architecture patterns, not entire agents or unrelated dependencies. Validate licensing, boundaries and test behavior per sample. |
| Awesome MCP Servers | Directory only | Approve individual read-only MCP servers and narrow permissions; no general access to production DB, shell or secrets. |
| Ollama | Do not install on production | Model inference and large contexts need more memory/compute than this instance affords. Evaluate later on separate compute with real benchmarks. |
| Scrapling | Optional bounded research worker | Start with compliant static-page fetching; honor robots and terms, rate limits and privacy. Do not use anti-bot bypass or headless browser on site host. |
| free-for-dev | Cost research, not software | Compare free-tier limits, regions, data handling, longevity and cost after upgrades before adopting a vendor. |

## Risk register and exact controls
| Risk | Control / test |
| --- | --- |
| Process restart loses a paid job | Persist each state and event; expired lease recovery must resume from last committed step. |
| Duplicate delivery or follow-up | Per-project idempotency keys plus per-side-effect unique key; replay cannot resend. |
| Cross-customer files | Enforced project authorization at every DB/object read; test revoked and unrelated sessions. |
| Unbounded agent token cost | Set per-task budgets, bounded handoffs, model quotas and timeouts; record usage per project. |
| Reviewer misses omitted evidence | Fail closed for incomplete handoffs; use evidence manifests and exact file hashes. |
| Tool response tries prompt injection | Treat tool results as data, enforce server-side permission and approved MCP allowlists. |
| Scraper overload / compliance | No bypass of access controls, only approved domains, quotas and timeout; external worker if needed. |
| Analytics visitor treated as contactable lead | Visits aggregated anonymously; contact only on explicit opt-in and known contact method. |
| Receipt interpreted as paid | Financial code remains unchanged until authoritative payment integration is separately authorized. |

## Next milestones and release gates
1. UX: Review PR #151 on mobile, verify screenshots and explicit release approval.
2. Team: Review PR #150 plus this stacked bounded-handoff patch; verify CI, no source-code execution from peer text.
3. Persistence: Continue existing feat/service-fulfillment-journal-20261107 branch, do not re-create its models. Add Alembic migration, isolated artifact encryption, lease recovery and replay tests. Do not bind it to payments yet.
4. Owner: Make opt-in leads, anonymous funnel visits, followups due, open jobs and failures visible in a coherent RTL dashboard; use real evidence or show unavailable.
5. Synthetic E2E: one fake client brief to assigned agents to QA to encrypted artifact to authorized download with restart/crash scenarios. No real user data or payment.
6. Rollout: verify backup/restore, latest CI, security review, isolated smoke, rollback plan and explicit approval before main merge. Render deploys main automatically.

## Sources
- https://github.com/OpenHands/docs/blob/main/openhands/usage/run-openhands/local-setup.mdx
- https://github.com/Shubhamsaboo/awesome-llm-apps
- https://github.com/punkpeye/awesome-mcp-servers
- https://github.com/ollama/ollama/blob/main/docs/context-length.mdx
- https://github.com/D4Vinci/Scrapling
- https://github.com/ripienaar/free-for-dev
- https://community.owasp.org/attacks/MCP_Tool_Poisoning

No external software installed, no Render or production environment changed, and no financial code touched.
## Lightweight production checks before any adoption
- Record peak RSS, P95 HTTP response latency and failure rates during a synthetic 1/3/5-client test. Never extrapolate from the idle CPU sample.
- Prefer read-only HTTP integration without browser installs; verify each tool's cost per useful completed customer task, and keep a rollback switch.
- Do not mix payment-confirmation authority with model-generated conclusions; payment work is intentionally deferred.
- This PR is separately reviewable and is based on PR #150; PR #152 must be reconciled to avoid parallel edits to the same execution engine.
