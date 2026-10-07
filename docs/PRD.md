# PRD — Al-Narjis AI: from zero revenue to first paying clients

Status: **active** · Owner: Mohammed Al-Narjis · Domain: https://karmaai.online
Last updated: 2026-10-07 · Repo: `Al-narjs-ai` · `main` = production

This document is the contract for what "working" means. Everything below is
stated against verified production behaviour, not intent. Where something is
blocked on the owner it says so and names what is needed.

---

## 1. The problem, as measured

The platform is built, tested (756 passing) and live. It cannot take a single
riyal, and it cannot keep a single record. Both facts were reproduced on
production, not inferred.

**1.1 No payment method can complete.**

```
GET /api/payments/capabilities
methods      : mada false · stcpay false · creditcard false · applepay false
               paypal false · invoice true
card_config  : true      card_credentials : "rejected"
paypal       : false     paypal_test_mode: true
bank         : {}
```

- `MOYASAR_API_SECRET` **is set**, and Moyasar answers `401 authentication_error /
  Invalid authorization credentials`. The checkout previously advertised mada,
  Visa, Mastercard and Apple Pay; every such payment failed.
- PayPal runs in **sandbox**. The checkout it authorised completed flows that
  charged no money and started no subscription.
- `content/transfer.json` publishes **no account details**, so the one remaining
  method — bank transfer — cannot be completed by a buyer alone.

**1.2 Production data is destroyed on every deploy.**

`DATABASE_URL` on the live service is `sqlite+aiosqlite:///…`, a file inside the
container's ephemeral filesystem. Three payments were created on production,
each confirmed present, and each was gone (`404 Payment not found`) after the
next deploy. Leads, client projects and payments are equally affected. The site
returned HTTP 200 throughout, so nothing surfaced the loss.

**1.3 The luxury storefront is specified but absent.**

`docs/design-system.md` v0.3 §8 specifies a near-black, glassmorphic public
presentation with a defined token set. Verified: `--lux-*` is **defined in no CSS
file**, used in **no template** (including the 233 KB `landing.html`), and
covered by **zero** assertions in `tests/test_design_system.py`. The document
describes a shipped state that does not exist.

**1.4 Revenue to date: SAR 0.** No payment has ever completed, through any
method, at any point. No leads, sales or testimonials may be claimed.

---

## 2. Goals

1. **Accept money.** One working, unattended payment path, verified end to end
   on production.
2. **Keep every record.** Data survives deploys, restarts and crashes.
3. **Present the product as priced**, so the funnel has something to sell.
4. **Never over-promise.** Every capability the site advertises is one the
   server can actually settle.

## 3. Non-goals

- Automating outbound sales messaging at scale before payment works.
- Changing prices, VAT treatment, payment capture or refund behaviour.
- Changing lead-status, opt-out or outreach logic.
- Public exposure of the owner console or any administrative surface.

---

## 4. Users and jobs to be done

| User | Job | Currently |
| --- | --- | --- |
| Owner (Arabic) | Approve and direct work; receive alerts | Alerts reached the wrong Telegram account — **fixed** |
| Owner (Karmish) | Direct the CEO and the 35 agents from one console | **Shipped**, owner-only |
| Prospective buyer (Arabic) | Understand the offer and pay without a human | Blocked at payment |
| Social media agent (Botpress) | Hand a closed sale to the CEO | **Shipped**, inert until a secret is set |
| Existing lead | Be contacted and activated | CRM fine; storage not durable |

---

## 5. Requirements

### R1 — Payment acceptance *(blocking, owner inputs required)*

| ID | Requirement | Acceptance |
| --- | --- | --- |
| R1.1 | A valid Moyasar credential, or the card buttons removed permanently | `card_credentials != "rejected"` on production, or no card method rendered |
| R1.2 | Published account details for manual transfer | `GET /api/payments/capabilities` returns a non-empty `bank` object |
| R1.3 | The buyer can settle an invoice unaided | Invoice page shows reference, amount, IBAN, copy buttons, WhatsApp |
| R1.4 | PayPal offered only when it collects money | `PAYPAL_MODE=live` → `paypal: true`; otherwise hidden |
| R1.5 | The advertised amount equals the charged amount | One figure across checkout, invoice, confirmation and the `Purchase` event |

**Delivered:** capability probing (only a real 401/403 hides a method; a network
blip never does), the self-serve invoice, `transfer-reported` with owner alert,
the invoice-link recovery page, and the halalas-as-SAR and Pixel-value fixes.

**Blocked on owner:** a working `MOYASAR_API_SECRET`; the real bank details; the
VAT decision (§7, D3).

### R2 — Data durability *(blocking, owner decision required)*

| ID | Requirement | Acceptance |
| --- | --- | --- |
| R2.1 | `DATABASE_URL` points at persistent storage | Boot log shows a non-SQLite dialect |
| R2.2 | Schema builds without a manual migration | `init_db()` `create_all` + Postgres self-heal on boot |
| R2.3 | The failure cannot recur silently | Boot warning asserts on any SQLite file target |

**Delivered:** R2.3 (PR #32). **Blocked:** R2.1 — the Render account holds zero
Postgres, zero Key Value and zero disks, so durable storage must be created and
billed. Owner decision, §7 D1.

### R3 — Luxury dark storefront *(specified, 0% built)*

| ID | Requirement | Acceptance |
| --- | --- | --- |
| R3.1 | `--lux-*` tokens defined once and used across public pages | Every token in §8 resolvable; zero hard-coded hex in public templates |
| R3.2 | All public pages dark; invoices stay light | §8 page list renders dark; `invoice*.html` unchanged |
| R3.3 | Glass cards per §8 rules | `--lux-glass` fill, hairline, `blur(14px)`, 16px radius, alpha ≤ .28 |
| R3.4 | Motion is decorative and removable | All animation disabled under `prefers-reduced-motion: reduce` |
| R3.5 | No SEO or content regression | 756 tests stay green; sitemap and JSON-LD unchanged |
| R3.6 | The contract is enforced, not just described | `tests/test_design_system.py` asserts §8 tokens |

**Owner correction, must be resolved first:** the design snippets circulated for
this work specified **gold `#d4af37`**. The owner's own recorded decision in §8
removed gold from the public site on request ("ثيم مثل موقع هيومين على خلفية
داكنة"), resolving the action hue to **mint `#00D49C` / teal `#00AD92` / aqua
`#00879F`** with lime `#D0F94A`. Gold survives only for printed light surfaces
and the owner console. The document is the contract; §7 D4 confirms this before
any pixel is written.

### R4 — Karmish owner console *(shipped)*

Owner-only console at `/karmish`; `POST /api/v1/karmish/talk` is owner-gated and
rate-limited; responses state what actually ran, including "nothing was
executed"; excluded from sitemap and `robots.txt`; `X-Robots-Tag: noindex`.
58 tests, including assertions that the CEO was *called* rather than merely
reported.

### R5 — Botpress closed-sale intake *(shipped, inert)*

HMAC-SHA256 over the raw body, rate limiting, `extra="forbid"` validation,
bounded fields, control-character stripping from every single-line field,
idempotent on `eventId`, upsert rather than clone, audit row storing a payload
hash and sanitised summary only. `lead_status` and `priority` deliberately
untouched. Inert (503) until `BOTPRESS_WEBHOOK_SECRET` is set.

---

## 6. Constraints

Non-negotiable, from `CLAUDE.md`:

1. Never write, print, log or commit secrets. `.env` is gitignored.
2. Never push to `main`; work on a branch, open a PR, merge after review.
3. `python -m pytest` must pass before requesting a merge.
4. Never invent business data. Report real numbers only.
5. No change to pricing, payment capture/refund, or lead-status logic without
   explicit owner approval.
6. Ask before touching `alembic/versions/*`, `render.yaml`, `Procfile`,
   `nginx.conf`, or env-var names in `src/config/settings.py`.

Product constraints: Arabic-first RTL; Cairo only; prices, plan names and agent
counts rendered from `src/services/catalog.py`, never hard-coded; no dead CTAs;
Telegram primary, WhatsApp second, both untouched by this work.

---

## 7. Open decisions — owner's call

| ID | Decision | Options and cost |
| --- | --- | --- |
| D1 | Persistent storage | **A.** Disk 1 GB — $0.25/mo, keeps SQLite, zero migration risk, requires a paid instance. **B.** Render Postgres basic — $6/mo, matches `render.yaml`, adds dialect risk. Free Postgres expires in 30 days and is not a fix |
| D2 | Card gateway | Supply a valid `MOYASAR_API_SECRET`, or remove the card methods entirely |
| D3 | VAT treatment | Invoice bills base + 15%; Moyasar and transfer paths record pre-VAT base. Currently a 15% discrepancy on card sales. Owner decides which figure is authoritative |
| D4 | Public action hue | Confirm mint/green per §8, or amend the design system to gold |
| D5 | Manual settlement details | Publish the real account into `content/transfer.json` |
| D6 | Botpress activation | Set `BOTPRESS_WEBHOOK_SECRET` in Render |
| D7 | Legacy CRM records | `c4_be` and the owner's own Telegram chat exist as leads; decide whether to purge |

---

## 8. Success metrics

Reported as real numbers only, never modelled:

| Metric | Now | Target |
| --- | --- | --- |
| Completed payments, lifetime | 0 | ≥ 1 |
| Revenue, lifetime | SAR 0 | SAR 10,000 |
| Payment methods that can settle | 0 | ≥ 1 unattended |
| Records surviving a deploy | 0 | 100% |
| Owner alerts arriving in the owner's Telegram | verified manually | continuous |
| Tests green | 756 | ≥ 756 |

---

## 9. Delivery plan

**Phase 1 — stop the bleeding** *(owner inputs; code is ready)*
D1 storage · D2 gateway · D5 bank details · D3 VAT · D6 Botpress secret.
Every one is a configuration or decision action. No further engineering is
required to accept a payment once D1 and either D2 or D5 are resolved.

**Phase 2 — verify the money path.** One end-to-end production transaction per
method, evidenced by a real payment record and a real owner alert. No mocked
verification.

**Phase 3 — storefront.** R3.1–R3.6 behind `prefers-reduced-motion`, catalog
sourced, SEO unchanged. Largest remaining engineering item.

**Phase 4 — growth.** Only after Phase 2: outbound follow-up to captured leads.

---

## 10. Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Gateway credential still rejected after replacement | No card revenue | Capability probe hides the methods honestly; bank transfer remains the manual path |
| Storage chosen is SQLite-on-disk | Single writer, no PITR | Acceptable for one instance; migrate deliberately when revenue warrants |
| Storefront redesign regresses SEO or CLS | Traffic loss | Sitemap, JSON-LD and the 756-test contract gate every visual change |
| Sales recorded from test data | False reporting | No test payment is ever counted as revenue; verification records are labelled and reported |
