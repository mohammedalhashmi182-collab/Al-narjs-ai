"""Governance service (Phase C) — autonomy BY POLICY, not by accident.

Each agent has an ``AgentPolicy`` contract with an autonomy level:

* Level 0 — read only.
* Level 1 — internal autonomy (create tasks, drafts, internal records).
* Level 2 — pre-authorized external execution inside an approved policy.
* Level 3 — owner approval required.

``authorize()`` is the single gate for any high-impact action. Every denial,
escalation and approval-aware decision is written to the append-only
``Decision`` log so nothing becomes invisible to the owner.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Action -> minimum autonomy level required.
ACTION_LEVEL_REQUIREMENT = {
    "read": 0,
    "internal": 1,
    "external": 2,
    "owner_approval": 3,
    "budget_spend": 3,
    "destructive": 3,
    "pricing_change": 3,
    "legal_commitment": 3,
}

DEFAULT_ALLOWED_ACTIONS = ["read", "internal"]
DEFAULT_DENIED_ACTIONS = [
    "destructive",
    "pricing_change",
    "legal_commitment",
    "budget_spend",
]
DEFAULT_REQUIRES_APPROVAL = ["external", "owner_approval"]


class PolicyService:
    def __init__(self, db_session_factory):
        self._db_session_factory = db_session_factory

    async def ensure_policy(self, agent_slug: str, *, level: int = 1) -> dict:
        from src.models import AgentPolicy

        async with self._db_session_factory() as session:
            policy = (
                await session.execute(select(AgentPolicy).where(AgentPolicy.agent_slug == agent_slug))
            ).scalar_one_or_none()
            if policy is None:
                policy = AgentPolicy(
                    agent_slug=agent_slug,
                    autonomy_level=max(0, min(level, 3)),
                    allowed_actions=list(DEFAULT_ALLOWED_ACTIONS),
                    denied_actions=list(DEFAULT_DENIED_ACTIONS),
                    requires_approval=list(DEFAULT_REQUIRES_APPROVAL),
                    budget_usd=0.0,
                )
                session.add(policy)
                await session.commit()
                await session.refresh(policy)
            return policy.to_dict()

    async def get_policy(self, agent_slug: str) -> dict | None:
        from src.models import AgentPolicy

        async with self._db_session_factory() as session:
            policy = (
                await session.execute(select(AgentPolicy).where(AgentPolicy.agent_slug == agent_slug))
            ).scalar_one_or_none()
            return policy.to_dict() if policy else None

    async def upsert_policy(
        self,
        agent_slug: str,
        *,
        autonomy_level: int,
        allowed_actions: list[str] | None = None,
        denied_actions: list[str] | None = None,
        requires_approval: list[str] | None = None,
        budget_usd: float = 0.0,
        rate_limits: dict | None = None,
    ) -> dict:
        from src.models import AgentPolicy

        async with self._db_session_factory() as session:
            policy = (
                await session.execute(select(AgentPolicy).where(AgentPolicy.agent_slug == agent_slug))
            ).scalar_one_or_none()
            if policy is None:
                policy = AgentPolicy(agent_slug=agent_slug)
                session.add(policy)
            policy.autonomy_level = max(0, min(autonomy_level, 3))
            if allowed_actions is not None:
                policy.allowed_actions = allowed_actions
            if denied_actions is not None:
                policy.denied_actions = denied_actions
            if requires_approval is not None:
                policy.requires_approval = requires_approval
            policy.budget_usd = budget_usd
            if rate_limits is not None:
                policy.rate_limits = rate_limits
            await session.commit()
            await session.refresh(policy)
            return policy.to_dict()

    async def list_policies(self) -> list[dict]:
        from src.models import AgentPolicy

        async with self._db_session_factory() as session:
            rows = (await session.execute(select(AgentPolicy).order_by(AgentPolicy.agent_slug))).scalars().all()
            return [p.to_dict() for p in rows]

    async def authorize(self, agent_slug: str, action: str) -> dict:
        """Gate every high-impact action.

        Returns ``{"allowed": bool, "level_required": int, ...}``. Denials and
        escalations are written to the Decision log so the owner always sees them.
        """
        policy = await self.get_policy(agent_slug)
        if policy is None:
            policy = await self.ensure_policy(agent_slug)

        level = policy["autonomy_level"]
        required = ACTION_LEVEL_REQUIREMENT.get(action, 1)

        denied = action in policy["denied_actions"]
        needs_approval = action in policy["requires_approval"]
        allowed_in_alw = action in policy["allowed_actions"]

        if denied:
            allowed, outcome, reason = False, "denied", f"action '{action}' explicitly denied"
        elif allowed_in_alw and level >= required:
            allowed, outcome, reason = True, "allowed", "within policy limits"
        elif needs_approval or level < required:
            allowed, outcome, reason = False, "escalated", (
                f"requires level {required}, agent has level {level} (or approval)"
            )
        else:
            allowed, outcome, reason = False, "escalated", f"not within allowed actions ({action})"

        if outcome != "allowed":
            await self._log(
                entry={
                    "decision": f"escalate {action} for {agent_slug}",
                    "reason": reason,
                    "evidence": {"action": action, "level": level, "policy": policy["autonomy_label"]},
                    "actor": "governance",
                    "expected": "owner reviews and approves or rejects",
                    "status": "escalated",
                }
            )

        return {
            "agent": agent_slug,
            "action": action,
            "allowed": allowed,
            "outcome": outcome,
            "reason": reason,
            "level_required": required,
            "level_actual": level,
            "level_label": policy["autonomy_label"],
        }

    async def _log(self, entry: dict) -> None:
        from src.models import Decision

        async with self._db_session_factory() as session:
            session.add(Decision(
                id=uuid4(),
                decision=entry["decision"],
                reason=entry.get("reason"),
                evidence=entry.get("evidence", {}),
                actor=entry.get("actor", "governance"),
                expected=entry.get("expected"),
                actual=entry.get("actual"),
                status=entry.get("status", "pending"),
                learning=entry.get("learning"),
            ))
            await session.commit()
