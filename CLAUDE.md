# Al-Narjis AI — working agreement for coding agents

This repository is a **live production system**, not a sandbox.
Production URL: **https://karmaai.online** · Database: PostgreSQL on Render · Channel: Telegram bot (WhatsApp Cloud API partially configured).

Any commit that lands on `main` **deploys to production within a minute** (Render auto-deploy).

## Hard rules (never break)

1. **Never write, print, log, or commit secrets.** `.env` is gitignored. Secrets live only in `.env` (local, gitignored) and in Render env vars. Never paste keys into code, comments, commit messages, or chat output.
2. **Never push directly to `main`.** Work on a feature branch and open a pull request. `main` = production.
3. **Run the tests before requesting a merge:** `python -m pytest` from the repo root (bare `pytest` fails with `No module named 'src'`). Baseline is **194 passing**.
4. **Never invent business data.** No fake leads, sales, revenue, testimonials, or metrics. Report real numbers only.
5. **Do not change pricing, payment capture/refund, or lead-status logic** without explicit owner approval.
6. Ask before touching: `alembic/versions/*` (schema), `render.yaml`, `Procfile`, `nginx.conf`, anything in `src/config/settings.py` env-var names.

## Stack and layout

- Python 3.12 · FastAPI · SQLAlchemy 2.x async (`asyncpg`) · Alembic · Jinja2 templates
- `src/main.py` — app assembly, routers, public pages, JSON APIs
- `src/interfaces/` — routers: `telegram_routes.py`, `whatsapp_routes.py`, `company_routes.py`, `sales_routes.py`, `web_ui.py`, `cli.py`
- `src/services/` — business logic and external clients (`telegram_sender.py`, `telegram_webhook.py`, …)
- `src/core/` — `model_provider.py` (multi-provider + fallback), `agent_registry.py`, workflow/queue engines
- `src/web/templates/` — all pages (`landing.html`, `privacy.html`, `data_deletion.html`, `payment_status.html`, `portal.html`, …)
- `agents/base/` — pre-built agent YAML definitions
- `tests/` — pytest suite
- `scripts/` — `seed_agents.py`, `setup_telegram_webhook.py`, `import_leads.py`, `verify_waba.py`

## Models

Fallback chain: **Gemini (default) → Moonshot/Kimi** when their keys are set. Optional: OpenAI, Groq, Anthropic, local Ollama. Each provider is registered in `ModelProvider._init_clients()` only if its API key exists.

## Telegram specifics that already caused an outage

- Webhook endpoints: `POST /telegram`, `GET /telegram/health` (WhatsApp equivalents live under `/whatsapp`).
- Telegram API results are stored in `OutboundMessage.provider_message_id` (varchar 255). **Store only the integer `message_id`** — storing the whole response dict overflows the column and rolls back the entire send, even though the message was delivered.
- Side effects (welcome message, owner alert) run inside a `try` that swallows exceptions; a failure there silently rolls back send rows. Keep that block minimal and exception-free.

## Front-end rules

- Arabic-first, RTL. All public copy is Arabic; keep it professional and consistent.
- **Telegram is the primary channel** (`https://t.me/AlNarjs7BOT`, support: `?start=support`). Public pages must not reintroduce `wa.me` links. Internal sales pages (`sales_lead.html`, `company.html`) may keep WhatsApp because real leads live there.
- New pages must include: Telegram quick-connect panel, working mobile CTA, and matching `privacy.html` / `data_deletion.html` policy text.

## Deploy and operations

- Render service: web service on `main` with auto-deploy. If a deploy ends `update_failed`, the site goes fully down — re-trigger with `POST https://api.render.com/v1/services/{id}/deploys`.
- Health probes: `GET /webhooks/whatsapp/health` and `GET /telegram/health`.
- After any change: verify with `curl -sS -o /dev/null -w "%{http_code}" https://karmaai.online/home` and the health endpoint.

## Communication

The operator replies in Arabic. Report changes in concise Arabic: what changed, what was verified, and what still needs his decision. Never claim something works without a live check.
