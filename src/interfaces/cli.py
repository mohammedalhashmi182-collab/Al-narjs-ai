from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.config.settings import get_settings
from src.core.agent_registry import AgentRegistry
from src.core.model_provider import ModelProvider, ModelRequest, ModelSpec
from src.core.prompt_engine import PromptEngine
from src.core.context_manager import ContextManager
from src.core.state_manager import StateManager
from src.automation.workflow_engine import WorkflowEngine, WorkflowDefinition, WorkflowStep
from src.automation.queue_worker import QueueWorker, QueueTask, TaskPriority
from src.automation.scheduler import AgentScheduler, ScheduleConfig
from src.automation.trigger_engine import TriggerEngine
from src.utils.logger import configure_logging

app = typer.Typer(name="ai-agent", help="AI Agent Automation System CLI")
console = Console()

settings = get_settings()
configure_logging(settings.log_level, settings.log_json)

agent_registry = None
model_provider = None
prompt_engine = None
context_manager = None
state_manager = None
workflow_engine = None
queue_worker = None
scheduler = None
trigger_engine = None


def get_components():
    global agent_registry, model_provider, prompt_engine, context_manager, state_manager
    global workflow_engine, queue_worker, scheduler, trigger_engine

    from src.db.session import get_session_factory

    session_factory = get_session_factory()

    if agent_registry is None:
        agent_registry = AgentRegistry(session_factory)
    if model_provider is None:
        model_provider = ModelProvider(settings)
    if prompt_engine is None:
        prompt_engine = PromptEngine()
    if context_manager is None:
        context_manager = ContextManager()
    if state_manager is None:
        state_manager = StateManager(session_factory)
    if workflow_engine is None:
        workflow_engine = WorkflowEngine(
            agent_registry, model_provider, state_manager, context_manager
        )
    if queue_worker is None:
        queue_worker = QueueWorker(
            agent_registry, model_provider, state_manager,
            concurrency=settings.queue_worker_concurrency
        )
    if scheduler is None:
        scheduler = AgentScheduler(session_factory)
    if trigger_engine is None:
        trigger_engine = TriggerEngine(session_factory)

    return {
        "agent_registry": agent_registry,
        "model_provider": model_provider,
        "prompt_engine": prompt_engine,
        "context_manager": context_manager,
        "state_manager": state_manager,
        "workflow_engine": workflow_engine,
        "queue_worker": queue_worker,
        "scheduler": scheduler,
        "trigger_engine": trigger_engine,
    }


@app.command()
def init():
    """Initialize the system (create DB tables, sync base agents)"""
    async def _init():
        from src.db.session import init_db
        await init_db()

        comps = get_components()
        await comps["agent_registry"].sync_base_agents()
        await comps["scheduler"].start()
        await comps["trigger_engine"].start()
        await comps["queue_worker"].start()

        console.print("[green]System initialized successfully![/green]")

    asyncio.run(_init())


@app.command()
def agent_list(category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter by category")):
    """List all agents"""
    async def _list():
        comps = get_components()
        cat = None
        if category:
            from src.core.agent_registry import AgentCategory
            cat = AgentCategory(category)
        agents = await comps["agent_registry"].list_agents(cat)

        table = Table(title="Agents")
        table.add_column("Slug", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Category", style="yellow")
        table.add_column("Model", style="blue")
        table.add_column("System", style="red")

        for agent in agents:
            table.add_row(
                agent.slug,
                agent.name,
                agent.category.value,
                agent.default_model,
                "✓" if agent.is_system else "✗"
            )

        console.print(table)

    asyncio.run(_list())


@app.command()
def agent_run(
    slug: str = typer.Argument(..., help="Agent slug"),
    input_data: str = typer.Option("{}", "--input", "-i", help="Input JSON"),
    prompt_template: str = typer.Option("default", "--template", "-t", help="Prompt template"),
):
    """Run an agent"""
    async def _run():
        comps = get_components()
        agent = await comps["agent_registry"].get_agent(slug)
        if not agent:
            console.print(f"[red]Agent '{slug}' not found[/red]")
            return

        data = json.loads(input_data)
        tmpl = agent.prompt_templates.get(prompt_template)
        if not tmpl:
            console.print(f"[red]Prompt template '{prompt_template}' not found[/red]")
            return

        rendered = comps["prompt_engine"].render(tmpl.template_text, data)
        request = ModelRequest(
            prompt=rendered.user_prompt,
            system_prompt=rendered.system_prompt,
            temperature=agent.default_parameters.get("temperature", 0.7),
            max_tokens=agent.default_parameters.get("max_tokens", 2000),
        )

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
            task = progress.add_task(f"Running {slug}...", total=None)
            response = await comps["model_provider"].complete(agent.default_model, request)

        console.print(Panel(response.content, title=f"Response from {slug}", border_style="green"))
        console.print(f"[dim]Tokens: {response.tokens_used}, Latency: {response.latency_ms}ms[/dim]")

    asyncio.run(_run())


@app.command()
def workflow_run(
    slug: str = typer.Argument(..., help="Workflow slug"),
    input_data: str = typer.Option("{}", "--input", "-i", help="Input JSON"),
):
    """Run a workflow"""
    async def _run():
        comps = get_components()
        # Load workflow definition from DB
        from src.models import Workflow as DBWorkflow
        from sqlalchemy import select

        async with comps["agent_registry"]._db_session_factory() as session:
            result = await session.execute(select(DBWorkflow).where(DBWorkflow.slug == slug))
            workflow = result.scalar_one_or_none()

        if not workflow:
            console.print(f"[red]Workflow '{slug}' not found[/red]")
            return

        definition = WorkflowDefinition.model_validate(workflow.definition)
        data = json.loads(input_data)

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
            task = progress.add_task(f"Running workflow {slug}...", total=None)
            result = await comps["workflow_engine"].execute(definition, data)

        if result.success:
            console.print("[green]Workflow completed successfully![/green]")
        else:
            console.print(f"[red]Workflow failed: {result.error}[/red]")

        console.print(Panel(json.dumps(result.final_context, indent=2, ensure_ascii=False), title="Final Context"))

    asyncio.run(_run())


@app.command()
def schedule_add(
    name: str = typer.Argument(..., help="Schedule name"),
    target_type: str = typer.Argument(..., help="Target type (agent/workflow)"),
    target_id: str = typer.Argument(..., help="Target UUID"),
    cron: Optional[str] = typer.Option(None, "--cron", help="Cron expression"),
    interval: Optional[int] = typer.Option(None, "--interval", help="Interval in seconds"),
    once: Optional[str] = typer.Option(None, "--once", help="Run once at ISO datetime"),
    payload: str = typer.Option("{}", "--payload", help="Payload JSON"),
):
    """Add a schedule"""
    async def _add():
        comps = get_components()
        config = ScheduleConfig(
            name=name,
            target_type=target_type,
            target_id=UUID(target_id),
            payload=json.loads(payload),
            cron_expression=cron,
            interval_seconds=interval,
            run_once_at=once,
        )
        schedule_id = await comps["scheduler"].add_schedule(config)
        console.print(f"[green]Schedule created: {schedule_id}[/green]")

    asyncio.run(_add())


@app.command()
def schedule_list():
    """List schedules"""
    async def _list():
        comps = get_components()
        jobs = comps["scheduler"].get_jobs()

        table = Table(title="Schedules")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Next Run", style="yellow")
        table.add_column("Trigger", style="blue")

        for job in jobs:
            table.add_row(
                job["id"],
                job["name"],
                str(job["next_run_time"]) if job["next_run_time"] else "N/A",
                job["trigger"],
            )

        console.print(table)

    asyncio.run(_list())


@app.command()
def queue_stats():
    """Show queue statistics"""
    comps = get_components()
    stats = comps["queue_worker"].get_queue_stats()

    table = Table(title="Queue Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    for key, value in stats.items():
        table.add_row(key, str(value))

    console.print(table)


@app.command()
def prompt_list(slug: str = typer.Argument(..., help="Agent slug")):
    """List prompt templates for an agent"""
    async def _list():
        comps = get_components()
        agent = await comps["agent_registry"].get_agent(slug)
        if not agent:
            console.print(f"[red]Agent '{slug}' not found[/red]")
            return

        table = Table(title=f"Prompt Templates for {slug}")
        table.add_column("Name", style="cyan")
        table.add_column("Version", style="yellow")
        table.add_column("Default", style="green")
        table.add_column("Variables", style="blue")
        table.add_column("Preview", style="dim")

        for name, tmpl in agent.prompt_templates.items():
            preview = tmpl.template_text[:80] + "..." if len(tmpl.template_text) > 80 else tmpl.template_text
            table.add_row(
                name,
                str(tmpl.version),
                "✓" if tmpl.is_default else "✗",
                ", ".join(tmpl.variables) if tmpl.variables else "none",
                preview,
            )

        console.print(table)

    asyncio.run(_list())


@app.command()
def prompt_render(
    slug: str = typer.Argument(..., help="Agent slug"),
    template: str = typer.Argument(..., help="Template name"),
    input_data: str = typer.Option("{}", "--input", "-i", help="Input JSON"),
):
    """Render a prompt template"""
    async def _render():
        comps = get_components()
        agent = await comps["agent_registry"].get_agent(slug)
        if not agent:
            console.print(f"[red]Agent '{slug}' not found[/red]")
            return

        tmpl = agent.prompt_templates.get(template)
        if not tmpl:
            console.print(f"[red]Template '{template}' not found[/red]")
            return

        data = json.loads(input_data)
        rendered = comps["prompt_engine"].render(tmpl.template_text, data)

        if rendered.system_prompt:
            console.print(Panel(rendered.system_prompt, title="System Prompt", border_style="blue"))
        console.print(Panel(rendered.user_prompt, title="User Prompt", border_style="green"))

        if rendered.missing_variables:
            console.print(f"[yellow]Missing variables: {rendered.missing_variables}[/yellow]")

    asyncio.run(_render())


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host"),
    port: int = typer.Option(8000, "--port"),
    reload: bool = typer.Option(False, "--reload"),
):
    """Start the web server"""
    import uvicorn
    uvicorn.run("src.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()