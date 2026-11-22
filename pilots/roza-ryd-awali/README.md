# Roza / العوالي — WhatsApp pilot (22 Nov 2026)

**Status:** preparation only. Not deployed, not connected to a customer's WhatsApp account, no messages sent. Source: customer-provided screenshot, held by the owner. No personally identifiable chat transcript or API credentials are committed.

## Existing platform capabilities confirmed from `main`

- `/webhooks/whatsapp` is registered in `src/main.py` and checks Meta webhook signatures.
- `src/services/tenant_reply.py` builds tenant-isolated knowledge-base replies; a project defaults to `reply_mode=review`; lack of customer token keeps drafts queued.
- `/api/owner/projects/{project_id}/whatsapp-number` binds **the customer's** Meta phone_number_id to an authenticated project.
- `src/interfaces/portal_routes.py` already exposes authenticated reply review and customer token configuration.
- `src/services/agent_tools/knowledge_base.py` supports tenant-specific `KnowledgeDoc` entries.

These code-level findings are **not** proof of production connectivity. The public health endpoint could not be read in this session, and the Render workspace listed through the current connection was `My Workspace`, not the previously named `alnarjis`. Do not pick or change that workspace without explicit owner confirmation.

## Source-grounded knowledge

`manifest.json` contains the location, maps, menu and TikTok links supplied by the customer. The menu URL was **not** readable from the web retrieval tool; do **not** claim specific dishes, prices or stock from it. Business hours, delivery availability, allergy information, reservations and checkout terms remain unverified. An independently found website may match the business phone, but its claims are not incorporated until the customer confirms their own details.

## Activation sequence — no surprises

1. Ask the customer for written approval to test AI replies and consent to link their WhatsApp Business account; establish who can approve answers and who receives human handoffs.
2. Confirm location, menu URLs, hours, delivery/ordering policy, allergies and whether the business uses WhatsApp Cloud API. Do **not** request access tokens in chat.
3. Confirm the correct Render workspace, inspect health and deployment status, and perform isolated tests against a Meta test number without adding paid infrastructure.
4. Provision an authorized `demo`/test project in the isolated environment, import only approved `knowledge_docs` via the existing tenant KB service, and leave `reply_mode=review`.
5. Configure customer's phone_number_id and **their own** token through authenticated admin/portal controls; verify webhook signature, inbound message storage, draft generation and the reviewed human approval path.
6. Run the `acceptance_tests` from `manifest.json` on a controlled test number and record exact message IDs, results and failures; check handoffs and opt-out.
7. Obtain written approval to switch `reply_mode=auto` for agreed inbound intents only, and verify a live reply to the customer's test number. Do not enable unsolicited outreach.
8. Treat any opt-in, Meta approved template/window, consumption or conversation cost as a separate gate. Never claim bookings or orders are completed without the customer's booking/order integration.

## Guardrails

- No changes to `main` and no production deploy in this branch.
- No credentials, customer telephone numbers, raw message bodies, or authentication secrets in commits.
- No misleading "sent", "connected", "free", "booked", or "paid" claims.
- This pilot's docs are not automatically imported into any database; `manifest.json` is only a staged source-of-truth for the future authorized demo setup.
