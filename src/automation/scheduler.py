from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional
from uuid import UUID

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ScheduleConfig:
    name: str
    target_type: str
    target_id: UUID
    payload: dict = field(default_factory=dict)
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    run_once_at: Optional[datetime] = None
    timezone: str = "UTC"
    is_active: bool = True
    max_runs: Optional[int] = None


class AgentScheduler:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory
        from src.db.session import sync_engine
        jobstores = {
            "default": SQLAlchemyJobStore(engine=sync_engine)
        }
        self.scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="UTC")
        self._job_callbacks: dict[str, Callable] = {}
        self._running = False

    async def start(self):
        if self._running:
            return
        self.scheduler.start()
        self._running = True
        await self._load_schedules_from_db()
        logger.info("Scheduler started")

    async def stop(self):
        if not self._running:
            return
        self.scheduler.shutdown(wait=True)
        self._running = False
        logger.info("Scheduler stopped")

    async def _load_schedules_from_db(self):
        async with self.session_factory() as session:
            from src.models import Schedule

            from sqlalchemy import select
            result = await session.execute(select(Schedule).where(Schedule.is_active == True))
            schedules = result.scalars().all()
            for schedule in schedules:
                self._add_schedule_job(schedule)

    def _add_schedule_job(self, schedule):
        if schedule.cron_expression:
            trigger = CronTrigger.from_crontab(schedule.cron_expression, timezone=schedule.timezone)
        elif schedule.interval_seconds:
            trigger = IntervalTrigger(seconds=schedule.interval_seconds, timezone=schedule.timezone)
        elif schedule.run_once_at:
            trigger = DateTrigger(run_date=schedule.run_once_at, timezone=schedule.timezone)
        else:
            logger.warning(f"Schedule {schedule.id} has no valid trigger")
            return

        job_id = str(schedule.id)
        self.scheduler.add_job(
            self._execute_scheduled_task,
            trigger=trigger,
            id=job_id,
            args=[schedule.id],
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    async def _execute_scheduled_task(self, schedule_id: UUID):
        async with self.session_factory() as session:
            from src.services.schedule_service import execute_schedule
            try:
                await execute_schedule(session, schedule_id)
            except Exception as e:
                logger.exception(f"Scheduled task {schedule_id} failed: {e}")

    async def add_schedule(self, config: ScheduleConfig) -> UUID:
        async with self.session_factory() as session:
            from src.models import Schedule
            schedule = Schedule(
                name=config.name,
                cron_expression=config.cron_expression,
                interval_seconds=config.interval_seconds,
                run_once_at=config.run_once_at,
                target_type=config.target_type,
                target_id=config.target_id,
                payload=config.payload,
                is_active=config.is_active,
                timezone=config.timezone,
                max_runs=config.max_runs,
            )
            session.add(schedule)
            await session.commit()
            await session.refresh(schedule)

            if config.is_active:
                self._add_schedule_job(schedule)

            return schedule.id

    async def remove_schedule(self, schedule_id: UUID) -> bool:
        try:
            self.scheduler.remove_job(str(schedule_id))
        except Exception:
            pass

        async with self.session_factory() as session:
            from src.models import Schedule
            from sqlalchemy import select
            result = await session.execute(select(Schedule).where(Schedule.id == schedule_id))
            schedule = result.scalar_one_or_none()
            if schedule:
                await session.delete(schedule)
                await session.commit()
                return True
        return False

    async def enable_schedule(self, schedule_id: UUID) -> bool:
        async with self.session_factory() as session:
            from src.models import Schedule
            from sqlalchemy import select
            result = await session.execute(select(Schedule).where(Schedule.id == schedule_id))
            schedule = result.scalar_one_or_none()
            if schedule:
                schedule.is_active = True
                await session.commit()
                self._add_schedule_job(schedule)
                return True
        return False

    async def disable_schedule(self, schedule_id: UUID) -> bool:
        try:
            self.scheduler.remove_job(str(schedule_id))
        except Exception:
            pass

        async with self.session_factory() as session:
            from src.models import Schedule
            from sqlalchemy import select
            result = await session.execute(select(Schedule).where(Schedule.id == schedule_id))
            schedule = result.scalar_one_or_none()
            if schedule:
                schedule.is_active = False
                await session.commit()
                return True
        return False

    def get_jobs(self) -> list[dict]:
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time,
                "trigger": str(job.trigger),
            })
        return jobs