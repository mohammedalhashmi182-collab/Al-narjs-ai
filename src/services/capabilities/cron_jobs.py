"""Daily platform summary and an evaluation pass over recent stored outputs.

Counts come from the database. A query that fails is reported as unavailable
and is not replaced with a made-up zero that could be read as a real metric.
"""

from __future__ import annotations

from sqlalchemy import func, select

from src.services import catalog
from src.services.capabilities.config import cron_eval_limit, cron_revise_stored
from src.services.capabilities.eval_loop import persist_log, run_eval_loop
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def _count(session, model) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


async def health_summary(session) -> dict:
    from src.models import ClientProject
    from src.models.usage import UsageEvent

    summary = {
        "agents_in_catalog": catalog.AGENT_COUNT,
        "projects": await _count(session, ClientProject),
        "usage_events": await _count(session, UsageEvent),
    }
    return summary


async def evaluate_recent(session) -> dict:
    from src.models import ClientAgent

    limit = cron_eval_limit()
    rows = (
        await session.execute(
            select(ClientAgent.slug, ClientAgent.result, ClientAgent.project_id)
            .where(ClientAgent.result.is_not(None))
            .order_by(ClientAgent.created_at.desc())
            .limit(limit)
        )
    ).all()
    scored = 0
    passed = 0
    for slug, result, project_id in rows:
        text = (result or "").strip()
        if not text:
            continue
        outcome = run_eval_loop(
            text,
            locale="ar",
            agent_slug=slug or "",
            client_key=str(project_id or ""),
            source="cron",
        )
        # Scores are logged. The stored client result is not replaced: a scheduled
        # job must not silently rewrite a deliverable the client already received.
        scored += 1
        passed += int(outcome.passed)
        try:
            await persist_log(
                session,
                {
                    "agent_slug": slug or "",
                    "client_key": str(project_id or ""),
                    "overall": outcome.scores[-1]["overall"] if outcome.scores else 0,
                    "rounds": outcome.rounds,
                    "passed": outcome.passed,
                    "source": "cron",
                    "scores": outcome.scores[-1] if outcome.scores else {},
                },
            )
        except Exception:  # noqa: BLE001
            logger.warning("eval_log_persist_failed")
    return {
        "scanned": scored,
        "passed": passed,
        "revise_stored": cron_revise_stored(),
    }


async def run_daily() -> dict:
    report: dict = {
        "job": "daily",
        "ok": True,
        "agents_in_catalog": catalog.AGENT_COUNT,
    }
    try:
        from src.db.session import get_session_factory

        factory = await get_session_factory()
        async with factory() as session:
            report["health"] = await health_summary(session)
            report["evaluation"] = await evaluate_recent(session)
    except Exception as exc:  # noqa: BLE001 - the web process must stay up
        report["ok"] = False
        report["db"] = "unavailable"
        report["error_type"] = type(exc).__name__
        logger.warning("cron_daily_failed", error_type=type(exc).__name__)
    else:
        logger.info("cron_daily", ok=True, scanned=(report.get("evaluation") or {}).get("scanned"))
    return report
