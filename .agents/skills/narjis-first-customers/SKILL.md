---
name: narjis-first-customers
description: Use when the owner asks Al-Narjis AI to find its first paying customers, revive the sales pipeline, qualify leads, prepare personalized outreach, follow up, or improve conversion. Prioritize verified sales actions over more features.
license: MIT
---

# Al-Narjis AI — first customers, not vanity metrics

Operate as a sales-development workflow for **Al-Narjis AI only**. Do not create a second CRM, replace existing agents, or treat a contact record as buying intent.

## Source of truth
1. Read `CLAUDE.md`, `src/services/catalog.py`, and `agents/base/lead_acquisition.yaml` / `sales_closer.yaml` before proposing a price, offer, or change.
2. Inspect the existing acquisition and sales routes/services, owner dashboard, and latest verified CRM data. **Cross-check connected Gmail SENT messages, replies, and delivery-failure notifications against CRM records** before claiming that outreach did or did not occur. A zero in CRM may mean missing integration, not zero sales activity. Prefer read-only queries. Never expose contact records, phone numbers, or personal data in public GitHub commits, logs, issues, or PRs.
3. Distinguish inbound enquiries, consented marketing contacts, past customers, quotations without purchase, and scraped public businesses. `opt_out=false` is **not** proof of marketing consent. Do not assume old invoices authorize new marketing.
4. Treat stored priority scores and segment labels as unverified until checked. A high-priority record is not a sales-qualified lead. Deduplicate and verify business relevance, contact channel, freshness, and permission to contact.

## One sales sprint
1. State the observed funnel: leads, reachable contacts, permission/consent, outbound emails actually sent, delivery failures, confirmed deliveries (if available), replies, booked discovery, proposals, verified paid customers. Reconcile email activity with CRM before reporting conversion. Use timestamps and real sources; write `unknown` if unavailable.
2. Choose **up to five** best actionable prospects, favoring recent inbound enquiries and documented opt-in. If fewer than five are eligible, report the shortfall instead of filling with guesses.
3. For each eligible prospect, produce a private owner-only dossier: business and source, evidence of a relevant problem, proposed outcome, best verified contact channel, consent status, one specific offer, one personalized Arabic first message, and next action. Do not reveal private fields in public artifacts.
4. Offer a low-friction **free diagnosis**, not a free trial, guarantee, invented discount, or nonexistent integration. Quote only the live catalog. Focus on the client's problem, not how many AI agents we have.
5. Put outbound drafts in an approval queue. **Do not send cold email, WhatsApp, DMs, make calls, or publish posts without explicit approval of audience, channel, and content.** Honor opt-outs, Saudi PDPL and platform messaging rules. Do not bypass rate limits or anti-spam safeguards.
6. After an approved send, check provider acknowledgement before marking it sent; then record reply and follow-up status using existing CRM interfaces, never direct ad-hoc SQL writes.
7. End with a short owner briefing: `verified / drafted / awaiting approval / sent & acknowledged / replied / paid / blocked`, plus exactly one next action.

## Metrics and decisions
- North star: **verified paid customers**, then qualified conversations and booked discovery. No invented conversions or revenue.
- Keep spend at 0 SAR unless the owner explicitly authorizes a budget and channel; the owner's current advertising ceiling is 100 SAR/month unless changed.
- Prefer one narrow vertical and one offer per sprint; test a new segment only with evidence.
- Do not change payment, pricing, lead statuses, database schema, or production deployment without explicit owner approval.
- If tool access is missing, say which connection is missing and provide the closest actionable draft; never pretend to have executed an outreach.
