from __future__ import annotations

from typing import Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Agent, PromptTemplate, Workflow, WorkflowExecution, StepExecution, Schedule
from src.core.model_provider import ModelProvider, ModelRequest
from src.core.prompt_engine import PromptEngine
from src.core.state_manager import StateManager
from src.core.agent_registry import AgentRegistry
from src.core.context_manager import ContextManager
from src.automation.workflow_engine import WorkflowEngine, WorkflowDefinition
from src.config.settings import get_settings
from src.db.session import get_session_factory


async def execute_agent(
    session: AsyncSession,
    agent_id: UUID,
    input_data: dict,
    prompt_template_name: str = "default",
) -> dict:
    session_factory = await get_session_factory()
    agent_registry = AgentRegistry(session_factory)
    agent = await agent_registry.get_agent(str(agent_id))

    if not agent:
        raise ValueError(f"Agent {agent_id} not found")

    tmpl = agent.prompt_templates.get(prompt_template_name)
    if not tmpl:
        raise ValueError(f"Prompt template {prompt_template_name} not found")

    prompt_engine = PromptEngine()
    rendered = prompt_engine.render(tmpl.template_text, input_data)

    settings = agent.default_parameters
    request = ModelRequest(
        prompt=rendered.user_prompt,
        system_prompt=rendered.system_prompt,
        temperature=settings.get("temperature", 0.7),
        max_tokens=settings.get("max_tokens", 2000),
    )

    model_provider = ModelProvider(get_settings())
    response = await model_provider.complete(agent.default_model, request)

    return {
        "content": response.content,
        "structured_output": response.structured_output.model_dump() if response.structured_output else None,
        "tokens_used": response.tokens_used,
        "latency_ms": response.latency_ms,
        "model": response.model,
    }


async def execute_workflow(
    session: AsyncSession,
    workflow_id: UUID,
    input_data: dict,
) -> dict:
    settings = get_settings()
    session_factory = await get_session_factory()
    agent_registry = AgentRegistry(session_factory)
    model_provider = ModelProvider(settings)
    context_manager = ContextManager()
    state_manager = StateManager(session_factory)
    workflow_engine = WorkflowEngine(agent_registry, model_provider, state_manager, context_manager)

    result = await session.execute(select(Workflow).where(Workflow.slug == str(workflow_id)))
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise ValueError(f"Workflow {workflow_id} not found")

    definition = WorkflowDefinition.model_validate(workflow.definition)

    result = await workflow_engine.execute(definition, input_data)

    return {
        "workflow_id": str(result.workflow_id),
        "success": result.success,
        "final_context": result.final_context,
        "error": result.error,
        "steps_completed": result.steps_completed,
        "steps_failed": result.steps_failed,
    }


async def execute_schedule(session: AsyncSession, schedule_id: UUID):
    result = await session.execute(select(Schedule).where(Schedule.id == schedule_id))
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise ValueError(f"Schedule {schedule_id} not found")

    if schedule.target_type == "agent":
        await execute_agent(session, schedule.target_id, schedule.payload)
    elif schedule.target_type == "workflow":
        await execute_workflow(session, schedule.target_id, schedule.payload)

    schedule.run_count += 1
    schedule.last_run_at = func.now()
    if schedule.max_runs and schedule.run_count >= schedule.max_runs:
        schedule.is_active = False
    await session.commit()