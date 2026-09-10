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

_running_scheduler: Optional["AgentScheduler"] = None


async def run_scheduled_task(schedule_id: UUID):
    if _running_scheduler is None:
        logger.warning("Scheduler not available; cannot execute scheduled task")
        return
    await _running_scheduler._execute_scheduled_task(schedule_id)


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
        global _running_scheduler
        _running_scheduler = self
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
        try:
            async with self.session_factory() as session:
                from src.models import Schedule

                from sqlalchemy import select
                result = await session.execute(select(Schedule).where(Schedule.is_active == True))
                for schedule in result.scalars():
                    try:
                        self._add_schedule_job(schedule)
                    except Exception as e:
                        logger.warning(f"Skipping malformed schedule {getattr(schedule, 'id', '?')}: {e}")
        except Exception as e:
            logger.warning(f"Failed to load schedules from DB: {e}")

    def _add_schedule_job(self, schedule):
        try:
            trigger = self._build_trigger(schedule)
        except Exception as e:
            logger.warning(f"Could not build trigger for schedule {schedule.id}: {e}")
            return
        if trigger is None:
            logger.warning(f"Schedule {schedule.id} has no valid trigger")
            return

        job_id = str(schedule.id)
        self.scheduler.add_job(
            run_scheduled_task,
            trigger=trigger,
            id=job_id,
            args=[schedule.id],
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    def _build_trigger(self, schedule):
        if schedule.cron_expression:
            try:
                return CronTrigger.from_crontab(schedule.cron_expression, timezone=schedule.timezone)
            except Exception:
                return CronTrigger.from_crontab(schedule.cron_expression, timezone="UTC")
        elif schedule.interval_seconds:
            try:
                return IntervalTrigger(seconds=schedule.interval_seconds, timezone=schedule.timezone)
            except Exception:
                return IntervalTrigger(seconds=schedule.interval_seconds, timezone="UTC")
        elif schedule.run_once_at:
            try:
                return DateTrigger(run_date=schedule.run_once_at, timezone=schedule.timezone)
            except Exception:
                return DateTrigger(run_date=schedule.run_once_at, timezone="UTC")
        return None

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