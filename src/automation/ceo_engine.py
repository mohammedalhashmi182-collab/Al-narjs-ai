"""CEO / Company Brain (Phase C).

Deterministic, evidence-based strategic engine on top of real observable state.
It reads the Company Observatory, computes the current bottlenecks into
concrete opportunities (deduplicated via the OpportunityEngine), promotes the
highest-confidence one into a Task, and records everything in the append-only
Decision log so each daily loop is auditable.

No LLM call is made and no action is executed externally here: this brain only
decides and assigns. Execution stays inside pre-authorized policies under the
Governance service.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.services.company_observatory import CompanyObservatory
from src.services.governance import PolicyService
from src.services.opportunity_engine import OpportunityEngine
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Scheduled loops registered once at startup (idempotent by name).
COMPANY_LOOPS = [
    ("ceo_engine.daily", "30 9 * * *"),
    ("ceo_engine.intraday", "0 */6 * * *"),
]


async def ensure_company_loops(scheduler) -> None:
    """Register the CEO operating cycles as APScheduler schedules (once).

    Idempotent: existing schedules with the same name are left untouched, so
    repeated app restarts never create duplicate loops.
    """
    from uuid import uuid4

    from sqlalchemy import select

    from src.automation.scheduler import ScheduleConfig
    from src.models import Schedule

    for name, cron in COMPANY_LOOPS:
        try:
            async with scheduler.session_factory() as session:
                exists = (
                    await session.execute(select(Schedule).where(Schedule.name == name))
                ).scalar_one_or_none()
            if exists is not None:
                continue
            await scheduler.add_schedule(ScheduleConfig(
                name=name,
                target_type="ceo_loop",
                target_id=uuid4(),
                payload={},
                cron_expression=cron,
                timezone="Asia/Riyadh",
            ))
            logger.info("Registered company loop: %s (%s)", name, cron)
        except Exception as e:  # pragma: no cover - defensive on startup
            logger.warning("Could not register company loop %s: %s", name, e)


class CompanyBrain:
    def __init__(self, db_session_factory):
        self._db_session_factory = db_session_factory
        self.observatory = CompanyObservatory(db_session_factory)
        self.opportunities = OpportunityEngine(db_session_factory)
        self.governance = PolicyService(db_session_factory)

    # -- priority detection: real signals -> suggested work --------------------

    async def _detect_priorities(self, snap: dict) -> list[dict]:
        acq = snap["acquisition"]
        revenue = snap["revenue"]
        priorities: list[dict] = []

        if acq["followups_due"] > 0:
            priorities.append({
                "area": "acquisition",
                "slot": "customer_manager",
                "title": f"Process {acq['followups_due']} due follow-ups",
                "description": (
                    "Lead follow-ups are due now. Load the CRM's highest-priority active leads "
                    "and prepare the next outreach step for owner review."
                ),
                "impact": "Prevents leads going cold and keeps the funnel moving",
                "confidence": 0.9,
                "priority": 200,
                "evidence": {"followups_due": acq["followups_due"]},
            })

        if acq["new_or_ready"] > 0:
            priorities.append({
                "area": "acquisition",
                "slot": "sales_closer",
                "title": f"Qualify {acq['new_or_ready']} new/ready leads",
                "description": (
                    "Uncontacted leads exist in the canonical CRM. Generate personalized outreach "
                    "drafts and queue them in the approved campaign for owner review."
                ),
                "impact": "Converts captured traffic into conversations",
                "confidence": 0.85,
                "priority": 180,
                "evidence": {"new_or_ready": acq["new_or_ready"]},
            })

        if acq["interested_demo_proposal"] > 0:
            priorities.append({
                "area": "revenue",
                "slot": "sales_closer",
                "title": f"Advance {acq['interested_demo_proposal']} interested/demo/proposal leads",
                "description": (
                    "Hot pipeline exists. Prepare demo talking points and proposal drafts "
                    "towards a WON outcome."
                ),
                "impact": "Direct revenue potential in the active pipeline",
                "confidence": 0.8,
                "priority": 160,
                "evidence": {"interested_demo_proposal": acq["interested_demo_proposal"]},
            })

        if acq["won"] > 0 and snap["projects"]["total"] == 0:
            priorities.append({
                "area": "customer_success",
                "slot": "customer_service",
                "title": f"Onboard {acq['won']} won leads into projects",
                "description": (
                    "Won leads exist but no client project was created yet. Welcome and onboard "
                    "them into an activated team under the existing portal."
                ),
                "impact": "Conversion of won leads into active paying projects",
                "confidence": 0.75,
                "priority": 120,
                "evidence": {"won": acq["won"], "projects": snap["projects"]["total"]},
            })

        if revenue["paid_total_sar"] == 0 and acq["total_leads"] > 0:
            priorities.append({
                "area": "growth",
                "slot": "marketing_agent",
                "title": "No paid revenue yet — sharpen offer and CRO",
                "description": (
                    "Leads are being captured but no payment has been recorded. Investigate the "
                    "offer, landing CTA and package pricing, then propose one A/B experiment."
                ),
                "impact": "Strongest lever: turning captured leads into paying customers",
                "confidence": 0.7,
                "priority": 140,
                "evidence": {
                    "leads": acq["total_leads"],
                    "paid_total_sar": revenue["paid_total_sar"],
                },
            })

        return priorities

    async def _revenue_priorities(self, snap: dict, metrics: dict) -> list[dict]:
        """Revenue Director: gap-driven reprioritization, deterministic focus."""
        acq = snap["acquisition"]
        wa = snap.get("whatsapp") or {}
        gap = metrics.get("gap_sar", 0)
        if gap <= 0:
            return []

        buying_signals = int(wa.get("buying_signals") or 0)
        if buying_signals > 0:
            focus = "reply_conversation"
            title = f"Reply to {buying_signals} hot WhatsApp buying signals now"
            description = (
                "Leads sent buying signals over WhatsApp and are waiting. Craft the reply "
                "per intent (price/demo/proposal/ready-to-buy), push straight to proposal, "
                "invoice and the confirm-received step to close today."
            )
            confidence = 0.85
            priority = 210
        elif acq["interested_demo_proposal"] > 0:
            focus = "proposal_close"
            title = (
                f"Close {acq['interested_demo_proposal']} demo/proposal leads toward payment"
            )
            description = (
                "Hot pipeline already in demo/proposal. Prepare the printable proposal pack, "
                "issue the invoice, and drive the confirm-received step to reach WON today."
            )
            confidence = 0.75
            priority = 205
        elif acq["replied"] > 0:
            focus = "replied_followup"
            title = f"Follow up {acq['replied']} replied leads while they are warm"
            description = (
                "Leads have replied; unanswered replies go cold fast. Prioritize answering and "
                "pushing to a demo with a personalized follow-up message."
            )
            confidence = 0.72
            priority = 200
        elif acq["followups_due"] > 0:
            focus = "followup"
            title = f"Run {acq['followups_due']} due follow-ups on the current wave"
            description = (
                "Scheduled follow-ups are due now. Process the highest-priority active leads "
                "and prepare the next outreach step for owner execution."
            )
            confidence = 0.68
            priority = 195
        elif metrics.get("required_contacts", 0) > 0:
            focus = "quotation_recovery"
            title = (
                f"Recover quotations & historical leads — contact {metrics['required_contacts']} "
                "leads today (interleaved wave)"
            )
            description = (
                "Gap-driven wave. Start with quotation-without-purchase evidence, interleave "
                "recent historical customers, use the wa.me one-tap fallback until WhatsApp "
                "credentials are configured, and push each reply to a demo."
            )
            confidence = 0.62
            priority = 190
        else:
            focus = "serial_contact"
            title = "Contact the next cold wave from the Tier B/C pool"
            description = "No warm evidence left; serialize a small cold wave with lower friction."
            confidence = 0.5
            priority = 180

        return [{
            "area": "revenue",
            "slot": "sales_closer",
            "title": title,
            "description": description,
            "impact": (
                f"Bridges the {gap} SAR gap ({metrics.get('verified_sar', 0)} verified -> "
                f"target {metrics.get('target_sar', 0)})"
            ),
            "confidence": confidence,
            "priority": priority,
            "evidence": {
                "gap_sar": gap,
                "verified_sar": metrics.get("verified_sar", 0),
                "target_sar": metrics.get("target_sar", 0),
                "required_contacts": metrics.get("required_contacts", 0),
                "focus": focus,
                "replied": acq["replied"],
                "followups_due": acq["followups_due"],
                "interested_demo_proposal": acq["interested_demo_proposal"],
                "buying_signals": buying_signals,
                "response_rate": wa.get("response_rate"),
                "sent_today": wa.get("sent_today"),
            },
        }]

    async def _record_decision(self, summary: dict) -> None:
        from src.models import Decision

        async with self._db_session_factory() as session:
            session.add(Decision(
                decision="CEO daily operating loop",
                reason="Autonomous prioritization on observable company state",
                evidence=summary,
                actor="ceo",
                expected="Agents pick up the assigned opportunities under policy",
                status="executed",
            ))
            await session.commit()

    async def run_once(self) -> dict:
        """One operating cycle: observe -> prioritize -> assign -> log."""
        snap = await self.observatory.snapshot()

        metrics = None
        try:
            from src.services.revenue_radar import revenue_metrics

            async with self._db_session_factory() as session:
                metrics = await revenue_metrics(session)
        except Exception as e:  # pragma: no cover - revenue radar must never break the loop
            logger.warning("Revenue metrics unavailable: %s", e)

        priorities = await self._detect_priorities(snap)
        if metrics is not None:
            priorities.extend(await self._revenue_priorities(snap, metrics.to_dict()))
        priorities.sort(key=lambda p: p.get("priority", 0), reverse=True)

        created_opportunities = []
        for p in priorities[:3]:
            opp = await self.opportunities.create(
                title=p["title"],
                owner_agent=p["slot"],
                area=p["area"],
                source="ceo_loop",
                description=p["description"],
                evidence=p["evidence"],
                impact=p["impact"],
                confidence=p["confidence"],
                priority=p["priority"],
            )
            created_opportunities.append(opp)

        promoted = []
        for opp in created_opportunities:
            if opp["confidence"] >= 0.8 and opp["status"] in ("open", "assigned"):
                task = await self.opportunities.promote_to_task(
                    opp["key"],
                    department=opp["area"],
                    due_at=(datetime.now(UTC) + timedelta(days=1)).replace(tzinfo=None),
                )
                if task:
                    promoted.append({"task_key": task["key"], "owner_agent": task["owner_agent"]})

        summary = {
            "ts": datetime.now(UTC).isoformat(),
            "priority_count": len(created_opportunities),
            "opportunities": [o["key"] for o in created_opportunities],
            "promoted_tasks": promoted,
            "revenue": metrics.to_dict() if metrics is not None else None,
        }
        await self._record_decision(summary)

        return {
            "run_id": summary["ts"],
            "priorities": created_opportunities,
            "promoted": promoted,
            "revenue": metrics.to_dict() if metrics is not None else None,
            "snapshot": snap,
        }
