from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.config.settings import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
    # Recycle connections well before the database/proxy idle timeout so the
    # first request after a quiet period never pays for a dead-connection retry.
    pool_recycle=600,
    pool_size=10,
    max_overflow=20,
)

# Synchronous engine for tools that require a sync engine (e.g. APScheduler jobstore).
# Derived from the same URL, mapping async drivers to their sync equivalents.
def _build_sync_engine():
    url = settings.database_url
    if url.startswith("sqlite"):
        path = url.split("///", 1)[-1]
        return create_engine(f"sqlite:///{path}")
    if url.startswith("postgres"):
        u = url.replace("+asyncpg", "+psycopg2")
        import psycopg2  # noqa: F401  ensure driver available
        return create_engine(u)
    return None


sync_engine = _build_sync_engine()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def ensure_pgvector() -> bool:
    """Best effort: enable pgvector and add agent_knowledge_chunks.embedding_vec (alembic 0011).

    Own transaction, so a database without the extension never breaks startup;
    RAG then uses in-process cosine over the JSON embedding column.
    """
    if engine.dialect.name != "postgresql":
        return False
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text(
                "ALTER TABLE agent_knowledge_chunks ADD COLUMN IF NOT EXISTS embedding_vec vector"))
        return True
    except Exception:  # noqa: BLE001
        return False


async def init_db():
    import src.models  # noqa: F401  register all models on Base.metadata
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Self-heal schema drift on tables created by older model versions.
        # Statements are best-effort idempotent.
        if engine.dialect.name == "postgresql":
            placeholders = [
                ("schedules", "interval_seconds", "INTEGER"),
                ("schedules", "run_once_at", "TIMESTAMPTZ"),
                ("schedules", "payload", "JSONB"),
                ("schedules", "is_active", "BOOLEAN NOT NULL DEFAULT TRUE"),
                ("schedules", "timezone", "VARCHAR(50) DEFAULT 'UTC'"),
                ("schedules", "next_run_at", "TIMESTAMPTZ"),
                ("schedules", "last_run_at", "TIMESTAMPTZ"),
                ("schedules", "run_count", "INTEGER DEFAULT 0"),
                ("schedules", "max_runs", "INTEGER"),
                ("schedules", "created_by", "UUID"),
                ("schedules", "created_at", "TIMESTAMPTZ DEFAULT now()"),
                ("schedules", "updated_at", "TIMESTAMPTZ DEFAULT now()"),
                # Multi-tenancy + cost tracking (architectural middleware layer)
                ("workflow_executions", "tenant_id", "VARCHAR(64) NOT NULL DEFAULT 'system'"),
                ("workflow_executions", "cost", "NUMERIC(12,4) NOT NULL DEFAULT 0"),
                ("step_executions", "tenant_id", "VARCHAR(64) NOT NULL DEFAULT 'system'"),
                ("step_executions", "cost", "NUMERIC(12,4) NOT NULL DEFAULT 0"),
                # Client subscription lifecycle (payment -> project activation)
                ("payments", "project_id", "UUID"),
                # The production Postgres was built before this column existed on
                # the model. create_all() creates missing *tables* but never adds
                # missing *columns* to a table that already exists, so the column
                # was absent while the model declared it: every payment INSERT
                # failed with "column lead_id does not exist" and the checkout
                # answered 500 to every buyer.
                ("payments", "lead_id", "UUID"),
                ("client_projects", "subscription_note", "TEXT"),
                # Billing periods, add-on agents and renewals (alembic 0002)
                ("payments", "billing_period", "VARCHAR(10) NOT NULL DEFAULT 'monthly'"),
                ("payments", "addon_agents", "INTEGER NOT NULL DEFAULT 0"),
                ("payments", "is_renewal", "BOOLEAN NOT NULL DEFAULT FALSE"),
                ("payments", "refund_consent_at", "TIMESTAMPTZ"),
                ("payments", "refund_consent_version", "VARCHAR(20)"),
                ("payments", "charge_currency", "VARCHAR(3)"),
                ("payments", "charge_amount", "INTEGER"),
                ("payments", "total_halalas", "INTEGER"),
                ("client_projects", "billing_period", "VARCHAR(10) NOT NULL DEFAULT 'monthly'"),
                ("client_projects", "addon_agents", "INTEGER NOT NULL DEFAULT 0"),
                ("client_projects", "current_period_end", "TIMESTAMPTZ"),
                ("client_projects", "last_payment_id", "UUID"),
                ("client_projects", "renewal_payment_id", "UUID"),
                # Usage metering + founding offer (alembic 0007)
                ("payments", "addon_conversation_packs", "INTEGER NOT NULL DEFAULT 0"),
                ("payments", "addon_voice_packs", "INTEGER NOT NULL DEFAULT 0"),
                ("payments", "founding", "BOOLEAN NOT NULL DEFAULT FALSE"),
                ("client_projects", "addon_conversation_packs", "INTEGER NOT NULL DEFAULT 0"),
                ("client_projects", "addon_voice_packs", "INTEGER NOT NULL DEFAULT 0"),
                ("client_projects", "founding", "BOOLEAN NOT NULL DEFAULT FALSE"),
                ("client_projects", "founding_at", "TIMESTAMPTZ"),
                ("client_projects", "founding_locked_until", "TIMESTAMPTZ"),
                ("client_projects", "founding_commitment_until", "TIMESTAMPTZ"),
                ("client_projects", "founding_revoked_at", "TIMESTAMPTZ"),
                ("client_projects", "wa_phone_number_id", "VARCHAR(64)"),
                # Tenant Reply Agent + portal login (alembic 0009)
                ("client_projects", "reply_mode", "VARCHAR(10) NOT NULL DEFAULT 'review'"),
                ("client_projects", "wa_access_token_enc", "TEXT"),
                ("client_projects", "portal_token_version", "INTEGER NOT NULL DEFAULT 0"),
                ("automation_reply_drafts", "project_id", "UUID"),
                ("inbound_messages", "project_id", "UUID"),
            ]
            for table, column, ddl in placeholders:
                try:
                    await conn.execute(text(
                        f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{column}" {ddl}'
                    ))
                except Exception:
                    pass
            # Rows created before payments.total_halalas existed were all billed
            # at the then-hardcoded 15%: freeze that total so a later VAT_RATE
            # change never alters what an existing order owes (idempotent).
            try:
                await conn.execute(text(
                    "UPDATE payments SET total_halalas = amount + CAST(ROUND(amount * 0.15) AS INTEGER) "
                    "WHERE total_halalas IS NULL"
                ))
            except Exception:
                pass
            await conn.commit()
        elif engine.dialect.name == "sqlite":
            # create_all cannot add columns to an existing SQLite table, so the
            # revenue-execution and WhatsApp-integration additions are applied
            # as best-effort ALTERs. New tables (e.g. inbound_messages) are
            # created by create_all above.
            sqlite_placeholders = [
                ("payments", "lead_id", "CHAR(36)"),
                # WhatsApp outbound lifecycle (ack tracking, errors)
                ("outbound_messages", "provider_status", "VARCHAR(30)"),
                ("outbound_messages", "message_type", "VARCHAR(20) DEFAULT 'text'"),
                ("outbound_messages", "acknowledged", "INTEGER DEFAULT 0"),
                ("outbound_messages", "acknowledged_at", "TIMESTAMP"),
                ("outbound_messages", "error_code", "VARCHAR(50)"),
                ("outbound_messages", "retry_count", "INTEGER DEFAULT 0"),
                ("outbound_messages", "updated_at", "TIMESTAMP"),
                # WhatsApp conversation state on the canonical lead record
                ("acquisition_leads", "opt_out", "INTEGER DEFAULT 0"),
                ("acquisition_leads", "buying_signal", "INTEGER DEFAULT 0"),
                ("acquisition_leads", "last_reply_at", "TIMESTAMP"),
                ("acquisition_leads", "intent", "VARCHAR(30)"),
                # Multi-tenancy + cost tracking (architectural middleware layer)
                ("workflow_executions", "tenant_id", "VARCHAR(64) NOT NULL DEFAULT 'system'"),
                ("workflow_executions", "cost", "NUMERIC(12,4) NOT NULL DEFAULT 0"),
                ("step_executions", "tenant_id", "VARCHAR(64) NOT NULL DEFAULT 'system'"),
                ("step_executions", "cost", "NUMERIC(12,4) NOT NULL DEFAULT 0"),
                # Client subscription lifecycle (payment -> project activation)
                ("payments", "project_id", "CHAR(36)"),
                ("client_projects", "subscription_note", "TEXT"),
                # Billing periods, add-on agents and renewals (alembic 0002)
                ("payments", "billing_period", "VARCHAR(10) NOT NULL DEFAULT 'monthly'"),
                ("payments", "addon_agents", "INTEGER NOT NULL DEFAULT 0"),
                ("payments", "is_renewal", "INTEGER NOT NULL DEFAULT 0"),
                ("payments", "refund_consent_at", "TIMESTAMP"),
                ("payments", "refund_consent_version", "VARCHAR(20)"),
                ("payments", "charge_currency", "VARCHAR(3)"),
                ("payments", "charge_amount", "INTEGER"),
                ("payments", "total_halalas", "INTEGER"),
                ("client_projects", "billing_period", "VARCHAR(10) NOT NULL DEFAULT 'monthly'"),
                ("client_projects", "addon_agents", "INTEGER NOT NULL DEFAULT 0"),
                ("client_projects", "current_period_end", "TIMESTAMP"),
                ("client_projects", "last_payment_id", "CHAR(36)"),
                ("client_projects", "renewal_payment_id", "CHAR(36)"),
                # Usage metering + founding offer (alembic 0007)
                ("payments", "addon_conversation_packs", "INTEGER NOT NULL DEFAULT 0"),
                ("payments", "addon_voice_packs", "INTEGER NOT NULL DEFAULT 0"),
                ("payments", "founding", "INTEGER NOT NULL DEFAULT 0"),
                ("client_projects", "addon_conversation_packs", "INTEGER NOT NULL DEFAULT 0"),
                ("client_projects", "addon_voice_packs", "INTEGER NOT NULL DEFAULT 0"),
                ("client_projects", "founding", "INTEGER NOT NULL DEFAULT 0"),
                ("client_projects", "founding_at", "TIMESTAMP"),
                ("client_projects", "founding_locked_until", "TIMESTAMP"),
                ("client_projects", "founding_commitment_until", "TIMESTAMP"),
                ("client_projects", "founding_revoked_at", "TIMESTAMP"),
                ("client_projects", "wa_phone_number_id", "VARCHAR(64)"),
                # Tenant Reply Agent + portal login (alembic 0009)
                ("client_projects", "reply_mode", "VARCHAR(10) NOT NULL DEFAULT 'review'"),
                ("client_projects", "wa_access_token_enc", "TEXT"),
                ("client_projects", "portal_token_version", "INTEGER NOT NULL DEFAULT 0"),
                ("automation_reply_drafts", "project_id", "CHAR(36)"),
                ("inbound_messages", "project_id", "CHAR(36)"),
            ]
            for table, column, ddl in sqlite_placeholders:
                try:
                    await conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {ddl}'))
                except Exception:
                    pass
            # Rows created before payments.total_halalas existed were all billed
            # at the then-hardcoded 15%: freeze that total so a later VAT_RATE
            # change never alters what an existing order owes (idempotent).
            try:
                await conn.execute(text(
                    "UPDATE payments SET total_halalas = amount + CAST(ROUND(amount * 0.15) AS INTEGER) "
                    "WHERE total_halalas IS NULL"
                ))
            except Exception:
                pass
            await conn.commit()


async def get_session_factory():
    return async_session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db():
    await engine.dispose()