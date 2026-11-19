"""Drain ``company_tasks`` that the CEO brain queues and nobody else executes.

The brain promotes observable work into ``company_tasks`` with status
``queued``. Nothing in the process claimed those rows, so a task such as
"Qualify N new/ready leads" stayed queued indefinitely.

This runner is the missing consumer. It is deliberately narrow:

* Qualification writes a count-only report and, for at most five recent
  inbound enquiries, a draft in the existing campaign tables.
* ``opt_out`` is not marketing consent. Imported and historical records are
  counted and left untouched.
* Lead status and outreach status are not modified.
* Nothing is emailed, messaged, or posted.
* A task with no safe handler is marked ``escalated`` with an explicit
  blocker instead of sitting in ``queued``.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, update

from src.utils.logger import get_logger

logger = get_logger(__name__)

MAX_TASKS_PER_RUN = 25
DRAFT_CAP = 5
INBOUND_SOURCES = frozenset({"website", "consult_assistant", "assistant"})

_QUALIFY_LEARNING = (
    "أُنجز تقرير التأهيل دون تغيير حالة أي عميل ودون إرسال. "
    "المسودات، إن وُجدت، لطلبات واردة فقط وبحد خمسة، وتنتظر موافقة المالك قبل أي إرسال. "
    "سجلات الاستيراد وغياب إلغاء الاشتراك ليسا إذناً بالتسويق."
)
_BLOCKED_LEARNING = (
    "لا يوجد منفّذ آمن لهذه المهمة. لم يُرسَل شيء ولم تُغيَّر بيانات العملاء. تحتاج قرار المالك."
)
_DENIED_LEARNING = (
    "سياسة الوكيل لا تسمح بالعمل الداخلي لهذه المهمة. لم يُرسَل شيء ولم تُغيَّر بيانات العملاء."
)
_FAILED_LEARNING = "تعذّر تنفيذ المهمة. لم يُرسَل شيء ولم تُغيَّر بيانات العملاء."


def handler_for(task) -> str:
    evidence = task.evidence or {}
    explicit = str(evidence.get("handler") or "").strip()
    if explicit == "qualify_new_ready":
        return explicit
    title = (task.title or "").strip().lower()
    if title.startswith("qualify ") or "new/ready leads" in title:
        return "qualify_new_ready"
    return ""


async def run_queued_tasks(session_factory, *, governance=None, limit: int = MAX_TASKS_PER_RUN) -> dict:
    """Claim queued company tasks and finish or escalate each one."""
    completed = escalated = failed = 0
    reports: list[dict] = []
    for _ in range(limit):
        task_id = await _claim_next(session_factory)
        if task_id is None:
            break
        outcome = await _execute_one(session_factory, task_id, governance)
        reports.append(outcome)
        status = outcome.get("status")
        if status == "completed":
            completed += 1
        elif status == "escalated":
            escalated += 1
        else:
            failed += 1
    return {
        "claimed": len(reports),
        "completed": completed,
        "escalated": escalated,
        "failed": failed,
        "tasks": reports,
    }


async def _claim_next(session_factory) -> UUID | None:
    from src.models import Task

    # PostgreSQL workers skip locked rows. SQLite serializes the UPDATE.
    candidate = (
        select(Task.id)
        .where(Task.status == "queued", ~Task.key.like("funnel:%"))
        .order_by(Task.priority.desc(), Task.created_at.asc(), Task.id.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    async with session_factory() as session:
        task_id = (
            await session.execute(
                update(Task)
                .where(Task.id == candidate.scalar_subquery(), Task.status == "queued")
                .values(status="running")
                .returning(Task.id)
            )
        ).scalar_one_or_none()
        await session.commit()
        return task_id


async def _execute_one(session_factory, task_id: UUID, governance) -> dict:
    from src.models import Task

    async with session_factory() as session:
        task = await session.get(Task, task_id)
        if task is None:
            return {"status": "failed", "blocker_code": "missing"}
        key = task.key
        if task.status != "running":
            return {"key": key, "status": "failed", "blocker_code": "claim_lost"}
        try:
            handler = handler_for(task)
            if handler == "qualify_new_ready":
                allowed = governance is None or (
                    await governance.authorize(task.owner_agent or "sales_closer", "internal")
                ).get("allowed")
                if allowed:
                    payload = await _qualify(session, task)
                else:
                    payload = {
                        "status": "escalated",
                        "learning": _DENIED_LEARNING,
                        "result": {
                            "handler": handler,
                            "blocker_code": "policy_denied",
                            "sent": 0,
                            "lead_status_changed": 0,
                        },
                    }
            else:
                payload = {
                    "status": "escalated",
                    "learning": _BLOCKED_LEARNING,
                    "result": {
                        "handler": "none",
                        "blocker_code": "no_executor",
                        "sent": 0,
                        "lead_status_changed": 0,
                    },
                }
            if not await _save_outcome(session, task_id, payload):
                return {"key": key, "status": "failed", "blocker_code": "claim_lost"}
        except Exception as exc:  # noqa: BLE001 - one task must not stall the drain
            await session.rollback()
            logger.warning("company task failed", error_type=type(exc).__name__)
            failure = {
                "status": "failed",
                "learning": _FAILED_LEARNING,
                "result": {
                    "blocker_code": "executor_error",
                    "error_type": type(exc).__name__,
                    "sent": 0,
                    "lead_status_changed": 0,
                },
            }
            saved = await _save_outcome(session, task_id, failure)
            blocker = "executor_error" if saved else "claim_lost"
            return {"key": key, "status": "failed", "blocker_code": blocker}
        return {
            "key": key,
            "status": payload["status"],
            "blocker_code": payload["result"].get("blocker_code"),
            "drafts_prepared": payload["result"].get("drafts_prepared", 0),
        }


async def _save_outcome(session, task_id: UUID, payload: dict) -> bool:
    from src.models import Task

    saved = (
        await session.execute(
            update(Task)
            .where(Task.id == task_id, Task.status == "running")
            .values(**payload)
            .returning(Task.id)
        )
    ).scalar_one_or_none()
    if saved is None:
        await session.rollback()
        return False
    await session.commit()
    return True


async def _qualify(session, task) -> dict:
    """Count the new/ready pool and draft at most five inbound enquiries."""
    from src.models import AcquisitionLead, Campaign, CampaignLead
    from src.services.lead_normalize import is_valid_email, is_valid_phone
    from src.services.lead_outreach import generate_message

    rows = (
        await session.execute(
            select(
                AcquisitionLead.id,
                AcquisitionLead.source,
                AcquisitionLead.opt_out,
                AcquisitionLead.email,
                AcquisitionLead.phone,
                AcquisitionLead.priority_score,
            ).where(AcquisitionLead.lead_status.in_(("NEW", "READY")))
        )
    ).all()

    new_or_ready = len(rows)
    opt_out = 0
    inbound = 0
    reachable = 0
    eligible: list[tuple] = []
    for lead_id, source, opted_out, email, phone, score in rows:
        if opted_out:
            opt_out += 1
        can_reach = is_valid_email(email) or is_valid_phone(phone)
        if can_reach:
            reachable += 1
        is_inbound = (source or "") in INBOUND_SOURCES
        if is_inbound:
            inbound += 1
        if is_inbound and not opted_out and can_reach:
            eligible.append((int(score or 0), lead_id))

    eligible.sort(key=lambda item: item[0], reverse=True)
    chosen = [lead_id for _score, lead_id in eligible[:DRAFT_CAP]]

    drafts_prepared = 0
    campaign_id = None
    if chosen:
        name = f"owner-review:{task.key}"
        campaign = (
            await session.execute(select(Campaign).where(Campaign.name == name))
        ).scalars().first()
        if campaign is None:
            batch_no = (
                await session.execute(select(func.max(Campaign.batch_no)))
            ).scalar_one_or_none()
            campaign = Campaign(
                name=name,
                batch_no=int(batch_no or 0) + 1,
                description="Inbound enquiry drafts awaiting owner approval. Nothing is sent.",
                status="awaiting_owner_approval",
            )
            session.add(campaign)
            await session.flush()
        campaign_id = str(campaign.id)
        already = set(
            (
                await session.execute(
                    select(CampaignLead.lead_id).where(CampaignLead.campaign_id == campaign.id)
                )
            ).scalars().all()
        )
        for lead_id in chosen:
            if lead_id in already:
                continue
            lead = await session.get(AcquisitionLead, lead_id)
            if lead is None or lead.lead_status not in ("NEW", "READY") or lead.opt_out:
                continue
            if (lead.source or "") not in INBOUND_SOURCES:
                continue
            draft = generate_message(lead)
            session.add(
                CampaignLead(
                    campaign_id=campaign.id,
                    lead_id=lead.id,
                    segment=lead.segment,
                    message_variant=draft["variant"],
                    message_text=draft["message"],
                    status="DRAFT",
                )
            )
            drafts_prepared += 1

    blocker = "drafts_await_owner" if drafts_prepared else "no_consented_outreach"
    return {
        "status": "completed",
        "learning": _QUALIFY_LEARNING,
        "result": {
            "handler": "qualify_new_ready",
            "blocker_code": blocker,
            "counts": {
                "new_or_ready": new_or_ready,
                "opt_out": opt_out,
                "inbound": inbound,
                "cold": new_or_ready - inbound,
                "reachable": reachable,
                "eligible_inbound": len(eligible),
            },
            "drafts_prepared": drafts_prepared,
            "draft_cap": DRAFT_CAP,
            "campaign_id": campaign_id,
            "sent": 0,
            "lead_status_changed": 0,
        },
    }
