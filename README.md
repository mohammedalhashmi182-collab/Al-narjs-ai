# Al-Narjis AI / النرجس

منصة وكلاء ذكاء اصطناعي عربية أولاً — تعمل على الإنترنت فعلياً على [karmaai.online](https://karmaai.online).
مبنية على هذا المستودع: FastAPI + PostgreSQL على Render، بوت تيليجرام، محرك workflows، مدفوعات، وواجهة عامة.

**Production:** https://karmaai.online · **Tests:** 194 passing · **Stack:** FastAPI, SQLAlchemy (asyncpg), Alembic, Telegram Bot API.

## Features

- **20 Pre-built Agents**: Customer service, content writing, marketing, analysis, automation, and more
- **Multi-Model Support**: Gemini (production default) with automatic fallback to Moonshot/Kimi, plus optional OpenAI, Groq, Anthropic and local Ollama
- **Telegram**: Inbound/outbound messaging, webhooks, owner alerts, welcome flows (`POST /webhooks/telegram`)
- **Workflow Engine**: DAG-based workflow execution with context passing between steps
- **Scheduler**: Cron-based and interval-based scheduling
- **Trigger Engine**: Webhook, file watch, and database polling triggers
- **Queue Worker**: Priority-based task queue with concurrency control
- **Web UI**: Public landing + packages + consult, owner portal, company/sales tooling
- **CLI**: Full command-line interface for automation
- **Prompt Versioning**: Template management with version control
- **PostgreSQL + pgvector**: Persistent storage with vector search ready

## Quick Start

### Prerequisites

- Docker & Docker Compose (or Python 3.12 + PostgreSQL locally)
- NVIDIA GPU (optional, for Ollama acceleration)

### Development

```bash
# Clone and navigate
cd ai-agent-system

# Copy environment file
cp .env.example .env

# Edit .env with your settings
# At minimum, set a secure SECRET_KEY

# Start services
docker-compose up -d

# View logs
docker-compose logs -f app
```

### Manual Setup (without Docker)

```bash
# Install dependencies
pip install -e ".[dev]"

# Start PostgreSQL and Redis locally
# Update .env with local connection strings

# Initialize database
alembic upgrade head

# Seed base agents
python scripts/seed_agents.py

# Start services
python -m src.main
```

## Project Structure

```
Al-narjs-ai/
├── agents/
│   ├── base/           # Pre-built agent definitions (YAML; live count from registry)
│   └── custom/         # User-created agents
├── src/
│   ├── automation/     # Scheduler, triggers, workflows, queue
│   ├── core/           # Model provider, agent registry, prompt engine
│   ├── db/             # Database session & models
│   ├── interfaces/     # API routers, CLI & Web UI
│   ├── models/         # SQLAlchemy models
│   ├── services/       # Business logic
│   └── utils/          # Logging, helpers
├── tests/              # 194 tests (pytest)
├── docker-compose.yml
├── Dockerfile
├── render.yaml
├── pyproject.toml
└── .env.example
```

## Pre-built Agents

| Agent | Category | Model | Purpose |
|-------|----------|-------|---------|
| customer_service | support | deepseek-r1 | 24/7 customer responses |
| store_manager | analysis | llama3.1 | Product/order analysis |
| content_writer | content | qwen2.5 | Daily content production |
| marketing_agent | marketing | deepseek-r1 | Campaign optimization |
| competitor_analyst | analysis | llama3.1 | Competitive intelligence |
| ad_writer | marketing | mixtral | Ad copy generation |
| project_manager | automation | deepseek-r1 | Task organization |
| cv_writer | content | llama3.1 | Professional CVs |
| data_analyst | analysis | deepseek-r1 | Data insights |
| content_manager | content | qwen2.5 | Content calendar |
| email_writer | content | mixtral | Professional emails |
| customer_manager | support | deepseek-r1 | Message analysis |
| business_ideas | analysis | llama3.1 | Project suggestions |
| product_describer | content | qwen2.5 | E-commerce descriptions |
| social_media | marketing | deepseek-r1 | Account optimization |
| market_analyst | analysis | deepseek-r1 | Market opportunities |
| article_writer | content | llama3.1 | Professional articles |
| time_manager | automation | qwen2.5 | Daily scheduling |
| text_improver | content | mixtral | Writing enhancement |
| content_ideas | content | deepseek-r1 | Content ideation |

## Usage

### CLI

```bash
# List agents
ai-agent agent list

# Run an agent
ai-agent agent run customer_service -i '{"customer_message": "Where is my order?"}'

# Run workflow
ai-agent workflow run daily_content -i '{"topic": "AI trends"}'

# Create schedule
ai-agent schedule add "Daily Report" --cron "0 9 * * *" --target workflow:daily_report

# View queue stats
ai-agent queue stats
```

### Guest card checkout (Moyasar)

Guests pay by card on Moyasar's hosted invoice. The checkout offers mada, Visa, and Mastercard (and STC Pay on the same hosted page). Apple Pay is not a checkout button. There is no guest bank transfer and no IBAN QR.

Set these on the host (Render). Do not commit values:

- `MOYASAR_API_SECRET` — secret key, `sk_live_…`. A `sk_test_` key does not open checkout.
- `MOYASAR_PUBLISHABLE_KEY` — publishable key, `pk_live_…`. A `pk_test_` key does not open checkout.
- `MOYASAR_WEBHOOK_SECRET` — required for payment events. Moyasar echoes this shared secret as `secret_token` in the JSON body. There is no signature header. `POST /webhooks/moyasar` compares it in constant time and returns 401 on a mismatch. When the variable is empty, payment events are refused with 503 and a warning is logged. `webhook_verification` is still accepted so the one-time code can be read from the logs. Point the webhook at `https://karmaai.online/webhooks/moyasar`.
- A `webhook_verification` event is accepted immediately. The 6-digit code is logged once as `MOYASAR_WEBHOOK_VERIFICATION_CODE=<code>`.
- `TEST_PAYMENT_TOKEN` — gates the hidden 1 SAR probe at `/payment/moyasar-live-test?token=…`. Unset means that path is 404. The charge does not start a subscription.

`PAYMENT_IBAN`, `PAYMENT_ACCOUNT_NAME`, and `PAYMENT_BANK_NAME` are not used for guest checkout.

PayPal stays behind `CUSTOMER_PAYPAL_ENABLED` and `PAYPAL_MODE=live`. Owner-raised invoices are paid by card from the invoice page.

### Web UI

Production: https://karmaai.online · Local: `http://localhost:8000`

### API

```bash
# Run agent via API (owner token required)
curl -X POST http://localhost:8000/api/agents/customer_service/run \
  -H "Content-Type: application/json" \
  -d '{"input_data": {"customer_message": "Hello"}}'

# Create schedule
curl -X POST http://localhost:8000/api/schedules \
  -H "Content-Type: application/json" \
  -d '{"name": "Daily", "target_type": "agent", "target_id": "...", "cron_expression": "0 9 * * *"}'
```

### Messaging webhooks

```bash
# Health probes
curl https://karmaai.online/telegram/health
curl https://karmaai.online/webhooks/telegram/health

# Register the Telegram webhook (uses the bot token from the environment)
python scripts/setup_telegram_webhook.py
```

### Tests

```bash
python -m pytest          # 194 tests
```

## Configuration

Key environment variables in `.env`:

```bash
# Required
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db

# Production models (fallback chain: Gemini -> Moonshot)
GEMINI_API_KEY=...
MOONSHOT_API_KEY=...

# Optional external models
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk_...
ANTHROPIC_API_KEY=sk-ant-...

# Telegram (bot + owner alerts)
TELEGRAM_TOKEN=...
TELEGRAM_OWNER_CHAT_ID=...
TELEGRAM_WEBHOOK_SECRET=...

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_DEFAULT_MODEL=deepseek-r1
```

### Capability agents (forecast, OCR, style, evaluation)

These four agents (AG-036 .. AG-039) read the variables below. Each one has a default, so a deploy does not fail when the variable is absent. `CRON_SECRET` is the exception that stays closed: until it is set, `POST /webhooks/cron/daily` answers 503 and does not run.

```bash
# Required only to open the daily job. Send it as X-Cron-Secret or Authorization: Bearer.
# Render cron command (do not put the secret in the repo):
#   curl -fsS -X POST -H "X-Cron-Secret: $CRON_SECRET" https://karmaai.online/webhooks/cron/daily
CRON_SECRET=
CAPABILITY_CRON_EVAL_LIMIT=20
CAPABILITY_CRON_REVISE=0

# Style profile injection into agent prompts (on by default)
CAPABILITY_STYLE_ENABLED=1

# Score every agent reply inside the runtime (on). Does not call a paid model.
CAPABILITY_EVAL_RUNTIME=1
# Paid-model revision of a failed score (off). Public eval then uses local placeholder cleanup only.
CAPABILITY_EVAL_USE_MODEL=0
CAPABILITY_EVAL_MAX_ROUNDS=3
CAPABILITY_EVAL_MIN_SCORE=0.72

CAPABILITY_FORECAST_MAX_HORIZON=36
CAPABILITY_FORECAST_VAT=0.15
CAPABILITY_OCR_MAX_BYTES=8000000
# Image OCR calls Gemini only when this is on AND GEMINI_API_KEY is set. PDFs use their text layer either way.
OCR_VISION_ENABLED=0
```

Workspaces: `/capabilities/forecast`, `/capabilities/ocr`, `/capabilities/style`, `/capabilities/eval` (Arabic and English via `/ar` and `/en`).

## Adding Custom Agents

1. Create YAML in `agents/custom/`:

```yaml
name: "My Custom Agent"
description: "Does something useful"
category: "general"
model: "ollama:llama3.1"
parameters:
  temperature: 0.7
prompts:
  default: |
    Your prompt template with {{variables}}
```

2. Restart the app or use CLI: `ai-agent agent create --from-yaml agents/custom/my_agent.yaml`

## Extending with Workflows

Create workflow definitions in the database or via API:

```json
{
  "version": 1,
  "steps": [
    {"id": "research", "agent_slug": "data_analyst", "prompt_template": "default"},
    {"id": "write", "agent_slug": "content_writer", "depends_on": ["research"]},
    {"id": "publish", "agent_slug": "email_writer", "depends_on": ["write"]}
  ],
  "global_config": {"slug": "research_to_publish"}
}
```

## License

MIT