# Al-Narjis AI / النرجس

منصة وكلاء ذكاء اصطناعي عربية أولاً — تعمل على الإنترنت فعلياً على [karmaai.online](https://karmaai.online).
مبنية على هذا المستودع: FastAPI + PostgreSQL على Render، بوت تيليجرام، محرك workflows، مدفوعات، وواجهة عامة.

**Production:** https://karmaai.online · **Tests:** 194 passing · **Stack:** FastAPI, SQLAlchemy (asyncpg), Alembic, Telegram Bot API, Meta WhatsApp Cloud API.

## Features

- **20 Pre-built Agents**: Customer service, content writing, marketing, analysis, automation, and more
- **Multi-Model Support**: Gemini (production default) with automatic fallback to Moonshot/Kimi, plus optional OpenAI, Groq, Anthropic and local Ollama
- **Telegram + WhatsApp**: Inbound/outbound messaging, webhooks, owner alerts, welcome flows (`POST /telegram`, `POST /whatsapp`)
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
│   ├── base/           # 20 pre-built agents (YAML)
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
curl https://karmaai.online/whatsapp/health

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