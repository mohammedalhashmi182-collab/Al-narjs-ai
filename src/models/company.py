"""Autonomous-company operating models for Al-Narjis AI (Phase C).

These tables are strictly additive. They model the "company operating system"
layer on top of the existing runtime (agents, workflows, schedules, CRM):

* ``AgentPolicy`` — autonomy/permission contract per agent (Levels 0-3).
* ``Task``       — a concrete unit of autonomous work assigned to an agent.
* ``Opportunity``— an evidence-backed, self-discovered piece of work (deduplicated).
* ``Decision``   — the append-only company decision log (learnings).
* ``Experiment`` — hypothesis-driven, measured optimizations.

Nothing here replaces the canonical acquisition system (AcquisitionLead & friends
in ``src/models/crm.py``); that remains the single source of truth for leads.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base

# Autonomy levels (mirror the master-prompt contract).
AUTONOMY_LEVELS = {
    0: "read",
    1: "internal",
    2: "pre_authorized_external",
    3: "owner_approval",
}

TASK_STATUSES = (
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
    "escalated",
)


class AgentPolicy(Base):
    """Permission contract for one agent: what it may do on its own."""

    __tablename__ = "agent_policies"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    autonomy_level: Mapped[int] = mapped_column(default=1, nullable=False)
    allowed_actions: Mapped[list] = mapped_column(JSON, default=list)
    denied_actions: Mapped[list] = mapped_column(JSON, default=list)
    requires_approval: Mapped[list] = mapped_column(JSON, default=list)
    budget_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rate_limits: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "agent_slug": self.agent_slug,
            "autonomy_level": self.autonomy_level,
            "autonomy_label": AUTONOMY_LEVELS.get(self.autonomy_level, "unknown"),
            "allowed_actions": self.allowed_actions,
            "denied_actions": self.denied_actions,
            "requires_approval": self.requires_approval,
            "budget_usd": self.budget_usd,
            "rate_limits": self.rate_limits,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Task(Base):
    """A concrete unit of work owned by exactly one agent."""

    __tablename__ = "company_tasks"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    parent_key: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(64), default="owner", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="queued", nullable=False, index=True)
    priority: Mapped[int] = mapped_column(default=50, nullable=False, index=True)
    impact: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    owner_agent: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    department: Mapped[str | None] = mapped_column(String(50))
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    learning: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_company_tasks_status_priority", "status", "priority"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "key": self.key,
            "title": self.title,
            "description": self.description,
            "parent_key": self.parent_key,
            "source": self.source,
            "status": self.status,
            "priority": self.priority,
            "impact": self.impact,
            "confidence": self.confidence,
            "owner_agent": self.owner_agent,
            "department": self.department,
            "evidence": self.evidence,
            "result": self.result,
            "learning": self.learning,
            "due_at": self.due_at.isoformat() if self.due_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Opportunity(Base):
    """Evidence-backed work discovered by agents or the CEO brain.

    Deduplicated on ``key`` — repeating the same finding updates an existing
    open opportunity rather than creating duplicates.
    """

    __tablename__ = "company_opportunities"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    area: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(64), default="agent", nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    impact: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    priority: Mapped[int] = mapped_column(default=50, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False, index=True)
    owner_agent: Mapped[str | None] = mapped_column(String(100), index=True)
    linked_task_key: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_company_opp_area_status", "area", "status"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "key": self.key,
            "title": self.title,
            "description": self.description,
            "area": self.area,
            "source": self.source,
            "evidence": self.evidence,
            "impact": self.impact,
            "confidence": self.confidence,
            "priority": self.priority,
            "status": self.status,
            "owner_agent": self.owner_agent,
            "linked_task_key": self.linked_task_key,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Decision(Base):
    """Append-only company decision log — the system's institutional memory."""

    __tablename__ = "company_decisions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    actor: Mapped[str] = mapped_column(String(100), default="ceo", nullable=False, index=True)
    expected: Mapped[str | None] = mapped_column(Text)
    actual: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    learning: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_company_decisions_actor_created", "actor", "created_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "decision": self.decision,
            "reason": self.reason,
            "evidence": self.evidence,
            "actor": self.actor,
            "expected": self.expected,
            "actual": self.actual,
            "status": self.status,
            "learning": self.learning,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Experiment(Base):
    """Hypothesis-driven experiment: baseline, change, measured result."""

    __tablename__ = "company_experiments"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    baseline: Mapped[dict] = mapped_column(JSON, default=dict)
    variable: Mapped[str | None] = mapped_column(String(255))
    target_metric: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="planned", nullable=False)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    decision: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "key": self.key,
            "hypothesis": self.hypothesis,
            "baseline": self.baseline,
            "variable": self.variable,
            "target_metric": self.target_metric,
            "status": self.status,
            "result": self.result,
            "decision": self.decision,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class OutboundMessage(Base):
    """Durable outbound messaging queue (revenue execution).

    Every queued message keeps its full lifecycle: queued -> sent (with provider
    acknowledgement and provider-supplied message id) or failed/awaiting_credential.
    Nothing is ever marked ``sent`` without an actual provider acknowledgement.
    """

    __tablename__ = "outbound_messages"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("acquisition_leads.id", ondelete="SET NULL"), index=True, nullable=True
    )
    channel: Mapped[str] = mapped_column(String(30), default="whatsapp", nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="queued", nullable=False, index=True)
    provider: Mapped[Optional[str]] = mapped_column(String(50))
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(255))
    provider_status: Mapped[Optional[str]] = mapped_column(String(30))
    message_type: Mapped[str] = mapped_column(String(20), default="text", nullable=False)
    acknowledged: Mapped[bool] = mapped_column(default=False, nullable=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error: Mapped[Optional[str]] = mapped_column(Text)
    error_code: Mapped[Optional[str]] = mapped_column(String(50))
    retry_count: Mapped[int] = mapped_column(default=0, nullable=False)
    wa_me_link: Mapped[Optional[str]] = mapped_column(Text)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "lead_id": str(self.lead_id) if self.lead_id else None,
            "channel": self.channel,
            "phone": self.phone,
            "text": self.text,
            "status": self.status,
            "provider": self.provider,
            "provider_message_id": self.provider_message_id,
            "provider_status": self.provider_status,
            "message_type": self.message_type,
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "error": self.error,
            "error_code": self.error_code,
            "retry_count": self.retry_count,
            "wa_me_link": self.wa_me_link,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class InboundMessage(Base):
    """One inbound WhatsApp webhook message, deduplicated by provider message id.

    ``payload_hash`` stores the SHA-256 of the raw webhook message entry so the
    original payload can be referenced for audits without persisting secrets or
    raw payload copies in the database.
    """

    __tablename__ = "inbound_messages"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("acquisition_leads.id", ondelete="SET NULL"), index=True, nullable=True
    )
    sender_number: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    provider_message_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    occurred_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    message_type: Mapped[str] = mapped_column(String(20), default="text", nullable=False)
    text: Mapped[Optional[str]] = mapped_column(Text)
    media_meta: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    payload_hash: Mapped[Optional[str]] = mapped_column(String(64))
    processing_status: Mapped[str] = mapped_column(String(20), default="received", nullable=False, index=True)
    intent: Mapped[Optional[str]] = mapped_column(String(30))
    buying_signal: Mapped[bool] = mapped_column(default=False, nullable=False)
    objection: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "lead_id": str(self.lead_id) if self.lead_id else None,
            "sender_number": self.sender_number,
            "provider_message_id": self.provider_message_id,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "message_type": self.message_type,
            "text": self.text,
            "processing_status": self.processing_status,
            "intent": self.intent,
            "buying_signal": self.buying_signal,
            "objection": self.objection,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
