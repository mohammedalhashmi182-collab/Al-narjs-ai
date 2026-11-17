"""Route sales, marketing and customer-service work by specialty and capacity.

The CEO does not spread one job across all 39 registered agents. Each kind has
a short roster. The agent with the fewest open tasks on that roster gets the
work. A stable order breaks ties, so the choice does not rotate for its own sake.

Duplicate customers are stopped by the task key ``funnel:{kind}:{lead_id}``.
"""

from __future__ import annotations

from sqlalchemy import func, select

SPECIALTY: dict[str, tuple[str, ...]] = {
    "sales": ("sales_closer", "lead_acquisition", "customer_manager"),
    "marketing": ("marketing_agent", "ad_writer", "email_writer", "social_media"),
    "customer_service": ("customer_service", "customer_manager"),
}

FUNNEL_HOLD = "funnel_hold"


def roster(kind: str) -> tuple[str, ...]:
    try:
        return SPECIALTY[kind]
    except KeyError as exc:
        raise ValueError(f"unknown work kind: {kind}") from exc


def choose_agent(kind: str, open_counts: dict[str, int]) -> str:
    """Pick the least-loaded specialist. Never a slug outside the roster."""
    names = roster(kind)
    return min(names, key=lambda slug: (int(open_counts.get(slug, 0)), names.index(slug)))


async def open_task_counts(session) -> dict[str, int]:
    from src.models import Task

    rows = (
        await session.execute(
            select(Task.owner_agent, func.count())
            .where(Task.status.in_(("queued", "running")))
            .group_by(Task.owner_agent)
        )
    ).all()
    return {str(owner): int(count) for owner, count in rows if owner}


def task_key(kind: str, lead_id) -> str:
    return f"funnel:{kind}:{lead_id}"


async def assign_lead_task(session, *, lead_id, kind: str, title: str, next_step: str, sla_due_at) -> dict:
    """Create the specialty task once. A second call returns the existing row."""
    from src.models import Task

    key = task_key(kind, lead_id)
    existing = (await session.execute(select(Task).where(Task.key == key))).scalar_one_or_none()
    if existing is not None:
        return {"key": existing.key, "owner_agent": existing.owner_agent, "created": False}

    owner = choose_agent(kind, await open_task_counts(session))
    task = Task(
        key=key,
        title=title[:512],
        description=next_step,
        source="funnel_callback",
        status="queued",
        priority=160,
        owner_agent=owner,
        department=kind,
        evidence={
            "handler": FUNNEL_HOLD,
            "lead_id": str(lead_id),
            "sla_due_at": sla_due_at.isoformat() if hasattr(sla_due_at, "isoformat") else str(sla_due_at),
            "sent": 0,
        },
        due_at=sla_due_at,
    )
    session.add(task)
    await session.flush()
    return {"key": task.key, "owner_agent": owner, "created": True}


async def record_send_proof(session, *, lead_id, kind: str, message_id: str) -> bool:
    """Attach the Message-ID to the assigned task. No proof, no completion."""
    from src.models import Task

    if not (message_id or "").strip():
        return False
    task = (
        await session.execute(select(Task).where(Task.key == task_key(kind, lead_id)))
    ).scalar_one_or_none()
    if task is None:
        return False
    task.result = {
        **(task.result or {}),
        "send_proof": message_id.strip(),
        "proof_kind": "mailbox_message_id",
        "sent": 1,
    }
    task.status = "completed"
    task.learning = "أُثبت الإرسال بمعرّف الرسالة. لم يُستنتج التسليم من رد واجهة الإرسال."
    return True


async def route_open_callbacks(session_factory) -> dict:
    """Assign queued specialty tasks for open callbacks. Sends nothing."""
    from src.models.funnel import FunnelCallback

    assigned = 0
    skipped = 0
    async with session_factory() as session:
        rows = (await session.execute(select(FunnelCallback).where(FunnelCallback.status == "open"))).scalars().all()
        for callback in rows:
            outcome = await assign_lead_task(
                session,
                lead_id=callback.lead_id,
                kind=callback.work_kind or "sales",
                title=f"متابعة عميل {callback.work_kind or 'sales'}",
                next_step=callback.next_step,
                sla_due_at=callback.sla_due_at,
            )
            if outcome["created"]:
                assigned += 1
                if callback.owner_agent != outcome["owner_agent"]:
                    callback.owner_agent = outcome["owner_agent"]
            else:
                skipped += 1
        await session.commit()
    return {"assigned": assigned, "already_assigned": skipped}
