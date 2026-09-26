# Al-Narjis AI — working agreement for coding agents

This repository is a **live production system**, not a sandbox.
Production URL: **https://karmaai.online** · Database: PostgreSQL on Render · Channel: Telegram bot (the WhatsApp integration has been removed).

Any commit that lands on `main` **deploys to production within a minute** (Render auto-deploy).

## Hard rules (never break)

1. **Never write, print, log, or commit secrets.** `.env` is gitignored. Secrets live only in `.env` (local, gitignored) and in Render env vars. Never paste keys into code, comments, commit messages, or chat output.
2. **Never push directly to `main`.** Work on a feature branch and open a pull request. `main` = production.
3. **Run the tests before requesting a merge:** `python -m pytest` from the repo root (bare `pytest` fails with `No module named 'src'`). Baseline is **401 passing** (`python -m pytest`).
4. **Never invent business data.** No fake leads, sales, revenue, testimonials, or metrics. Report real numbers only.
5. **Do not change pricing, payment capture/refund, or lead-status logic** without explicit owner approval.
6. Ask before touching: `alembic/versions/*` (schema), `render.yaml`, `Procfile`, `nginx.conf`, anything in `src/config/settings.py` env-var names.

## Stack and layout

- Python 3.12 · FastAPI · SQLAlchemy 2.x async (`asyncpg`) · Alembic · Jinja2 templates
- `src/main.py` — app assembly, routers, public pages, JSON APIs
- `src/interfaces/` — routers: `telegram_routes.py`, `company_routes.py`, `sales_routes.py`, `web_ui.py`, `cli.py`
- `src/services/` — business logic and external clients (`telegram_sender.py`, `telegram_webhook.py`, …)
- `src/core/` — `model_provider.py` (multi-provider + fallback), `agent_registry.py`, workflow/queue engines
- `src/web/templates/` — all pages (`landing.html`, `privacy.html`, `data_deletion.html`, `payment_status.html`, `portal.html`, …)
- `agents/base/` — pre-built agent YAML definitions
- `tests/` — pytest suite
- `scripts/` — `seed_agents.py`, `setup_telegram_webhook.py`, `import_leads.py`, `verify_waba.py`

## Models

Fallback chain: **Gemini (default) → Moonshot/Kimi** when their keys are set. Optional: OpenAI, Groq, Anthropic, local Ollama. Each provider is registered in `ModelProvider._init_clients()` only if its API key exists.

For local coding agents only, `opencode.json` exposes the optional **Genspark LLM proxy** (`genspark-llm-proxy/*`). It reads `GENSPARK_API_KEY` from the environment — never write the key into any file. Genspark tool reference docs live in `.gsk/skills/`.

## Telegram specifics that already caused an outage

- Webhook endpoints (the router uses `prefix="/webhooks"`): `POST /webhooks/telegram`, `GET /webhooks/telegram/health`. The unprefixed `/telegram` and `/telegram/health` paths are **404** — do not use them in probes or docs.
- Telegram API results are stored in `OutboundMessage.provider_message_id` (varchar 255). **Store only the integer `message_id`** — storing the whole response dict overflows the column and rolls back the entire send, even though the message was delivered.
- Side effects (welcome message, owner alert) run inside a `try` that swallows exceptions; a failure there silently rolls back send rows. Keep that block minimal and exception-free.
- Agent YAML files must use a valid `AgentCategory` (`support`, `marketing`, `content`, `analysis`, `automation`, `general`). An invalid value makes the agent fail to register silently in the logs.

## Visual identity: ODSF v0.2 — gold action, green structure

`docs/design-system.md` is the contract. Summary:

- The public site is a **premium ivory** design: gold `#F4C430` is the action colour, green `#4F7942` is structure and Telegram, page `#FAFAF9`, surface `#FFFFFF`, text `#292524`, secondary `#57534E`. Tokens live in `src/web/static/css/narjis.css`.
- The owner console is the dark counterpart (`narjis-dark-admin.css`): dark warm surfaces, green accent, gold reserved for the single primary action.
- Fonts are **Cairo** only. `Tajawal`, `Almarai`, `Manrope` and the previous IBM Plex/Inter pairing are retired.
- Layout is an 8pt grid. Cards use a soft radius with one quiet shadow step; gold is never a large background field.
- Conversation surfaces use `--r-bubble: 20px` with one `8px` corner, on purpose. Do not flatten them.
- The paper plane and the brand disc come from `src/web/templates/partials/_telegram_mark.html` (`tg_plane`, `tg_plane_cls`, `tg_badge`). The disc takes its colour from `var(--green)`, never a hard-coded hex, and never an icon-font glyph.
- Department role icons live in `src/web/templates/partials/_role_icon.html` with their animation in `src/web/static/css/narjis-role-icons.css`. Every path carries `pathLength="1"` so one draw-on animation works for any geometry. The Jinja `ROLE_ICONS` map and the client's `ROLE_ICONS`/`DEPT_EN` maps in `landing.html` must list the same departments as `src/services/catalog.py`.
- All motion honours `prefers-reduced-motion: reduce`.
- `tests/test_design_system.py` enforces all of the above. If it fails, fix the CSS, not the test.
## Front-end rules

- Arabic-first, RTL. All public copy is Arabic; keep it professional and consistent.
- **Telegram is the only channel** (`https://t.me/AlNarjs7BOT`, support: `?start=support`). Do not reintroduce `wa.me` links or the WhatsApp router; the integration was removed. Historical lead records and verified third-party contact sheets are data, not UI, and keep whatever they say.
- New pages must include: Telegram quick-connect panel, working mobile CTA, and matching `privacy.html` / `data_deletion.html` policy text.
- **No dead CTAs.** No `href="#"` on public pages, no invented numbers. Agent counts, prices, and plan names are rendered from `src/services/catalog.py` (never hard-coded), and the landing page reads the live registry count.
- New public pages reuse the SEO head macro: `{% import "partials/_seo.html" as seo with context %}` then `seo.head(title_ar, title_en, desc_ar, desc_en, request.url.path, og_type, extra_head)`. Note `with context` is required, and the path must be passed explicitly.
- SEO routes are generated in code: `src/services/seo.py` owns the sitemap, robots.txt, and the public/private path policy. `sitemap.xml` must only ever contain `https://karmaai.online/...` (apex is canonical; `www` redirects) and only paths that return 200. `tests/test_seo_surface.py` enforces both.
- Public per-agent pages live at `/ai-agent/<slug>` (built from `catalog.EMPLOYEES`). `/agents` is the owner-only console and must stay out of the sitemap.

## Deploy and operations

- Render service: web service on `main` with auto-deploy. If a deploy ends `update_failed`, the site goes fully down — re-trigger with `POST https://api.render.com/v1/services/{id}/deploys`.
- Health probe: `GET /webhooks/telegram/health`.
- After any change: verify with `curl -sS -o /dev/null -w "%{http_code}" https://karmaai.online/home` and the health endpoint.

## Communication

The operator replies in Arabic. Report changes in concise Arabic: what changed, what was verified, and what still needs his decision. Never claim something works without a live check.
