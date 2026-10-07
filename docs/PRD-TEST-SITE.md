# PRD — Al-Narjis test environment (`test site`)

Status: **proposed — awaiting owner approval** · Companion to `docs/PRD.md`
Last updated: 2026-10-07

## Why

There is no test environment. The entire platform — the only environment that
exists — is production.

```
Render services : 1  -> Al-narjs-ai-1 (web, branch main, autoDeploy yes)
ENVIRONMENT      : production
domains          : karmaai.online, www.karmaai.online
postgres/key-value/disks : 0 / 0 / 0
```

Everything is therefore verified by touching the live customer-facing system.
That is not a preference, it is what has happened repeatedly, and each instance
cost money, data or trust.

## What a test site would have caught

| Defect | How it was actually found | Cost |
| --- | --- | --- |
| `MOYASAR_API_SECRET` rejected (401) | POSTing a **real payment** to production to read the error | Test rows in the production DB, later wiped |
| Production DB is an ephemeral container file | Three payments confirmed present, each gone after a deploy | Silent, undetected for weeks; site returned 200 throughout |
| Owner alerts routed to the wrong Telegram account (`c4_be`) | Live configuration audit | Real alerts misdelivered; the owner's own chat recorded as a lead |
| Changing an env var restarts the service | Triggering a restart to load the correct chat id | Another data wipe |
| PR #30 could not import (`SyntaxError` + BOM) | Local test run; CI also failed the PR | Caught before merge, but only by luck of ordering |

Note: CI **did** fail PR #30, so `main` was protected. What CI cannot do is
exercise the gateway, the storage durability, the Telegram routing, or the
real browser journey. Those need an environment.

## Requirements

### T1 — A second environment

| ID | Requirement | Acceptance |
| --- | --- | --- |
| T1.1 | A dedicated Render web service deploying from a `test` branch, autoDeploy on | Test URL serves the app; production untouched by test merges |
| T1.2 | `ENVIRONMENT=test` | Reported by the boot log and by `/api/v1/botpress/health` |
| T1.3 | Merges to `main` happen only after a green test deploy | A release checklist step; production deploys are never the first place a change runs |

### T2 — Data isolation *(the whole point)*

| ID | Requirement | Acceptance |
| --- | --- | --- |
| T2.1 | Test has its own database; production credentials are never present on test | `DATABASE_URL` on test differs from production; audit confirms |
| T2.2 | Test storage is persistent, or its volatility is accepted knowingly | Boot log shows the intended dialect |
| T2.3 | No test write can reach production | No shared DB, no shared Telegram channel, no shared gateway account |
| T2.4 | Test data is clearly labelled and never counted as revenue | Verification records carry a `TEST` marker; reported as zero revenue |

### T3 — Separate credentials per channel

| ID | Requirement | Acceptance |
| --- | --- | --- |
| T3.1 | Separate Telegram bot and separate owner chat id | A test alert arrives in the test chat and nowhere else |
| T3.2 | Payment gateways in **sandbox/test mode** only | `paypal_test_mode: true`; a card charge in test cannot move real money |
| T3.3 | WhatsApp disabled on test | `/webhooks/whatsapp/health` reports not configured |
| T3.4 | Test OAuth/redirect URLs point at the test domain | Redirects never land on `karmaai.online` |

### T4 — Never contaminate production signals

| ID | Requirement | Acceptance |
| --- | --- | --- |
| T4.1 | `DOMAIN` / `WWW_DOMAIN` set to the test host | `seo.site_origin()` on test emits the test origin, so canonical URLs and `sitemap.xml` do not point at production |
| T4.2 | `META_PIXEL_ID` is **not** the production pixel | Test page views never enter production ad attribution or ROAS. `settings.py` defaults this to the production ID, so the override is mandatory |
| T4.3 | `CORS_ORIGINS` limited to the test host | Test cannot be embedded by, or call into, production |
| T4.5 | Test is `noindex` and absent from the production sitemap | Robots header on test; production sitemap unchanged |

### T5 — Verification that actually exercises the system

| ID | Requirement | Acceptance |
| --- | --- | --- |
| T5.1 | A repeatable smoke run: register → subscribe → checkout → invoice → report | Passes on test, run before every production release |
| T5.2 | The payment path is proven end to end in test | A real sandbox transaction produces a payment record and an owner alert |
| T5.3 | Durability is proven, not assumed | A record written on test survives a test restart |

### T6 — Isolation at the cost level

| ID | Requirement | Acceptance |
| --- | --- | --- |
| T6.1 | Prefer zero-cost options; pay only where durability demands it | Monthly cost stated explicitly in this document and reviewed by the owner |
| T6.2 | Preview instances for pull requests where the plan allows | A PR can be opened on a URL without touching either long-lived environment |

## Non-goals

- Test hosting real customer traffic.
- Feature flags or A/B tooling.
- Load or performance testing.

## Build plan

**Phase 0 — owner actions (cannot be automated)**

1. Confirm the test domain name and point DNS at Render.
2. Approve the cost in §Cost.

**Phase 1 — service and isolation**

1. Create the `test` branch and a Render web service on it, autoDeploy on.
2. Set `ENVIRONMENT=test`, `DOMAIN`/`WWW_DOMAIN` to the test host,
   `CORS_ORIGINS` to the test host, `META_PIXEL_ID` to a separate or empty value.
3. Create test storage; set `DATABASE_URL`.
4. Provision a separate Telegram bot + owner chat id; disable WhatsApp.
5. Configure `BOTPRESS_WEBHOOK_SECRET` for test separately from production.

**Phase 2 — prove it**

1. Run T5.1 on test and capture the output.
2. Run a sandbox card transaction; confirm the payment record and the owner alert.
3. Restart test; confirm the record survived (T5.3).

**Phase 3 — make it the release gate**

1. Production merges require a green test deploy and a passed smoke run.
2. Record the last verified production release in `docs/PRD.md`.

## Cost

Prices from `render.com/pricing`, retrieved 2026-10-07.

| Component | Free | Paid |
| --- | --- | --- |
| Web service | $0 (512 MB, sleeps when idle) | $7/mo (`0.5c-512mb`) |
| Persistent disk 1 GB | — | $0.25/mo |
| Render Postgres | $0, **expires after 30 days** | $6/mo (basic, 1 GB) |
| Preview instances | Included on Hobby, single-service | Unlimited on Pro ($25/mo) |

**Recommended:** test service on the free plan with **Postgres free**, accepting
that the test database is recreated roughly monthly. A test database losing its
contents is an annoyance; a production database doing the same is the incident
this document exists to prevent. Move the test database to the $6 plan only if
monthly churn becomes a real time cost. Total recommended incremental cost:
**$0/month.**

Caveat: persistent disks require a paid instance, so if the test environment
needs durable disk storage the service moves to $7/mo as well.

## Open decisions

| ID | Decision | Owner |
| --- | --- | --- |
| D1 | Test domain name and DNS | Required before Phase 1 |
| D2 | Test service plan: free (sleeps) vs paid (always on, disk capable) | Required before Phase 1 |
| D3 | Test database: free-expiring vs paid-durable | Recommended: free |
| D4 | Separate Telegram bot, or test bot posting to a dedicated test chat | Required before Phase 1 |
