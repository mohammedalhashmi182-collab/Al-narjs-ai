from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings, settings
from src.utils.logger import configure_logging
from src.utils.rate_limit import rate_limit_consult, rate_limit_login
from src.db.session import init_db, get_session_factory, close_db

configure_logging(settings.log_level, settings.log_json)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    session_factory = await get_session_factory()

    from src.core.agent_registry import AgentRegistry
    from src.core.model_provider import ModelProvider
    from src.core.prompt_engine import PromptEngine
    from src.core.context_manager import ContextManager
    from src.core.state_manager import StateManager
    from src.automation.workflow_engine import WorkflowEngine
    from src.automation.queue_worker import QueueWorker
    from src.automation.scheduler import AgentScheduler
    from src.automation.trigger_engine import TriggerEngine

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
    await close_db()


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

_LOCALE_COOKIE = "narjis_lang"
_SUPPORTED_LOCALES = ("ar", "en")


def _parse_request_cookies(scope: dict) -> dict:
    cookies: dict[str, str] = {}
    for name, value in scope.get("headers", []):
        if name.lower() == b"cookie":
            for part in value.decode("latin-1", "ignore").split(";"):
                if "=" in part:
                    k, v = part.strip().split("=", 1)
                    cookies[k.strip()] = v.strip()
    return cookies


def _detect_accepted_language(scope: dict) -> str:
    header = ""
    for name, value in scope.get("headers", []):
        if name.lower() == b"accept-language":
            header = value.decode("latin-1", "ignore")
            break
    weights = {"ar": 0.0, "en": 0.0}
    for part in header.split(","):
        lang = part.strip()
        weight = 1.0
        if ";" in lang:
            core, _, params = lang.partition(";")
            lang = core.strip()
            for param in params.split(";")[1:]:
                if param.strip().lower().startswith("q="):
                    try:
                        weight = float(param.strip()[2:])
                    except ValueError:
                        weight = 0.0
        base = lang.split("-")[0].lower()
        if base in _SUPPORTED_LOCALES:
            weights[base] = max(weights[base], weight)
    best = max((w, lang) for lang, w in weights.items())
    return best[1] if best[0] > 0 else "ar"


def _inject_locale_cookie(scope: dict, locale: str) -> None:
    cookies = _parse_request_cookies(scope)
    if cookies.get(_LOCALE_COOKIE) == locale:
        return
    cookies[_LOCALE_COOKIE] = locale
    header = "; ".join(f"{k}={v}" for k, v in cookies.items())
    headers = [(n, v) for n, v in scope.get("headers", []) if n.lower() != b"cookie"]
    headers.append((b"cookie", header.encode("latin-1")))
    scope["headers"] = headers


class LocaleMiddleware:
    """Serves /ar/ and /en/ URL prefixes with a persistent language cookie.

    /en/home serves the homepage rendered in English; /ar/home in Arabic.
    Unprefixed paths keep working and fall back to the cookie, then to the
    browser's Accept-Language header (English for anonymous international
    visitors, Arabic for Arabic browsers).
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path") or ""
        locale = None
        rest = path
        for lang in _SUPPORTED_LOCALES:
            if path == f"/{lang}" or path.startswith(f"/{lang}/"):
                locale = lang
                rest = path[len(lang) + 1:] or "/"
                break

        cookies = _parse_request_cookies(scope)
        if locale:
            scope["path"] = rest
            _inject_locale_cookie(scope, locale)
        elif not cookies.get(_LOCALE_COOKIE) and not path.startswith("/static"):
            _inject_locale_cookie(scope, _detect_accepted_language(scope))

        is_html = not (
            path.startswith("/static")
            or path.startswith("/api")
            or path in ("/robots.txt", "/sitemap.xml", "/favicon.ico")
            or "/health" in path
        )
        effective = locale or cookies.get(_LOCALE_COOKIE) or _detect_accepted_language(scope)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = [(n, v) for n, v in message.get("headers", [])]
                if is_html:
                    headers.append(
                        (
                            b"set-cookie",
                            (
                                f"{_LOCALE_COOKIE}={effective}; Max-Age=31536000; "
                                "Path=/; SameSite=Lax"
                            ).encode("latin-1"),
                        )
                    )
                if locale and message.get("status", 0) in (301, 302, 303, 307, 308):
                    for i, (n, v) in enumerate(headers):
                        if n.lower() == b"location" and v:
                            loc = v.decode("latin-1", "ignore")
                            if loc.startswith("/") and not (
                                loc.startswith(f"/{locale}/")
                                or loc == f"/{locale}"
                                or loc.startswith("/static")
                            ):
                                headers[i] = (n, f"/{locale}{loc}".encode("latin-1"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)

app.add_middleware(LocaleMiddleware)

try:
    app.mount("/static", StaticFiles(directory="src/web/static"), name="static")
except Exception:
    pass

templates = Jinja2Templates(directory="src/web/templates")


def _page_lang(request: Request) -> str:
    return request.cookies.get(_LOCALE_COOKIE, "ar")


templates.env.globals["page_lang"] = _page_lang


async def get_session() -> AsyncSession:
    async with app.state.session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


def require_owner_api(request: Request):
    from src.core.owner_auth import require_owner
    return require_owner(request)


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
    from src.core.owner_auth import check_owner
    if not check_owner(request):
        return RedirectResponse("/login")
    return templates.TemplateResponse(request, "dashboard.html")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    from src.core.owner_auth import check_owner
    if check_owner(request):
        return RedirectResponse("/")
    return templates.TemplateResponse(request, "login.html")


@app.post("/login", dependencies=[Depends(rate_limit_login)])
async def login_submit(request: Request):
    from starlette.responses import RedirectResponse
    from src.core.owner_auth import set_owner_cookie

    body = await request.json()
    password = body.get("password", "")
    if password == settings.owner_password:
        resp = RedirectResponse("/", status_code=303)
        return set_owner_cookie(resp)
    return {"error": "wrong_password"}


@app.get("/logout")
async def logout(request: Request):
    from starlette.responses import RedirectResponse
    from src.core.owner_auth import clear_owner_cookie
    resp = RedirectResponse("/home")
    return clear_owner_cookie(resp)


@app.get("/home", response_class=HTMLResponse)
async def landing_page(request: Request):
    return templates.TemplateResponse(request, "landing.html")


@app.get("/robots.txt", response_class=HTMLResponse)
async def robots_txt():
    from fastapi.responses import FileResponse
    return FileResponse("src/web/static/robots.txt", media_type="text/plain")


@app.get("/sitemap.xml", response_class=HTMLResponse)
async def sitemap_xml():
    from fastapi.responses import FileResponse
    return FileResponse("src/web/static/sitemap.xml", media_type="application/xml")


@app.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    return templates.TemplateResponse(request, "privacy.html")


@app.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    return templates.TemplateResponse(request, "terms.html")


@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request):
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/home#pricing")


@app.get("/portal", response_class=HTMLResponse)
async def client_portal_page(request: Request):
    return templates.TemplateResponse(request, "portal.html")


@app.get("/consult", response_class=HTMLResponse)
async def consult_page(request: Request):
    return templates.TemplateResponse(request, "consult.html")


@app.get("/agents", response_class=HTMLResponse)
async def agents_page(request: Request):
    from src.core.owner_auth import check_owner
    if not check_owner(request):
        return RedirectResponse("/login")
    return templates.TemplateResponse(request, "agents.html")


@app.get("/workflows", response_class=HTMLResponse)
async def workflows_page(request: Request):
    from src.core.owner_auth import check_owner
    if not check_owner(request):
        return RedirectResponse("/login")
    return templates.TemplateResponse(request, "workflows.html")


@app.get("/schedules", response_class=HTMLResponse)
async def schedules_page(request: Request):
    from src.core.owner_auth import check_owner
    if not check_owner(request):
        return RedirectResponse("/login")
    return templates.TemplateResponse(request, "schedules.html")


@app.get("/executions", response_class=HTMLResponse)
async def executions_page(request: Request):
    from src.core.owner_auth import check_owner
    if not check_owner(request):
        return RedirectResponse("/login")
    return templates.TemplateResponse(request, "executions.html")


@app.get("/api/agents")
async def list_agents(category: Optional[str] = None):
    from src.core.agent_registry import AgentCategory
    from src.services import catalog

    cat = AgentCategory(category) if category else None
    agents = await app.state.agent_registry.list_agents(cat)
    result = []
    for a in agents:
        emp = catalog.get_employee(a.slug) or {}
        item = {
            "slug": a.slug,
            "name": a.name,
            "description": a.description,
            "category": a.category,
            "is_active": a.is_active,
            "employee_no": emp.get("no", ""),
            "title_ar": emp.get("title_ar", a.name),
            "title_en": emp.get("title_en", a.name),
            "dept": emp.get("dept", ""),
            "intro_ar": emp.get("intro_ar", a.description),
            "intro_en": emp.get("intro_en", a.description),
        }
        result.append(item)
    return {"agents": result}


@app.get("/api/agents/{slug}", dependencies=[Depends(require_owner_api)])
async def get_agent(slug: str):
    agent = await app.state.agent_registry.get_agent(slug)
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent.model_dump()


@app.post("/api/agents/{slug}/run", dependencies=[Depends(require_owner_api)])
async def run_agent(slug: str, request: AgentRunRequest, http_request: Request):
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


@app.get("/api/workflows", dependencies=[Depends(require_owner_api)])
async def list_workflows(limit: int = 100, offset: int = 0):
    from src.models import Workflow as DBWorkflow
    from sqlalchemy import select, desc

    async with app.state.session_factory() as session:
        result = await session.execute(
            select(DBWorkflow).order_by(desc(DBWorkflow.created_at)).limit(limit).offset(offset)
        )
        workflows = result.scalars().all()
        return {"workflows": [
            {
                "id": str(w.id),
                "slug": w.slug,
                "name": w.name,
                "description": w.description,
                "version": w.version,
                "is_active": w.is_active,
                "created_at": w.created_at.isoformat() if w.created_at else None,
            } for w in workflows
        ]}


# ---------------- Client Portal (System 1: package -> dormant team -> wake -> interview) ----------------

@app.get("/api/portal/packages")
async def portal_packages():
    from src.services import catalog

    icons = {"social": "fa-hashtag", "ecommerce": "fa-store", "content": "fa-pen-nib", "growth": "fa-chart-line"}
    result = []
    for key, p in catalog.PACKAGES.items():
        team = catalog.get_team(key)
        result.append({
            "key": key,
            "name": p["name"],
            "name_en": p["name_en"],
            "price": p["price"],
            "tagline": p["tagline"],
            "tagline_en": p["tagline_en"],
            "team_size": len(team),
            "icon": icons.get(key, "fa-robot"),
        })
    return {"packages": result}


class PortalProjectCreate(BaseModel):
    client_name: str
    phone: str
    email: Optional[str] = None
    package: str


@app.post("/api/portal/projects")
async def portal_create_project(request: PortalProjectCreate):
    from src.services import catalog
    from src.models import ClientProject, ClientAgent

    if request.package not in catalog.PACKAGES:
        raise HTTPException(400, "Unknown package")

    async with app.state.session_factory() as session:
        project = ClientProject(
            client_name=request.client_name.strip(),
            phone=request.phone.strip(),
            email=request.email,
            package=request.package,
        )
        session.add(project)
        await session.flush()

        for slug in catalog.get_team(request.package):
            session.add(ClientAgent(project_id=project.id, slug=slug, status="dormant"))
        await session.commit()
        await session.refresh(project)

        return await portal_project_payload(session, project)


@app.get("/api/portal/projects/{project_id}")
async def portal_get_project(project_id: str):
    from src.models import ClientProject
    from sqlalchemy import select
    from uuid import UUID

    async with app.state.session_factory() as session:
        result = await session.execute(
            select(ClientProject).where(ClientProject.id == UUID(project_id))
        )
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(404, "Project not found")
        return await portal_project_payload(session, project)


class PortalAnswers(BaseModel):
    answers: dict


@app.post("/api/portal/projects/{project_id}/agents/{slug}/wake")
async def portal_wake_agent(project_id: str, slug: str):
    from src.services import catalog
    from src.models import ClientAgent, ClientProject
    from sqlalchemy import select
    from uuid import UUID

    async with app.state.session_factory() as session:
        result = await session.execute(
            select(ClientAgent).where(
                ClientAgent.project_id == UUID(project_id),
                ClientAgent.slug == slug,
            )
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(404, "Agent not part of this project")

        emp = catalog.get_employee(slug)
        defn = await app.state.agent_registry.get_agent(slug)
        if not emp or not defn:
            raise HTTPException(404, "Agent definition missing")

        agent.status = "interviewing"
        await session.commit()

        return {
            "agent": {
                "slug": slug,
                "no": emp["no"],
                "title_ar": emp["title_ar"],
                "title_en": emp["title_en"],
                "dept": emp["dept"],
                "intro_ar": emp["intro_ar"],
                "intro_en": emp["intro_en"],
                "recommendation": defn.description,
            },
            "questions": emp["questions"],
        }


@app.post("/api/portal/projects/{project_id}/agents/{slug}/run")
async def portal_run_agent(project_id: str, slug: str, request: PortalAnswers, http_request: Request):
    from src.models import ClientAgent, ClientProject
    from sqlalchemy import select
    from uuid import UUID

    async with app.state.session_factory() as session:
        result = await session.execute(
            select(ClientAgent).where(
                ClientAgent.project_id == UUID(project_id),
                ClientAgent.slug == slug,
            )
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(404, "Agent not part of this project")

        agent_def = await app.state.agent_registry.get_agent(slug)
        if not agent_def:
            raise HTTPException(404, "Agent definition missing")

        agent.answers = request.answers
        agent.status = "running"
        await session.commit()

        tmpl = agent_def.prompt_templates.get("default")
        if not tmpl:
            raise HTTPException(404, "Prompt template not found")

        rendered = app.state.prompt_engine.render(tmpl.template_text, request.answers)

        from src.core.model_provider import ModelRequest
        locale = http_request.cookies.get(_LOCALE_COOKIE, "ar")
        lang_instruction = (
            "Respond in Modern Standard Arabic (اللغة العربية الفصحى) unless the user"
            " explicitly asks otherwise. Structure your answer clearly with headings."
            if locale == "ar" else
            "Respond in clear, fluent business English. Use proper terminology and"
            " structure your answer clearly with headings."
        )
        model_request = ModelRequest(
            prompt=rendered.user_prompt,
            system_prompt=(rendered.system_prompt + "\n\n" + lang_instruction).strip(),
            temperature=agent_def.default_parameters.get("temperature", 0.7),
            max_tokens=agent_def.default_parameters.get("max_tokens", 2000),
        )
        response = await app.state.model_provider.complete(agent_def.default_model, model_request)

        agent.result = response.content
        agent.status = "done"
        await session.commit()

        return {"result": response.content, "status": "done"}


async def portal_project_payload(session, project) -> dict:
    from src.models import ClientAgent
    from sqlalchemy import select
    from src.services import catalog

    result = await session.execute(
        select(ClientAgent).where(ClientAgent.project_id == project.id).order_by(ClientAgent.created_at)
    )
    rows = result.scalars().all()

    names = {}
    for row in rows:
        defn = await app.state.agent_registry.get_agent(row.slug)
        if defn:
            names[row.slug] = defn.name

    team = catalog.team_with_identity([r.slug for r in rows], names)
    for t in team:
        row = next((x for x in rows if x.slug == t["slug"]), None)
        if row:
            t["status"] = row.status
            t["done"] = bool(row.result)

    pkg = catalog.PACKAGES.get(project.package, {})
    return {
        "project_id": str(project.id),
        "package": project.package,
        "package_name": pkg.get("name", project.package),
        "package_en": pkg.get("name_en", project.package),
        "client_name": project.client_name,
        "team": team,
    }


# ---------------- Smart Consultant (System 2: conversational solutions guide) ----------------

class ConsultMessage(BaseModel):
    role: str
    content: str


class ConsultRequest(BaseModel):
    messages: list[ConsultMessage]


@app.post("/api/consult", dependencies=[Depends(rate_limit_consult)])
async def consult_chat(request: ConsultRequest, http_request: Request):
    from src.core.model_provider import ModelRequest

    if not request.messages:
        raise HTTPException(400, "No messages")

    locale = http_request.cookies.get(_LOCALE_COOKIE, "ar")

    history = []
    for m in request.messages[-12:]:
        role = "user" if m.role in ("user", "client") else "assistant"
        history.append({"role": role, "content": m.content})

    from src.services import catalog as _catalog

    _pkgs = ", ".join(
        f"{p['name']} ({p['price']} SAR/mo)" for p in _catalog.PACKAGES.values()
    )
    _emps = ", ".join(
        e["title_ar"] for e in _catalog.EMPLOYEES.values()
    )
    system_prompt = (
        "You are the Smart Consultant (المستشار الذكي) of Al-Narjis AI (النرجس للذكاء الاصطناعي), "
        "a Riyadh-based AI agency offering a team of "
        f"({len(_catalog.EMPLOYEES)}) specialist AI agents across these packages: {_pkgs}.\n"
        "Your job: read the client's working style, environment and challenges from the conversation, "
        "then guide them to the best solutions and the most relevant agents. "
        "Rules:\n"
        "- Ask a focused clarifying question first if their situation is unclear (one question max).\n"
        "- Then propose a concrete plan, mention which named agents would help (job titles like "
        f"{_emps}), and suggest a package.\n"
        "- Be warm, practical and specific.\n"
        "- Respond in the language of the visitor"
        + (": Modern Standard Arabic (اللغة العربية الفصحى), with clear short sections and bullet points." if locale == "ar" else
           ": clear, fluent English, with clear short sections and bullet points.")
        + "\n- Keep replies concise (under ~250 words) unless asked for depth."
    )

    model_request = ModelRequest(
        prompt="\n".join(f"{m['role']}: {m['content']}" for m in history) + "\n\nassistant:",
        system_prompt=system_prompt,
        temperature=0.6,
        max_tokens=1200,
    )

    try:
        response = await app.state.model_provider.complete(
            "gemini:gemini-3.6-flash",
            model_request,
        )
        return {"reply": response.content.strip()}
    except Exception as e:
        from src.utils.logger import get_logger
        get_logger(__name__).error(f"Consult failed: {e}")
        return {
            "reply": (
                "عذراً، تعذر الاتصال بالمستشار حالياً. تفضل بزيارة /portal لتفعيل فريقك مباشرة."
                if locale == "ar" else
                "Sorry, we can't reach the consultant right now. Visit /portal to activate your team directly."
            )
        }


@app.post("/api/workflows/{slug}/run", dependencies=[Depends(require_owner_api)])
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


@app.get("/api/schedules", dependencies=[Depends(require_owner_api)])
async def list_schedules():
    jobs = app.state.scheduler.get_jobs()
    return {"schedules": jobs}


@app.post("/api/schedules", dependencies=[Depends(require_owner_api)])
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


@app.delete("/api/schedules/{schedule_id}", dependencies=[Depends(require_owner_api)])
async def delete_schedule(schedule_id: str):
    from uuid import UUID
    success = await app.state.scheduler.remove_schedule(UUID(schedule_id))
    if not success:
        raise HTTPException(404, "Schedule not found")
    return {"success": True}


@app.get("/api/queue/stats", dependencies=[Depends(require_owner_api)])
async def queue_stats():
    return app.state.queue_worker.get_queue_stats()


@app.post("/api/queue/enqueue", dependencies=[Depends(require_owner_api)])
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


@app.get("/api/executions", dependencies=[Depends(require_owner_api)])
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


@app.get("/api/executions/{execution_id}", dependencies=[Depends(require_owner_api)])
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


@app.post("/api/leads")
async def create_lead(request: Request):
    body = await request.json()
    from src.models import Lead

    async with app.state.session_factory() as session:
        lead = Lead(
            name=body.get("name", ""),
            phone=body.get("phone", ""),
            email=body.get("email"),
            package=body.get("package"),
            message=body.get("message"),
        )
        session.add(lead)
        await session.commit()
        await session.refresh(lead)

    email_sent = False
    if lead.email:
        from src.services import email_service
        email_sent = await email_service.send_welcome(lead.email, lead.name or "عميلنا العزيز")

    return {"success": True, "lead_id": str(lead.id), "email_sent": email_sent}


@app.post("/api/email/test", dependencies=[Depends(require_owner_api)])
async def email_test(request: Request):
    from src.services import email_service

    body = await request.json()
    to = body.get("to", "")
    if not to:
        raise HTTPException(400, "Provide 'to' email")

    if not email_service.is_configured():
        return {
            "configured": False,
            "message": "SMTP not configured. Set SMTP_USERNAME, SMTP_PASSWORD (Gmail App Password), SMTP_FROM in .env",
        }

    ok = await email_service.send_welcome(to, "اختبار التجربة")
    return {"configured": True, "sent": ok}


@app.get("/api/leads", dependencies=[Depends(require_owner_api)])
async def list_leads(limit: int = 100, offset: int = 0):
    from src.models import Lead
    from sqlalchemy import select, desc

    async with app.state.session_factory() as session:
        result = await session.execute(
            select(Lead).order_by(desc(Lead.created_at)).limit(limit).offset(offset)
        )
        leads = result.scalars().all()
        return {"leads": [
            {
                "id": str(l.id),
                "name": l.name,
                "phone": l.phone,
                "email": l.email,
                "package": l.package,
                "message": l.message,
                "status": l.status,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            } for l in leads
        ]}


@app.post("/api/leads/{lead_id}/status", dependencies=[Depends(require_owner_api)])
async def update_lead_status(lead_id: str, request: Request):
    from src.models import Lead
    from sqlalchemy import select
    from uuid import UUID

    body = await request.json()
    async with app.state.session_factory() as session:
        result = await session.execute(select(Lead).where(Lead.id == UUID(lead_id)))
        lead = result.scalar_one_or_none()
        if not lead:
            raise HTTPException(404, "Lead not found")
        lead.status = body.get("status", lead.status)
        await session.commit()
    return {"success": True}


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "0.1.0"}


# ---------------- Payments (Moyasar) ----------------

class PaymentCreateRequest(BaseModel):
    package: str
    method: str = "creditcard"
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None


def _request_locale(request: Request) -> str:
    return request.cookies.get("narjis_lang") or "ar"


@app.post("/api/payments")
async def create_payment(request: Request, body: PaymentCreateRequest):
    from src.services import payments as pm

    locale = _request_locale(request)
    include_vat = locale == "ar"
    async with app.state.session_factory() as session:
        payment = await pm.create_payment(
            session,
            body.package,
            body.customer_name,
            body.customer_phone,
            body.customer_email,
        )

        method = body.method.lower()

        if method == "paypal":
            charge = pm.total_with_vat(payment.amount) if include_vat else payment.amount
            try:
                base = str(request.base_url).rstrip("/")
                order = await pm.create_paypal_order(
                    session,
                    payment,
                    amount_halalas=charge,
                    return_url=f"{base}/payment/success?id={payment.id}",
                    cancel_url=f"{base}/payment/failure?id={payment.id}",
                )
                return {
                    "payment_id": str(payment.id),
                    "status": payment.status,
                    "gateway": "paypal",
                    "accepts_vat": include_vat,
                    "order_id": order["order_id"],
                    "redirect_url": order["approval_url"],
                    "amount": payment.amount,
                    "vat": pm.vat_amount(payment.amount) if include_vat else 0,
                    "total": charge,
                }
            except pm.PaymentError as e:
                payment.status = "invoice"
                await session.commit()
                return {
                    "payment_id": str(payment.id),
                    "status": "invoice",
                    "gateway": "invoice",
                    "message": str(e),
                    "amount": payment.amount,
                    "vat": 0,
                    "total": payment.amount,
                }

        # Moyasar if configured and method is a local gateway
        gateway_enabled = bool(settings.moyasar_api_secret)

        if gateway_enabled and method != "invoice":
            source_map = {
                "mada": pm.source_mada(),
                "stcpay": pm.source_stcpay(),
                "applepay": pm.source_applepay(),
                "creditcard": pm.source_credit_card(),
            }
            source = source_map.get(method, pm.source_credit_card())
            try:
                data = await pm.initiate_moyasar(session, payment, source)
                return {
                    "payment_id": str(payment.id),
                    "status": payment.status,
                    "gateway": "moyasar",
                    "gateway_payment_id": payment.gateway_payment_id,
                    "redirect_url": data.get("source", {}).get("transaction_url") if isinstance(data.get("source"), dict) else None,
                    "publishable_key": pm.get_publishable_key(),
                    "amount": payment.amount,
                    "vat": pm.vat_amount(payment.amount),
                    "total": pm.total_with_vat(payment.amount),
                }
            except pm.PaymentError as e:
                payment.status = "pending"
                await session.commit()
                return {
                    "payment_id": str(payment.id),
                    "status": "invoice",
                    "gateway": "invoice",
                    "message": str(e),
                    "amount": payment.amount,
                }

        # Invoice / bank-transfer fallback
        payment.status = "invoice"
        await session.commit()
        return {
            "payment_id": str(payment.id),
            "status": "invoice",
            "gateway": "invoice",
            "amount": payment.amount,
            "vat": 0,
            "total": payment.amount,
        }


@app.post("/api/payments/{payment_id}/capture")
async def capture_payment(payment_id: str, request: Request):
    from uuid import UUID
    from sqlalchemy import select
    from src.models import Payment
    from src.services import payments as pm

    body = await request.json()
    order_id = body.get("order_id", "")
    locale = _request_locale(request)

    async with app.state.session_factory() as session:
        result = await session.execute(select(Payment).where(Payment.id == UUID(payment_id)))
        payment = result.scalar_one_or_none()
        if not payment:
            raise HTTPException(404, "Payment not found")

        if payment.gateway == "paypal" and payment.gateway_payment_id:
            data = await pm.capture_paypal_order(payment.gateway_payment_id)
            status = data.get("status")
            if status == "COMPLETED":
                payment.status = "paid"
                payment.gateway_source = "paypal"
                await session.commit()
            elif status == "VOIDED":
                payment.status = "failed"
                await session.commit()
            else:
                payment.status = status.lower() if status else payment.status
                await session.commit()
        else:
            payment = (await session.execute(select(Payment).where(Payment.id == UUID(payment_id)))).scalar_one()
            if payment.status != "paid":
                await pm.verify_payment(session, payment.id)

    email_sent = False
    if payment.status == "paid" and payment.customer_email:
        from src.services import email_service
        email_sent = await email_service.send_invoice(
            payment,
            base_halalas=payment.amount,
            total_halalas=pm.total_with_vat(payment.amount),
            locale=locale,
        )

    return {
        "payment_id": str(payment.id),
        "status": payment.status,
        "gateway": payment.gateway,
        "amount": payment.amount,
        "vat": pm.vat_amount(payment.amount),
        "total": pm.total_with_vat(payment.amount),
        "invoice_url": f"/invoice/{payment.id}" if payment.status == "paid" else None,
        "email_sent": email_sent,
    }


@app.get("/invoice/{payment_id}")
async def invoice_page(request: Request, payment_id: str):
    from uuid import UUID
    from sqlalchemy import select
    from src.models import Payment
    from src.services import payments as pm

    locale = _request_locale(request)
    async with app.state.session_factory() as session:
        result = await session.execute(select(Payment).where(Payment.id == UUID(payment_id)))
        payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(404, "Invoice not found")

    template = "invoice.html" if locale == "ar" else "invoice_en.html"
    return templates.TemplateResponse(
        request,
        template,
        {
            "payment": payment,
            "base": payment.amount,
            "vat": pm.vat_amount(payment.amount),
            "total": pm.total_with_vat(payment.amount),
        },
    )


@app.get("/api/payments/{payment_id}")
async def get_payment(payment_id: str):
    from uuid import UUID
    from src.services import payments as pm

    async with app.state.session_factory() as session:
        try:
            payment = await pm.verify_payment(session, UUID(payment_id))
        except pm.PaymentError as e:
            raise HTTPException(404, str(e))

    return {
        "payment_id": str(payment.id),
        "status": payment.status,
        "amount": payment.amount,
        "currency": payment.currency,
        "package": payment.package,
        "description": payment.description,
        "gateway": payment.gateway,
        "gateway_payment_id": payment.gateway_payment_id,
        "vat": pm.vat_amount(payment.amount),
        "total": pm.total_with_vat(payment.amount),
    }


@app.get("/payment/success")
async def payment_success(request: Request, id: Optional[str] = None):
    return templates.TemplateResponse(request, "payment_status.html", {"result": "success", "payment_id": id})


@app.get("/payment/failure")
async def payment_failure(request: Request, id: Optional[str] = None):
    return templates.TemplateResponse(request, "payment_status.html", {"result": "failure", "payment_id": id})
