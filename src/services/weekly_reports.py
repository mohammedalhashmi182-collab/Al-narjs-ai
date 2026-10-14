"""Weekly report for Operate-plan (``tashgheel``) projects.

Built only from data the system already records for a project:

* ``usage_events``        - conversations (unique contacts, per channel),
                            new contacts vs earlier weeks, voice seconds, Meta fees
* ``subscription_usage``  - the current monthly allowance and how much is used
* ``client_agents``       - the project's agents and their status
* ``agent_knowledge_docs``- knowledge-base size

Never invents numbers: a metric with no data is reported as zero / "no data".
Each report is created as a ``draft``; the owner reviews (optionally edits)
and approves it before anything is sent to the customer.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import ClientAgent, ClientProject
from src.models.ops import WeeklyReport
from src.models.usage import UsageEvent
from src.services import catalog

log = logging.getLogger(__name__)

ELIGIBLE_TIERS = ("tashgheel",)
SCHEDULE_NAME = "ops-weekly-reports"
SCHEDULE_CRON = "0 7 * * 0"  # Sunday 07:00 Riyadh, start of the Saudi work week


def week_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    """The last full week [Sunday 00:00, next Sunday 00:00) in UTC."""
    now = (now or datetime.now(UTC)).astimezone(UTC)
    days_since_sunday = (now.weekday() + 1) % 7
    this_sunday = (now - timedelta(days=days_since_sunday)).replace(hour=0, minute=0, second=0, microsecond=0)
    return this_sunday - timedelta(days=7), this_sunday


def eligible(project) -> bool:
    return project.status == "active" and catalog.limits_tier(project.package) in ELIGIBLE_TIERS


async def collect_metrics(session: AsyncSession, project, start: datetime, end: datetime) -> dict:
    pid = project.id
    ev = (await session.execute(
        select(UsageEvent).where(UsageEvent.project_id == pid, UsageEvent.occurred_at >= start,
                                 UsageEvent.occurred_at < end)
    )).scalars().all()
    convs = [e for e in ev if e.kind == "conversation"]
    contacts = {e.contact_key for e in convs if e.contact_key}
    earlier = set()
    if contacts:
        earlier = set((await session.execute(
            select(UsageEvent.contact_key).where(
                UsageEvent.project_id == pid, UsageEvent.kind == "conversation",
                UsageEvent.occurred_at < start, UsageEvent.contact_key.in_(list(contacts)))
        )).scalars())
    by_channel: dict[str, int] = {}
    for e in convs:
        by_channel[e.channel or "other"] = by_channel.get(e.channel or "other", 0) + int(e.quantity or 1)
    voice_seconds = sum(int(e.quantity or 0) for e in ev if e.kind == "voice")
    meta_fees = sum(int(e.quantity or 0) for e in ev if e.kind == "meta_fee")

    agents = (await session.execute(select(ClientAgent).where(ClientAgent.project_id == pid))).scalars().all()
    agent_status: dict[str, int] = {}
    for a in agents:
        agent_status[a.status] = agent_status.get(a.status, 0) + 1

    kb_docs = 0
    try:
        from src.models.agent_tools import KnowledgeDoc

        kb_docs = int((await session.execute(
            select(func.count()).select_from(KnowledgeDoc).where(KnowledgeDoc.project_id == pid))).scalar() or 0)
    except Exception:  # noqa: BLE001
        pass

    allowance = None
    try:
        from src.services import usage

        row = await usage.current_usage(session, project, end - timedelta(seconds=1))
        allowance = usage.usage_summary(project, row)["metrics"]
    except Exception:  # noqa: BLE001
        log.info("weekly report: no usage window for %s", pid)

    return {
        "conversations": sum(int(e.quantity or 1) for e in convs),
        "unique_contacts": len(contacts),
        "new_contacts": len(contacts - earlier),
        "returning_contacts": len(contacts & earlier),
        "by_channel": by_channel,
        "voice_minutes": round(voice_seconds / 60, 1),
        "meta_fees_sar": round(meta_fees / 100, 2),
        "agents": agent_status,
        "kb_docs": kb_docs,
        "allowance": allowance,
    }


_CH = {"whatsapp": "واتساب", "telegram": "تيليجرام", "messenger": "ماسنجر"}


def render_text(project, m: dict, start: datetime, end: datetime) -> str:
    last_day = (end - timedelta(days=1)).date().isoformat()
    lines = [f"📊 التقرير الأسبوعي — {project.client_name}", f"الفترة: {start.date().isoformat()} إلى {last_day}", ""]
    if not m["conversations"]:
        lines.append("لم تُسجَّل محادثات هذا الأسبوع.")
    else:
        lines.append(f"• المحادثات الذكية: {m['conversations']} (عملاء مختلفون: {m['unique_contacts']})")
        lines.append(f"• عملاء جدد: {m['new_contacts']} · عملاء عائدون: {m['returning_contacts']}")
        if m["by_channel"]:
            lines.append("• حسب القناة: " + "، ".join(f"{_CH.get(k, k)} {v}" for k, v in sorted(m["by_channel"].items())))
    if m["voice_minutes"]:
        lines.append(f"• دقائق الصوت: {m['voice_minutes']}")
    if m["meta_fees_sar"]:
        lines.append(f"• رسوم ميتا هذا الأسبوع: {m['meta_fees_sar']} ر.س")
    if m["agents"]:
        running = m["agents"].get("running", 0) + m["agents"].get("done", 0)
        lines.append(f"• الوكلاء: {sum(m['agents'].values())} (يعمل/أنجز: {running})")
    lines.append(f"• مستندات قاعدة المعرفة: {m['kb_docs']}")
    conv = (m.get("allowance") or {}).get("conversations")
    if conv and conv.get("limit"):
        lines.append(f"• استهلاك الشهر: {conv['used']} من {conv['limit']} محادثة ({conv['pct']}٪)")
    lines += ["", "أي ملاحظة أو طلب؟ رد على هذه الرسالة."]
    return "\n".join(lines)


async def generate_for_project(session: AsyncSession, project, now: datetime | None = None) -> WeeklyReport:
    start, end = week_bounds(now)
    existing = (await session.execute(
        select(WeeklyReport).where(WeeklyReport.project_id == project.id, WeeklyReport.week_start == start)
    )).scalar_one_or_none()
    if existing is not None:
        return existing
    m = await collect_metrics(session, project, start, end)
    rep = WeeklyReport(id=uuid4(), project_id=project.id, week_start=start, week_end=end,
                       metrics=m, text=render_text(project, m, start, end), status="draft")
    session.add(rep)
    await session.flush()
    return rep


async def generate_all(session: AsyncSession, now: datetime | None = None) -> list[WeeklyReport]:
    projects = (await session.execute(select(ClientProject).where(ClientProject.status == "active"))).scalars().all()
    out = []
    for p in projects:
        if eligible(p):
            out.append(await generate_for_project(session, p, now))
    await session.commit()
    if out:
        from src.services import ops_monitor

        await ops_monitor.alert_owner(
            "weekly-reports", f"📝 {len(out)} تقرير أسبوعي جاهز للمراجعة قبل الإرسال: /api/owner/ops/weekly-reports",
            cooldown=3600)
    return out


async def _get(session: AsyncSession, report_id: Any) -> WeeklyReport:
    rep = await session.get(WeeklyReport, report_id if isinstance(report_id, UUID) else UUID(str(report_id)))
    if rep is None:
        raise LookupError("report not found")
    return rep


async def edit(session: AsyncSession, report_id: Any, text: str) -> WeeklyReport:
    rep = await _get(session, report_id)
    if rep.status != "draft":
        raise ValueError("only drafts can be edited")
    if not (text or "").strip():
        raise ValueError("empty text")
    rep.final_text = text.strip()[:4000]
    await session.flush()
    return rep


async def reject(session: AsyncSession, report_id: Any) -> WeeklyReport:
    rep = await _get(session, report_id)
    if rep.status != "draft":
        raise ValueError("only drafts can be rejected")
    rep.status, rep.decided_at = "rejected", datetime.now(UTC)
    await session.flush()
    return rep


async def approve_and_send(session: AsyncSession, report_id: Any) -> WeeklyReport:
    """Owner approval: send to the project's phone over WhatsApp (template path outside 24h)."""
    from src.services import wa_templates

    rep = await _get(session, report_id)
    if rep.status != "draft":
        raise ValueError("report already decided")
    project = await session.get(ClientProject, rep.project_id)
    rep.status, rep.decided_at = "approved", datetime.now(UTC)
    text = rep.final_text or rep.text
    res = await wa_templates.send_business_initiated(
        session, phone=project.phone if project else None, purpose="weekly_report", text=text,
        params=[project.client_name if project else "", str((rep.metrics or {}).get("conversations", 0))],
    )
    rep.send_result = res
    rep.status = "sent" if res.get("ok") else ("approved" if res.get("path") == "fallback" else "failed")
    await session.flush()
    return rep


def to_dict(r: WeeklyReport) -> dict:
    return {
        "id": str(r.id), "project_id": str(r.project_id),
        "week_start": r.week_start.isoformat() if r.week_start else None,
        "week_end": r.week_end.isoformat() if r.week_end else None,
        "metrics": r.metrics or {}, "text": r.text, "final_text": r.final_text,
        "status": r.status, "send_result": r.send_result,
        "decided_at": r.decided_at.isoformat() if r.decided_at else None,
    }


async def ensure_schedule(scheduler) -> None:
    from src.automation.scheduler import ScheduleConfig
    from src.models import Schedule

    try:
        async with scheduler.session_factory() as session:
            exists = (await session.execute(select(Schedule).where(Schedule.name == SCHEDULE_NAME))).scalar_one_or_none()
        if exists is not None:
            return
        await scheduler.add_schedule(ScheduleConfig(
            name=SCHEDULE_NAME, target_type="weekly_reports", target_id=uuid4(),
            cron_expression=SCHEDULE_CRON, timezone="Asia/Riyadh"))
    except Exception as e:  # pragma: no cover
        log.warning("Could not register weekly report schedule: %s", e)
