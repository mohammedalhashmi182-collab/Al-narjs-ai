from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings, settings
from src.utils.logger import configure_logging

configure_logging(settings.log_level, settings.log_json)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.db.session import init_db, get_session_factory
    from src.core.agent_registry import AgentRegistry
    from src.core.model_provider import ModelProvider
    from src.core.prompt_engine import PromptEngine
    from src.core.context_manager import ContextManager
    from src.core.state_manager import StateManager
    from src.automation.workflow_engine import WorkflowEngine
    from src.automation.queue_worker import QueueWorker
    from src.automation.scheduler import AgentScheduler
    from src.automation.trigger_engine import TriggerEngine

    await init_db()
    session_factory = get_session_factory()

    agent_registry = AgentRegistry(session_factory)
    await agent_registry.sync_base_agents()

    model_provider = ModelProvider(settings)
    prompt_engine = PromptEngine()
    context_manager = ContextManager()
    state_manager = StateManager(session_factory)
    workflow_engine = WorkflowEngine(agent_registry, model_provider, state_manager, context_manager)
    queue_worker = QueueWorker(agent_registry, model_provider, state_manager, concurrency=settings.queue_worker_concurrency)
    scheduler = AgentScheduler(session_factory)
    trigger_engine = TriggerEngine(session_factory)

    await scheduler.start()
    await trigger_engine.start()
    await queue_worker.start()

    app.state.agent_registry = agent_registry
    app.state.model_provider = model_provider
    app.state.prompt_engine = prompt_engine
    app.state.context_manager = context_manager
    app.state.state_manager = state_manager
    app.state.workflow_engine = workflow_engine
    app.state.queue_worker = queue_worker
    app.state.scheduler = scheduler
    app.state.trigger_engine = trigger_engine
    app.state.session_factory = session_factory

    yield

    await model_provider.close()
    await queue_worker.stop()
    await scheduler.stop()
    await trigger_engine.stop()


app = FastAPI(
    title="AI Agent System",
    description="AI Agent Automation System API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    app.mount("/static", StaticFiles(directory="src/web/static"), name="static")
except Exception:
    pass

templates = Jinja2Templates(directory="src/web/templates")


async def get_session() -> AsyncSession:
    async with app.state.session_factory() as session:
        yield session


class AgentRunRequest(BaseModel):
    input_data: dict = {}
    prompt_template: str = "default"


class WorkflowRunRequest(BaseModel):
    input_data: dict = {}


class ScheduleCreateRequest(BaseModel):
    name: str
    target_type: str
    target_id: str
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    run_once_at: Optional[str] = None
    payload: dict = {}
    timezone: str = "UTC"
    max_runs: Optional[int] = None


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")


@app.get("/agents", response_class=HTMLResponse)
async def agents_page(request: Request):
    return templates.TemplateResponse(request, "agents.html")


@app.get("/workflows", response_class=HTMLResponse)
async def workflows_page(request: Request):
    return templates.TemplateResponse(request, "workflows.html")


@app.get("/schedules", response_class=HTMLResponse)
async def schedules_page(request: Request):
    return templates.TemplateResponse(request, "schedules.html")


@app.get("/executions", response_class=HTMLResponse)
async def executions_page(request: Request):
    return templates.TemplateResponse(request, "executions.html")


@app.get("/api/agents")
async def list_agents(category: Optional[str] = None):
    from src.core.agent_registry import AgentCategory
    cat = AgentCategory(category) if category else None
    agents = await app.state.agent_registry.list_agents(cat)
    return {"agents": [a.model_dump() for a in agents]}


@app.get("/api/agents/{slug}")
async def get_agent(slug: str):
    agent = await app.state.agent_registry.get_agent(slug)
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent.model_dump()


@app.post("/api/agents/{slug}/run")
async def run_agent(slug: str, request: AgentRunRequest):
    agent = await app.state.agent_registry.get_agent(slug)
    if not agent:
        raise HTTPException(404, "Agent not found")

    tmpl = agent.prompt_templates.get(request.prompt_template)
    if not tmpl:
        raise HTTPException(404, "Prompt template not found")

    rendered = app.state.prompt_engine.render(tmpl.template_text, request.input_data)

    from src.core.model_provider import ModelRequest
    model_request = ModelRequest(
        prompt=rendered.user_prompt,
        system_prompt=rendered.system_prompt,
        temperature=agent.default_parameters.get("temperature", 0.7),
        max_tokens=agent.default_parameters.get("max_tokens", 2000),
    )

    response = await app.state.model_provider.complete(agent.default_model, model_request)
    return {
        "content": response.content,
        "structured_output": response.structured_output.model_dump() if response.structured_output else None,
        "tokens_used": response.tokens_used,
        "latency_ms": response.latency_ms,
        "model": response.model,
    }


@app.post("/api/workflows/{slug}/run")
async def run_workflow(slug: str, request: WorkflowRunRequest):
    from src.models import Workflow as DBWorkflow
    from sqlalchemy import select

    async with app.state.session_factory() as session:
        result = await session.execute(select(DBWorkflow).where(DBWorkflow.slug == slug))
        workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(404, "Workflow not found")

    from src.automation.workflow_engine import WorkflowDefinition
    definition = WorkflowDefinition.model_validate(workflow.definition)

    result = await app.state.workflow_engine.execute(definition, request.input_data)
    return {
        "workflow_id": str(result.workflow_id),
        "success": result.success,
        "final_context": result.final_context,
        "error": result.error,
        "steps_completed": result.steps_completed,
        "steps_failed": result.steps_failed,
    }


@app.get("/api/schedules")
async def list_schedules():
    jobs = app.state.scheduler.get_jobs()
    return {"schedules": jobs}


@app.post("/api/schedules")
async def create_schedule(request: ScheduleCreateRequest):
    from uuid import UUID
    from src.automation.scheduler import ScheduleConfig
    from datetime import datetime

    config = ScheduleConfig(
        name=request.name,
        target_type=request.target_type,
        target_id=UUID(request.target_id),
        payload=request.payload,
        cron_expression=request.cron_expression,
        interval_seconds=request.interval_seconds,
        run_once_at=datetime.fromisoformat(request.run_once_at) if request.run_once_at else None,
        timezone=request.timezone,
        max_runs=request.max_runs,
    )
    schedule_id = await app.state.scheduler.add_schedule(config)
    return {"schedule_id": str(schedule_id)}


@app.delete("/api/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str):
    from uuid import UUID
    success = await app.state.scheduler.remove_schedule(UUID(schedule_id))
    if not success:
        raise HTTPException(404, "Schedule not found")
    return {"success": True}


@app.get("/api/queue/stats")
async def queue_stats():
    return app.state.queue_worker.get_queue_stats()


@app.post("/api/queue/enqueue")
async def enqueue_task(
    agent_slug: str,
    input_data: dict,
    prompt_template: str = "default",
    priority: int = 50,
):
    from src.automation.queue_worker import TaskPriority
    task_id = await app.state.queue_worker.enqueue_agent(
        agent_slug=agent_slug,
        input_data=input_data,
        prompt_template=prompt_template,
        priority=TaskPriority(priority),
    )
    return {"task_id": task_id}


@app.get("/api/executions")
async def list_executions(limit: int = 50, offset: int = 0):
    from src.models import WorkflowExecution
    from sqlalchemy import select, desc

    async with app.state.session_factory() as session:
        result = await session.execute(
            select(WorkflowExecution)
            .order_by(desc(WorkflowExecution.created_at))
            .limit(limit)
            .offset(offset)
        )
        executions = result.scalars().all()
        return {"executions": [e.to_dict() for e in executions]}


@app.get("/api/executions/{execution_id}")
async def get_execution(execution_id: str):
    from src.models import WorkflowExecution, StepExecution
    from sqlalchemy import select
    from uuid import UUID

    async with app.state.session_factory() as session:
        result = await session.execute(select(WorkflowExecution).where(WorkflowExecution.id == UUID(execution_id)))
        execution = result.scalar_one_or_none()
        if not execution:
            raise HTTPException(404, "Execution not found")

        steps_result = await session.execute(
            select(StepExecution).where(StepExecution.workflow_execution_id == UUID(execution_id))
        )
        steps = steps_result.scalars().all()

    return {
        "execution": execution.to_dict(),
        "steps": [s.to_dict() for s in steps],
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except Exception:
        pass