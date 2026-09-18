"""Company operating system API (Phase C) — owner-gated read/write surface.

Endpoints expose the Company Observatory, the autonomous work backlog
(opportunities), assigned tasks, the append-only decision log, experiments and
the governance/policy gate. Everything is additive to the existing acquisition
routes in ``src/interfaces/sales_routes.py`` — no duplicates.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.core.owner_auth import require_owner
from src.services.company_observatory import CompanyObservatory
from src.services.governance import PolicyService
from src.services.opportunity_engine import OpportunityEngine

router = APIRouter()


def _services(request: Request) -> tuple[CompanyObservatory, OpportunityEngine, PolicyService]:
    brain = request.app.state.company_brain
    return brain.observatory, brain.opportunities, brain.governance


# ---------------------------------------------------------------------------
# Company observatory
# ---------------------------------------------------------------------------

@router.get("/api/company/state", dependencies=[Depends(require_owner)])
async def company_state(request: Request):
    observatory, _, _ = _services(request)
    return await observatory.snapshot()


@router.get("/api/company/what-happened", dependencies=[Depends(require_owner)])
async def company_what_happened(request: Request, limit: int = 10):
    from sqlalchemy import desc, select

    from src.models import Decision, Task

    async with request.app.state.session_factory() as session:
        decisions = (
            await session.execute(select(Decision).order_by(desc(Decision.created_at)).limit(limit))
        ).scalars().all()
        tasks = (
            await session.execute(select(Task).order_by(desc(Task.created_at)).limit(limit))
        ).scalars().all()
    return {
        "decisions": [d.to_dict() for d in decisions],
        "tasks": [t.to_dict() for t in tasks],
    }


# ---------------------------------------------------------------------------
# CEO brain
# ---------------------------------------------------------------------------

@router.post("/api/ceo/run", dependencies=[Depends(require_owner)])
async def ceo_run(request: Request):
    brain = request.app.state.company_brain
    return await brain.run_once()


# ---------------------------------------------------------------------------
# Opportunities
# ---------------------------------------------------------------------------

class OpportunityCreate(BaseModel):
    title: str = Field(min_length=3)
    owner_agent: str
    area: str = Field(default="general")
    source: str = Field(default="agent")
    description: str | None = None
    evidence: dict = {}
    impact: str | None = None
    confidence: float = 0.0
    priority: int = 50


@router.get("/api/opportunities", dependencies=[Depends(require_owner)])
async def list_opportunities(request: Request, status: str | None = None, area: str | None = None, limit: int = 200):
    _, engine, _ = _services(request)
    return {"opportunities": await engine.list(status=status, area=area, limit=limit)}


@router.post("/api/opportunities", dependencies=[Depends(require_owner)])
async def create_opportunity(request: Request, body: OpportunityCreate):
    _, engine, _ = _services(request)
    return await engine.create(
        title=body.title,
        owner_agent=body.owner_agent,
        area=body.area,
        source=body.source,
        description=body.description,
        evidence=body.evidence,
        impact=body.impact,
        confidence=body.confidence,
        priority=body.priority,
    )


class OpportunityStatus(BaseModel):
    status: str
    learning: str | None = None


@router.post("/api/opportunities/{key}/status", dependencies=[Depends(require_owner)])
async def update_opportunity_status(request: Request, key: str, body: OpportunityStatus):
    _, engine, _ = _services(request)
    updated = await engine.update_status(key, status=body.status, learning=body.learning)
    if updated is None:
        raise HTTPException(404, "Opportunity not found")
    if body.status in ("won", "dismissed"):
        await _log_decision(request, f"opportunity settled: {key} ({body.status})", body.learning)
    return updated


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

class TaskCreate(BaseModel):
    title: str = Field(min_length=3)
    owner_agent: str
    department: str | None = None
    description: str | None = None
    source: str = Field(default="owner")
    priority: int = 50
    evidence: dict = {}


class TaskUpdate(BaseModel):
    status: str | None = None
    result: dict | None = None
    learning: str | None = None


@router.get("/api/tasks", dependencies=[Depends(require_owner)])
async def list_tasks(request: Request, status: str | None = None, limit: int = 200):
    from sqlalchemy import asc, desc, select

    from src.models import Task

    query = select(Task).order_by(desc(Task.priority), asc(Task.created_at)).limit(limit)
    if status:
        query = query.where(Task.status == status)
    async with request.app.state.session_factory() as session:
        rows = (await session.execute(query)).scalars().all()
    return {"tasks": [t.to_dict() for t in rows]}


@router.post("/api/tasks", dependencies=[Depends(require_owner)])
async def create_task(request: Request, body: TaskCreate):
    from src.models import Task
    from src.services.opportunity_engine import _opportunity_key

    key = _opportunity_key(body.owner_agent, body.title)
    async with request.app.state.session_factory() as session:
        existing = (await session.execute(select(Task).where(Task.key == key))).scalar_one_or_none()
        if existing:
            return existing.to_dict()
        task = Task(
            key=key,
            title=body.title,
            description=body.description,
            source=body.source,
            priority=body.priority,
            owner_agent=body.owner_agent,
            department=body.department,
            evidence=body.evidence,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task.to_dict()


@router.patch("/api/tasks/{key}", dependencies=[Depends(require_owner)])
async def update_task(request: Request, key: str, body: TaskUpdate):
    from sqlalchemy import select

    from src.models import Task

    async with request.app.state.session_factory() as session:
        task = (await session.execute(select(Task).where(Task.key == key))).scalar_one_or_none()
        if task is None:
            raise HTTPException(404, "Task not found")
        if body.status is not None:
            task.status = body.status
        if body.result is not None:
            task.result = body.result
        if body.learning is not None:
            task.learning = body.learning
        await session.commit()
        await session.refresh(task)
        return task.to_dict()


# ---------------------------------------------------------------------------
# Decision log
# ---------------------------------------------------------------------------

@router.get("/api/decisions", dependencies=[Depends(require_owner)])
async def list_decisions(request: Request, limit: int = 50, actor: str | None = None):
    from sqlalchemy import desc, select

    from src.models import Decision

    query = select(Decision).order_by(desc(Decision.created_at)).limit(min(limit, 200))
    if actor:
        query = query.where(Decision.actor == actor)
    async with request.app.state.session_factory() as session:
        rows = (await session.execute(query)).scalars().all()
    return {"decisions": [d.to_dict() for d in rows]}


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------

class ExperimentCreate(BaseModel):
    hypothesis: str
    variable: str | None = None
    target_metric: str | None = None
    baseline: dict = {}


@router.get("/api/experiments", dependencies=[Depends(require_owner)])
async def list_experiments(request: Request, limit: int = 100):
    from sqlalchemy import desc, select

    from src.models import Experiment

    async with request.app.state.session_factory() as session:
        rows = (await session.execute(
            select(Experiment).order_by(desc(Experiment.created_at)).limit(limit)
        )).scalars().all()
    return {"experiments": [e.to_dict() for e in rows]}


@router.post("/api/experiments", dependencies=[Depends(require_owner)])
async def create_experiment(request: Request, body: ExperimentCreate):
    import hashlib

    from src.models import Experiment

    key = hashlib.sha1(body.hypothesis.strip().encode("utf-8")).hexdigest()[:24]
    async with request.app.state.session_factory() as session:
        existing = (await session.execute(select(Experiment).where(Experiment.key == key))).scalar_one_or_none()
        if existing:
            return existing.to_dict()
        exp = Experiment(
            key=key,
            hypothesis=body.hypothesis,
            variable=body.variable,
            target_metric=body.target_metric,
            baseline=body.baseline,
        )
        session.add(exp)
        await session.commit()
        await session.refresh(exp)
        return exp.to_dict()


# ---------------------------------------------------------------------------
# Governance / policies
# ---------------------------------------------------------------------------

class PolicyUpsert(BaseModel):
    agent_slug: str
    autonomy_level: int = Field(ge=0, le=3)
    allowed_actions: list[str] | None = None
    denied_actions: list[str] | None = None
    requires_approval: list[str] | None = None
    budget_usd: float = 0.0
    rate_limits: dict = {}


@router.get("/api/governance/policies", dependencies=[Depends(require_owner)])
async def list_policies(request: Request):
    _, _, governance = _services(request)
    return {"policies": await governance.list_policies()}


@router.post("/api/governance/policies", dependencies=[Depends(require_owner)])
async def upsert_policy(request: Request, body: PolicyUpsert):
    _, _, governance = _services(request)
    return await governance.upsert_policy(
        body.agent_slug,
        autonomy_level=body.autonomy_level,
        allowed_actions=body.allowed_actions,
        denied_actions=body.denied_actions,
        requires_approval=body.requires_approval,
        budget_usd=body.budget_usd,
        rate_limits=body.rate_limits,
    )


@router.get("/api/governance/authorize", dependencies=[Depends(require_owner)])
async def governance_authorize(request: Request, agent: str, action: str):
    _, _, governance = _services(request)
    return await governance.authorize(agent, action)


# ---------------------------------------------------------------------------
# Revenue war room (maximum-revenue mode)
# ---------------------------------------------------------------------------

@router.get("/api/company/revenue", dependencies=[Depends(require_owner)])
async def company_revenue(request: Request):
    from src.services.revenue_radar import revenue_metrics

    async with request.app.state.session_factory() as session:
        metrics = await revenue_metrics(session)
    return metrics.to_dict()


@router.get("/api/company/radar", dependencies=[Depends(require_owner)])
async def company_radar(request: Request, top: int = 10, size: int = 0, verified_sar: int | None = None):
    from src.services.revenue_radar import build_wave
    from src.services.whatsapp_sender import conversation_summary

    async with request.app.state.session_factory() as session:
        wave = await build_wave(session, target_sar=None, verified_sar=verified_sar, size=size or None)
        conversation = await conversation_summary(session)
    return {
        "metrics": wave["metrics"],
        "wave_size": wave["wave_size"],
        "total_active": wave["total_active"],
        "tier_counts": wave["tier_counts"],
        "top_10": wave["top_10"],
        "next_20": wave["next_20"],
        "whatsapp": wave["whatsapp"],
        "conversation": conversation,
    }


@router.get("/api/company/queue", dependencies=[Depends(require_owner)])
async def company_outbox(request: Request, limit: int = 50):
    from sqlalchemy import desc, select

    from src.models import OutboundMessage

    async with request.app.state.session_factory() as session:
        rows = (
            await session.execute(
                select(OutboundMessage).order_by(desc(OutboundMessage.created_at)).limit(min(limit, 200))
            )
        ).scalars().all()
    return {
        "sender": _whatsapp_status(),
        "outbox": [r.to_dict() for r in rows],
    }


class QueueSendRequest(BaseModel):
    lead_id: str
    message: str | None = None


@router.post("/api/company/queue/send", dependencies=[Depends(require_owner)])
async def company_send(request: Request, body: QueueSendRequest):
    from uuid import UUID as _UUID

    from sqlalchemy import select as _sel

    from src.models import AcquisitionLead
    from src.services.whatsapp_sender import enqueue, flush_queue

    try:
        lead_uuid = _UUID(body.lead_id)
    except ValueError:
        raise HTTPException(422, "lead_id must be a valid UUID")

    status = _whatsapp_status()
    async with request.app.state.session_factory() as session:
        lead = (
            await session.execute(_sel(AcquisitionLead).where(AcquisitionLead.id == lead_uuid))
        ).scalar_one_or_none()
        if lead is None:
            raise HTTPException(404, "Lead not found")
        if getattr(lead, "opt_out", False) or (lead.lead_status or "") == "DO_NOT_CONTACT":
            raise HTTPException(409, "Lead has opted out — never message opted-out leads")

        from src.services.lead_outreach import generate_message

        message = body.message
        if not message:
            drafted = generate_message(lead, lang="ar")
            message = drafted["message"]

        phone = getattr(lead, "phone_number", None) or lead.phone or lead.phone_raw
        record = await enqueue(session, lead_id=lead.id, message=message, phone=phone)
        await session.commit()

        flushed = await flush_queue(session)
        await session.commit()

        record_full = (
            await session.execute(_sel(type(record)).where(type(record).id == record.id))
        ).scalar_one()

        return {
            "sender": status,
            "record": record_full.to_dict(),
            "flush": flushed,
            "lead_id": str(lead.id),
        }


def _whatsapp_status() -> dict:
    from src.services.whatsapp_sender import send_status

    return send_status()


async def _log_decision(request: Request, decision: str, learning: str | None = None) -> None:
    from src.models import Decision

    async with request.app.state.session_factory() as session:
        session.add(Decision(
            decision=decision,
            actor="owner",
            status="resolved",
            learning=learning,
        ))
        await session.commit()
