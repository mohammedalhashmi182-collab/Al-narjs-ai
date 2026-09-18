"""Company Observatory — the shared operational knowledge layer (Phase C).

Agents and the CEO brain read company state here instead of asking the owner.
Every value is computed from real tables. When a metric genuinely has no source
table we return the string ``UNKNOWN`` — we never fabricate business data.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select

from src.utils.logger import get_logger

logger = get_logger(__name__)

UNKNOWN = "UNKNOWN"

# Sections the observatory reports. Used by the owner panel and tests.
OBSERVATORY_SECTIONS = ("company", "acquisition", "revenue", "projects", "engineering", "operations")


class CompanyObservatory:
    def __init__(self, db_session_factory):
        self._db_session_factory = db_session_factory

    async def agent_snapshot(self, session) -> dict:
        """Agents known to the runtime registry (DB-backed)."""
        from src.models import Agent

        total = (await session.execute(select(func.count()).select_from(Agent))).scalar_one()
        active = (
            await session.execute(
                select(func.count()).select_from(Agent).where(Agent.is_active.is_(True))
            )
        ).scalar_one()
        by_category = dict(
            (await session.execute(
                select(Agent.category, func.count()).group_by(Agent.category)
            )).all()
        )
        rows = (await session.execute(select(Agent).order_by(Agent.slug))).scalars().all()
        return {
            "name": "Al-Narjis AI",
            "agents_total": total,
            "agents_active": active,
            "agents_available": len(rows),
            "by_category": {k: v for k, v in sorted(by_category.items())},
            "agent_slugs": [a.slug for a in rows],
        }

    async def acquisition_snapshot(self, session) -> dict:
        """Canonical CRM funnel (AcquisitionLead is the single source of truth)."""
        from src.models import ACTIVE_STATUSES, AcquisitionLead

        status_rows = dict(
            (await session.execute(
                select(AcquisitionLead.lead_status, func.count()).group_by(AcquisitionLead.lead_status)
            )).all()
        )
        total = (await session.execute(select(func.count()).select_from(AcquisitionLead))).scalar_one()
        now = datetime.now(UTC)

        due_rows = (
            await session.execute(
                select(AcquisitionLead)
                .where(AcquisitionLead.next_followup_at.is_not(None))
                .where(AcquisitionLead.next_followup_at <= now)
                .where(AcquisitionLead.lead_status.in_(ACTIVE_STATUSES))
            )
        ).scalars().all()

        active_leads = (await session.execute(
            select(AcquisitionLead).where(AcquisitionLead.lead_status.in_(ACTIVE_STATUSES))
        )).scalars().all()

        high_priority_active = sum(1 for lead in active_leads if lead.priority == "HIGH")
        return {
            "total_leads": total,
            "by_status": {k: v for k, v in sorted(status_rows.items())},
            "active_leads": len(active_leads),
            "followups_due": len(due_rows),
            "high_priority_active": high_priority_active,
            "new_or_ready": status_rows.get("NEW", 0) + status_rows.get("READY", 0),
            "replied": status_rows.get("REPLIED", 0),
            "interested_demo_proposal": (
                status_rows.get("INTERESTED", 0)
                + status_rows.get("DEMO", 0)
                + status_rows.get("PROPOSAL", 0)
            ),
            "won": status_rows.get("WON", 0),
            "lost": status_rows.get("LOST", 0),
        }

    async def revenue_snapshot(self, session) -> dict:
        """Real recorded payments only. MRR/CAC/LTV have no source table yet -> UNKNOWN."""
        from src.models import Payment

        paid_rows = (await session.execute(
            select(Payment).where(Payment.status == "paid")
        )).scalars().all()
        paid_total_sar = round(sum((p.amount or 0) for p in paid_rows) / 100.0, 2)
        return {
            "payments_total": len(paid_rows),
            "paid_total_sar": paid_total_sar,
            "mrr_sar": UNKNOWN,
            "cac_sar": UNKNOWN,
            "ltv_sar": UNKNOWN,
            "churn_rate": UNKNOWN,
        }

    async def projects_snapshot(self, session) -> dict:
        from src.models import ClientAgent, ClientProject

        total = (await session.execute(select(func.count()).select_from(ClientProject))).scalar_one()
        active = (
            await session.execute(
                select(func.count()).select_from(ClientProject).where(ClientProject.status == "active")
            )
        ).scalar_one()
        agent_slots = (await session.execute(select(func.count()).select_from(ClientAgent))).scalar_one()
        return {"total": total, "active": active, "agent_slots": agent_slots}

    async def engineering_snapshot(self, session) -> dict:
        from src.models import Schedule, WorkflowExecution

        executions = (await session.execute(select(func.count()).select_from(WorkflowExecution))).scalar_one()
        failed = (
            await session.execute(
                select(func.count()).select_from(WorkflowExecution).where(
                    WorkflowExecution.status == "failed"
                )
            )
        ).scalar_one()
        active_schedules = (
            await session.execute(
                select(func.count()).select_from(Schedule).where(Schedule.is_active.is_(True))
            )
        ).scalar_one()
        return {
            "workflow_executions": executions,
            "failed_executions": failed,
            "active_schedules": active_schedules,
        }

    async def operations_snapshot(self, session) -> dict:
        from src.models import Decision, Experiment, Opportunity, Task

        tasks = dict(
            (await session.execute(
                select(Task.status, func.count()).group_by(Task.status)
            )).all()
        )
        opportunities_open = (
            await session.execute(
                select(func.count()).select_from(Opportunity).where(Opportunity.status == "open")
            )
        ).scalar_one()
        decisions = (await session.execute(select(func.count()).select_from(Decision))).scalar_one()
        experiments = (await session.execute(select(func.count()).select_from(Experiment))).scalar_one()
        return {
            "tasks": {k: v for k, v in sorted(tasks.items())},
            "tasks_total": sum(tasks.values()),
            "opportunities_open": opportunities_open,
            "decisions_total": decisions,
            "experiments_total": experiments,
        }

    async def whatsapp_snapshot(self, session) -> dict:
        """WhatsApp/revenue conversation state (secret-free, observable facts)."""
        from src.models import AcquisitionLead, InboundMessage, OutboundMessage
        from src.services.whatsapp_sender import send_status

        total_sent = (await session.execute(select(func.count()).select_from(OutboundMessage))).scalar_one()
        sent_today = (
            await session.execute(
                select(func.count())
                .select_from(OutboundMessage)
                .where(OutboundMessage.status == "sent")
                .where(OutboundMessage.sent_at.is_not(None))
                .where(OutboundMessage.sent_at >= datetime.combine(datetime.now(UTC).date(), datetime.min.time()))
            )
        ).scalar_one()
        replies_total = (
            await session.execute(select(func.count()).select_from(InboundMessage))
        ).scalar_one()
        buying_signals = (
            await session.execute(
                select(func.count())
                .select_from(AcquisitionLead)
                .where(AcquisitionLead.buying_signal.is_(True))
                .where(AcquisitionLead.lead_status != "WON")
            )
        ).scalar_one()
        opted_out = (
            await session.execute(
                select(func.count())
                .select_from(AcquisitionLead)
                .where(AcquisitionLead.opt_out.is_(True))
            )
        ).scalar_one()
        queued = (
            await session.execute(
                select(func.count())
                .select_from(OutboundMessage)
                .where(OutboundMessage.status.in_(["queued", "held", "awaiting_credential"]))
            )
        ).scalar_one()
        failed = (
            await session.execute(
                select(func.count()).select_from(OutboundMessage).where(OutboundMessage.status == "failed")
            )
        ).scalar_one()
        response_rate = round(replies_total / total_sent, 4) if total_sent else 0.0
        return {
            "status": send_status(),
            "total_sent": total_sent,
            "sent_today": sent_today,
            "queued": queued,
            "failed": failed,
            "replies_total": replies_total,
            "response_rate": response_rate,
            "buying_signals": buying_signals,
            "opted_out": opted_out,
        }

    async def snapshot(self) -> dict:
        """Full observable state of the company at this moment."""
        async with self._db_session_factory() as session:
            return {
                "generated_at": datetime.now(UTC).isoformat(),
                "company": await self.agent_snapshot(session),
                "acquisition": await self.acquisition_snapshot(session),
                "revenue": await self.revenue_snapshot(session),
                "projects": await self.projects_snapshot(session),
                "engineering": await self.engineering_snapshot(session),
                "operations": await self.operations_snapshot(session),
                "whatsapp": await self.whatsapp_snapshot(session),
            }
