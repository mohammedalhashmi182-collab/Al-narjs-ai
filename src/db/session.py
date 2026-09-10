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


async def init_db():
    import src.models  # noqa: F401  register all models on Base.metadata
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Self-heal schema drift on tables created by older model versions.
        # Postgres supports ADD COLUMN IF NOT EXISTS; statements are best-effort.
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
            ]
            for table, column, ddl in placeholders:
                try:
                    await conn.execute(text(
                        f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{column}" {ddl}'
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