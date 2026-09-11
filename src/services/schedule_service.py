from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from src.utils.logger import get_logger

logger = get_logger(__name__)


async def execute_schedule(session, schedule_id) -> dict:
    from src.models import Schedule

    result = await session.execute(select(Schedule).where(Schedule.id == UUID(schedule_id)))
    sched = result.scalar_one_or_none()
    if not sched:
        return {"status": "not_found", "schedule_id": str(schedule_id)}

    target_type = sched.target_type or ""
    logger.info("Executing schedule %s type=%s target=%s", sched.id, target_type, sched.target_id)
    try:
        if target_type == "lead_email":
            return await _send_lead_followup(sched)
        if target_type == "workflow":
            return await _run_workflow(session, sched)
        if target_type == "agent":
            return await _run_agent(sched)
        return {"status": "unsupported", "target_type": target_type}
    except Exception as e:
        logger.exception("Schedule %s failed: %s", sched.id, e)
        return {"status": "error", "message": str(e)[:300]}


async def _send_lead_followup(sched) -> dict:
    from src.services import email_service

    payload = sched.payload or {}
    step = int(payload.get("step", 1) or 1)
    email = payload.get("email")
    name = payload.get("name") or "عميلنا العزيز"
    if not email:
        return {"status": "skipped_no_email", "step": step}

    ok = await email_service.send_followup(step, to=email, name=name)
    return {"status": "sent" if ok else "failed", "step": step, "to": email}


async def _run_workflow(session, sched) -> dict:
    from src.models import Workflow

    target = str(sched.target_id)
    wf = None
    try:
        wf = (
            await session.execute(select(Workflow).where(Workflow.id == UUID(target)))
        ).scalar_one_or_none()
    except Exception:
        wf = None
    if wf is None:
        wf = (
            await session.execute(select(Workflow).where(Workflow.slug == target))
        ).scalar_one_or_none()
    if not wf:
        return {"status": "no_workflow", "target": target}

    from src.automation.workflow_engine import WorkflowDefinition
    from src.main import app

    definition = WorkflowDefinition(**wf.definition)
    result = await app.state.workflow_engine.execute(definition, sched.payload or {})
    return {"status": "executed"}


async def _run_agent(sched) -> dict:
    from src.main import app

    slug = str(sched.target_id)
    agent = await app.state.agent_registry.get_agent(slug)
    if not agent:
        return {"status": "no_agent", "target": slug}

    template_name = (sched.payload or {}).get("prompt_template")
    tmpl = agent.prompt_templates.get(template_name) if template_name else None
    if not tmpl and agent.prompt_templates:
        tmpl = next(iter(agent.prompt_templates.values()))
    if not tmpl:
        return {"status": "no_template", "target": slug}

    input_data = (sched.payload or {}).get("input", {})
    rendered = app.state.prompt_engine.render(tmpl.template_text, input_data)

    from src.core.model_provider import ModelRequest

    model_request = ModelRequest(
        prompt=rendered.user_prompt,
        system_prompt=rendered.system_prompt,
        temperature=agent.default_parameters.get("temperature", 0.7),
        max_tokens=agent.default_parameters.get("max_tokens", 2000),
    )
    await app.state.model_provider.complete(agent.default_model, model_request)
    return {"status": "executed", "target": slug}