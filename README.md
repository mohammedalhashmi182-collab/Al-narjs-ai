# Al-Narjis AI / النرجس

[![production](https://img.shields.io/badge/production-alnarjisai.com-black)](https://alnarjisai.com)
[![version](https://img.shields.io/badge/version-1.0.0-FF5A36)](docs/release-v1.0.0.md)
[![python](https://img.shields.io/badge/python-3.12-black)](pyproject.toml)
[![tests](https://github.com/mohammedalhashmi182-collab/Al-narjs-ai/actions/workflows/tests.yml/badge.svg)](https://github.com/mohammedalhashmi182-collab/Al-narjs-ai/actions/workflows/tests.yml)

منصة وكلاء ذكاء اصطناعي عربية أولاً، من الرياض. رئيس تنفيذي ذكي و**39 وكيلاً**، بوابة عميل، ودفع بالبطاقة عبر Moyasar. الموقع يعمل على [alnarjisai.com](https://alnarjisai.com).

Arabic-first AI-agent platform from Riyadh. An AI CEO and **39 agents**, a customer portal, and card checkout through Moyasar. The live site is [alnarjisai.com](https://alnarjisai.com).

**Stack:** FastAPI, SQLAlchemy (asyncpg), Alembic, PostgreSQL, Jinja2, on Render.

## Links

| | Arabic | English |
| --- | --- | --- |
| Site | [alnarjisai.com/ar/home](https://alnarjisai.com/ar/home) | [alnarjisai.com/en/home](https://alnarjisai.com/en/home) |
| Status | [/ar/status](https://alnarjisai.com/ar/status) | [/en/status](https://alnarjisai.com/en/status) |
| API reference | [/ar/docs](https://alnarjisai.com/ar/docs) | [/en/docs](https://alnarjisai.com/en/docs) |
| What's new | [/ar/changelog](https://alnarjisai.com/ar/changelog) | [/en/changelog](https://alnarjisai.com/en/changelog) |
| Service level | [/ar/sla](https://alnarjisai.com/ar/sla) | [/en/sla](https://alnarjisai.com/en/sla) |
| Partnerships | [/ar/partnerships](https://alnarjisai.com/ar/partnerships) | [/en/partnerships](https://alnarjisai.com/en/partnerships) |

Machine-readable status: [https://alnarjisai.com/api/status](https://alnarjisai.com/api/status). OpenAPI: [https://alnarjisai.com/openapi.json](https://alnarjisai.com/openapi.json).

## Features

- **39 agents** plus the AI CEO who staffs a plan from the live catalog. Count and prices come from `src/services/catalog.py`.
- **Plans:** البداية / Starter 790 SAR, النمو / Growth 1,490 SAR, الشركات / Enterprise 2,990 SAR per month. VAT is not added while the operator is not VAT-registered.
- **Customer portal** at `/portal`. Signup links (`/signup`, `/ar/signup`, `/en/signup`) redirect there.
- **Moyasar** guest card checkout (mada, Visa, Mastercard). PayPal exists in the code and is shown only when live mode is turned on.
- **Bilingual public site** under `/ar` and `/en`, with sitemap, hreflang, and `llms.txt`.
- **Voice advisor** at `/voice`. The provider key stays on the server.
- **Workflows, schedules, and a queue** for the owner console.
- **Salla, Zid, and WhatsApp Business** are in development. They are not offered as available connections.

## Quick start

Python 3.12, PostgreSQL, and a copy of the environment file.

```bash
git clone https://github.com/mohammedalhashmi182-collab/Al-narjs-ai.git
cd Al-narjs-ai
cp .env.example .env
pip install -e ".[dev]"
alembic upgrade head
python scripts/seed_agents.py
python -m src.main
```

The app listens on `0.0.0.0:$PORT` (local default is port 8000). Open http://localhost:8000/ar/home.

Docker:

```bash
docker compose up -d
docker compose logs -f app
```

Tests, from the repository root:

```bash
python -m pytest
```

## Project layout

```
src/main.py            app, public pages, customer API
src/services/catalog.py  plans, prices, the 39 agents
src/web/templates/     Arabic and English pages
agents/base/           agent definitions (YAML)
tests/                 pytest
docs/                  status monitoring, release notes, topics
```

## Payments

Guest checkout is a Moyasar hosted invoice. There is no guest bank transfer.

Set these on the host. Do not commit the values.

- `MOYASAR_API_SECRET` — live secret (`sk_live_…`). A test secret does not open checkout.
- `MOYASAR_PUBLISHABLE_KEY` — live publishable key (`pk_live_…`).
- `MOYASAR_WEBHOOK_SECRET` — required for dashboard payment events. Moyasar echoes it as `secret_token` in the JSON body; `POST /webhooks/moyasar` compares it in constant time (401 on mismatch, 503 while unset). `webhook_verification` is always accepted. Point the dashboard webhook at `https://alnarjisai.com/webhooks/moyasar`. Hosted-invoice callbacks go to `POST /webhooks/moyasar/invoice`, which carries no token: the body is only a hint and the order is settled from a fresh Moyasar API fetch.
- `CUSTOMER_PAYPAL_ENABLED` and `PAYPAL_MODE=live` — PayPal stays off until both are set.

`TEST_PAYMENT_TOKEN` gates a hidden probe. Leave it unset on a normal deploy.

## Documentation

- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)
- [Status monitoring and status.alnarjisai.com](docs/status-monitoring.md)
- [Release 1.0.0 (draft)](docs/release-v1.0.0.md)
- [Suggested GitHub topics](docs/github-topics.md)

## License

No license file is published in this repository. Ask the owner before reusing the code.
