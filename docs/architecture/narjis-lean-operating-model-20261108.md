# Al-Narjis AI — lightweight autonomous-company operating model

Assessment: 2026-11-08. Draft engineering implementation: PR #152 on top of PR #150.
**No production deployment. Payment, Moyasar and IBAN remain outside scope.**

## Verified constraints

- Connected Render service Al-narjs-ai-1 is one Docker web instance on 0.5 CPU / 512 MB RAM in Frankfurt. It automatically deploys commits to main.
- Local Render filesystem is ephemeral. Existing short-lived DocPack PACKS state is in process memory and cannot survive a restart.
- The source code already provides an agent runtime, WorkflowEngine, client projects, owner console, customer funnel, and Postgres/Neon persistence.
- The system does not yet demonstrate a paid, automatically fulfilled and safely delivered client transaction.

Evidence: Render compute docs https://render.com/docs/compute-plans and filesystem docs https://render.com/docs/faq ;
existing code src/automation/workflow_engine.py, src/core/state_manager.py,
src/services/docgen/store.py, src/services/funnel.py.

## Evaluation of the six candidate tools

| Tool | Real benefit | Cost and security concern | Decision |
| --- | --- | --- | --- |
| OpenHands | Separate developer/test agent | Docker sandbox, code-execution permissions, memory and CPU overhead | Evaluate off the visitor server; never put it inside Render web process |
| Ollama | Self-hosted AI inference | Common 7B models need multiple GB RAM, beyond current 512 MB | Defer until separate measured infrastructure is justified |
| Awesome LLM Apps | Examples of multi-agent patterns, RAG and communication | Examples may be unmaintained; check licenses and tests per sample | Study small patterns; do not bulk-install |
| Awesome MCP Servers | Directory of real external connectors | Server permissions and prompt-injection trust boundaries | Whitelist one specific connector at a time, prefer read-only |
| Scrapling | Authorized public-web research for agent | Scraping policies, personal data, rate limits and bypass features | Defer; use official sources and authorized APIs first |
| Free-for-dev | Identify useful free tiers | Limits and terms change, may store customer data with vendors | Use as cost research only, no automatic registration |

Official/source references:
- OpenHands sandbox documentation https://github.com/OpenHands/docs/blob/main/openhands/usage/sandboxes/docker.mdx
- Ollama models https://ollama.com/library
- Awesome LLM Apps https://github.com/Shubhamsaboo/awesome-llm-apps
- MCP catalog https://github.com/punkpeye/awesome-mcp-servers
- MCP security model https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/SECURITY.md
- Scrapling https://github.com/D4Vinci/Scrapling
- Free-for-dev https://github.com/ripienaar/free-for-dev

## Deployment pattern within existing resources

1. The FastAPI website handles visitor input and authenticated portal responses, not heavy model processes.
2. One executive orchestrator selects only the needed specialists and passes narrowly scoped outputs through an explicit dependency graph. Independent tasks run in bounded parallelism.
3. Postgres stores durable internal job metadata, lease/retry state, event history and small encrypted files. A future job worker can reclaim expired leases; no additional paid service is needed merely to test the journal.
4. Customer delivery requires separate checked authorization, contract/payment gates, an independently reviewed output, and an idempotent external-message outbox. Internal review status is NOT customer delivery.
5. Owner UI displays internal execution status and first-party aggregate funnel events with honest labels. Anonymous visitors are not contactable leads.
6. Larger files need reviewed object storage, retention limits, encrypted backup and key rotation, after a usage assessment.

## Work implemented in draft PR #152

- New additive migration 0019 and SQLAlchemy tables for service offers, jobs, artifacts and journal events.
- Encrypted internal work briefs and files; separate required Fernet key, with no silent fallback.
- Idempotent project request keys, atomic work leases, lease heartbeat, restart recovery and bounded retries. Sanitized failure codes only, no model outputs or personal data in status logs.
- File size limits, QA-bound hash, project isolation and checked decryption before internal reads.
- Owner-only summary API and a new owner dashboard section for job progress and anonymous recorded funnel steps.
- Synthetic tests covering duplicate requests, wrong tenants, stale workers, failed QA, missing secret and recovery simulation.

No new Docker images, AI inference service, broker or paid plans were added. No customer messages or real payment activity were performed.

## Critical release gates

| Priority | Risk | Required evidence |
| --- | --- | --- |
| P0 | Production auto-deploy on main | Green full CI, reviewed PR and explicit release decision |
| P0 | Key loss makes files unreadable | Dedicated key management, staged key rotation, encrypted external backup and restore test |
| P0 | Repeated external send after retry | Persistent effect outbox with provider acknowledgments and deduplication |
| P0 | Another project's files become visible | Portal/session checks, tenant-scoped SQL, expired/revoked-session tests |
| P0 | AI says work completed without proof | Deterministic artifact/tool checks + independent substantive QA; HOLD when uncertain |
| P0 | Payment not ready | Keep gateway and banking code unchanged until owner receives Moyasar keys and approves |
| P1 | 512-MB worker memory pressure | File limits, bounded concurrency, memory/latency monitoring and load tests |
| P1 | DB storage growth | Per-tenant limits, retention policy, archiving and storage cost monitoring |
| P1 | Anonymous visitors treated as leads | Aggregate consent-aware events only; only user-provided authorized contacts become CRM leads |
| P1 | Poor mobile owner experience | Arabic RTL, 320/390/768 mobile tests, keyboard access and error states |

## Next engineering stages (no production work authorized yet)

A. Prove the new journal against an actual isolated Postgres instance and inspect CI on the newest branch head.
B. Connect a trusted internal DocPack executor to the journal, including durable step checkpoints and an outbound-free synthetic end-to-end test.
C. Add a correctly authenticated portal preview read path, expiration/revocation and retention cleanup; still no customer release.
D. Deploy to a staging environment only after backup and approval; measure CPU, memory, token and storage usage.
E. Separately plan financial settlement and customer delivery when the merchant is ready, with explicit approval.

**Success metric:** real task evidence and safe recovery per delivered customer result, not a high agent count or many installed tools.
