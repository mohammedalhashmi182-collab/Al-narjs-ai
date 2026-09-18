"""Opportunity engine (Phase C) — agents and the CEO brain discover work.

The loop: observe -> detect -> evidence -> estimate impact -> create (dedup) ->
prioritize -> assign (promote to task) -> execute -> measure -> learn.

Deduplication: same ``owner_agent`` + normalized title hash to the same ``key``.
A repeat finding updates the existing open opportunity instead of duplicating it,
so agents can never flood the backlog with the same task.
"""

from __future__ import annotations

import hashlib
import re

from sqlalchemy import select

from src.utils.logger import get_logger

logger = get_logger(__name__)


def _slugify(title: str) -> str:
    slug = re.sub(r"[^0-9a-zA-Zا-ي]+", "-", title.strip().lower())
    return re.sub(r"-{2,}", "-", slug).strip("-")[:120]


def _opportunity_key(owner_agent: str, title: str) -> str:
    raw = f"{owner_agent}|{_slugify(title)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


class OpportunityEngine:
    def __init__(self, db_session_factory):
        self._db_session_factory = db_session_factory

    async def create(
        self,
        *,
        title: str,
        owner_agent: str,
        area: str,
        source: str = "agent",
        description: str | None = None,
        evidence: dict | None = None,
        impact: str | None = None,
        confidence: float = 0.0,
        priority: int = 50,
    ) -> dict:
        """Create an opportunity, or refresh its evidence if the key already exists open."""
        from src.models import Opportunity

        key = _opportunity_key(owner_agent, title)
        async with self._db_session_factory() as session:
            existing = (
                await session.execute(
                    select(Opportunity).where(Opportunity.key == key)
                )
            ).scalar_one_or_none()

            if existing is not None and existing.status in ("open", "assigned"):
                if evidence:
                    existing.evidence = {**(existing.evidence or {}), **evidence}
                existing.confidence = max(existing.confidence or 0.0, confidence)
                existing.priority = max(existing.priority or 0, priority)
                await session.commit()
                return {**existing.to_dict(), "deduplicated": True}

            if existing is not None:
                existing.evidence = {**(existing.evidence or {}), **(evidence or {})}
                await session.commit()
                return {**existing.to_dict(), "deduplicated": True}

            opportunity = Opportunity(
                key=key,
                title=title,
                description=description,
                area=area,
                source=source,
                evidence=evidence or {},
                impact=impact,
                confidence=confidence,
                priority=priority,
                owner_agent=owner_agent,
                status="open",
            )
            session.add(opportunity)
            await session.commit()
            await session.refresh(opportunity)
            return {**opportunity.to_dict(), "deduplicated": False}

    async def promote_to_task(
        self,
        key: str,
        *,
        department: str | None = None,
        due_at=None,
    ) -> dict | None:
        """Assign the highest-confidence open opportunity as a concrete Task."""
        from src.models import Opportunity, Task

        async with self._db_session_factory() as session:
            opp = (
                await session.execute(select(Opportunity).where(Opportunity.key == key))
            ).scalar_one_or_none()
            if opp is None or opp.status not in ("open", "assigned"):
                return None

            existing_task = (
                await session.execute(select(Task).where(Task.key == opp.key))
            ).scalar_one_or_none()
            if existing_task:
                return existing_task.to_dict()

            task = Task(
                key=opp.key,
                title=opp.title,
                description=opp.description,
                source=opp.source,
                priority=opp.priority,
                impact=opp.impact,
                confidence=opp.confidence,
                owner_agent=opp.owner_agent or "orchestrator",
                department=department,
                evidence=opp.evidence,
                due_at=due_at,
            )
            session.add(task)
            opp.status = "assigned"
            opp.linked_task_key = opp.key
            await session.commit()
            await session.refresh(task)
            return task.to_dict()

    async def list(self, *, status: str | None = None, area: str | None = None, limit: int = 200) -> list[dict]:
        from src.models import Opportunity

        query = select(Opportunity).order_by(Opportunity.priority.desc(), Opportunity.created_at.desc()).limit(limit)
        if status:
            query = query.where(Opportunity.status == status)
        if area:
            query = query.where(Opportunity.area == area)
        async with self._db_session_factory() as session:
            rows = (await session.execute(query)).scalars().all()
            return [o.to_dict() for o in rows]

    async def update_status(self, key: str, *, status: str, result: dict | None = None, learning: str | None = None) -> dict | None:
        from src.models import Opportunity

        async with self._db_session_factory() as session:
            opp = (
                await session.execute(select(Opportunity).where(Opportunity.key == key))
            ).scalar_one_or_none()
            if opp is None:
                return None
            opp.status = status
            if result is not None:
                opp.evidence = {**(opp.evidence or {}), "result": result}
            await session.commit()
            await session.refresh(opp)
            return opp.to_dict()
