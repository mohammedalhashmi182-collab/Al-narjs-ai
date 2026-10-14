"""DPA retention: delete customer content 30 days after a subscription ended.

The DPA (``/dpa``, ``ops_routes.RETENTION``) promises "subscription term + 30
days after cancellation, then deleted". :func:`purge_ended_projects` enforces it.

Scope (per ended project, matched strictly by ``project_id`` — rows with a NULL
``project_id``, i.e. Al-Narjs's own data, are never touched):

- deleted: tenant inbound messages, reply drafts, knowledge docs, uploaded data
  files and tenant contacts.
- kept: the project row, payments/invoices (ZATCA), usage counters, audit log.

A project qualifies when its status is ended (``expired``/``cancelled``/``ended``)
and ``current_period_end`` is more than :data:`RETENTION_AFTER_END` ago. A project
without ``current_period_end`` is skipped (we cannot prove when it ended).

``dry_run`` is the default everywhere: it reports counts and writes nothing.
The scheduled job only deletes when the env var ``DPA_PURGE_LIVE=true`` is set
(owner decision). Every live purge writes one ``AuditLog`` row per project.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

RETENTION_AFTER_END = timedelta(days=30)
ENDED_STATUSES = ("expired", "cancelled", "canceled", "ended")
SCHEDULE_NAME = "dpa.retention_purge"
SCHEDULE_CRON = "40 3 * * *"  # daily 03:40 Asia/Riyadh
LIVE_ENV = "DPA_PURGE_LIVE"


def _aware(dt):
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _scoped_models():
    from src.models.agent_tools import KnowledgeDoc, ProjectDataFile
    from src.models.automation import ReplyDraft
    from src.models.company import InboundMessage
    from src.models.tenant import TenantContact

    return {
        "inbound_messages": InboundMessage,
        "reply_drafts": ReplyDraft,
        "knowledge_docs": KnowledgeDoc,
        "data_files": ProjectDataFile,
        "tenant_contacts": TenantContact,
    }


def live_enabled() -> bool:
    return os.environ.get(LIVE_ENV, "").strip().lower() in ("1", "true", "yes")


async def purge_ended_projects(session: AsyncSession, *, now: Optional[datetime] = None,
                               dry_run: bool = True) -> dict:
    from src.models import AuditLog, ClientProject

    now = _aware(now) or datetime.now(timezone.utc)
    cutoff = now - RETENTION_AFTER_END
    projects = (await session.execute(select(ClientProject).where(
        ClientProject.status.in_(ENDED_STATUSES),
        ClientProject.current_period_end.is_not(None),
        ClientProject.current_period_end <= cutoff,
    ))).scalars().all()

    report = []
    for project in projects:
        counts = {}
        for name, model in _scoped_models().items():
            cond = model.project_id == project.id
            counts[name] = int((await session.execute(select(func.count()).select_from(model).where(cond))).scalar() or 0)
            if not dry_run and counts[name]:
                await session.execute(delete(model).where(cond))
        if not dry_run and any(counts.values()):
            session.add(AuditLog(id=uuid4(), action="dpa_retention_purge", resource_type="client_project",
                                 resource_id=project.id,
                                 changes={"deleted": counts, "period_end": _aware(project.current_period_end).isoformat(),
                                          "ran_at": now.isoformat()}))
        logger.info("dpa retention %s project=%s counts=%s", "dry-run" if dry_run else "PURGE", project.id, counts)
        report.append({"project_id": str(project.id), "status": project.status, "counts": counts})
    if not dry_run:
        await session.commit()
    return {"dry_run": dry_run, "ran_at": now.isoformat(), "cutoff": cutoff.isoformat(),
            "projects": report, "count": len(report)}


async def ensure_schedule(scheduler) -> None:
    """Register the daily retention pass (once). NOTE: must be added to the
    startup registration steps in ``src/main.py`` to run."""
    from src.automation.scheduler import ScheduleConfig
    from src.models import Schedule

    try:
        async with scheduler.session_factory() as session:
            exists = (await session.execute(select(Schedule).where(Schedule.name == SCHEDULE_NAME))).scalar_one_or_none()
        if exists is None:
            await scheduler.add_schedule(ScheduleConfig(
                name=SCHEDULE_NAME, target_type="dpa_retention", target_id=uuid4(),
                cron_expression=SCHEDULE_CRON, timezone="Asia/Riyadh"))
    except Exception as e:  # pragma: no cover - defensive on startup
        logger.warning("Could not register DPA retention schedule: %s", e)
