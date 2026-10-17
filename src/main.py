from __future__ import annotations

import asyncio
import os
import re
from functools import lru_cache
from pathlib import Path
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, Depends, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import MutableHeaders

from src.config.settings import get_settings, settings
from src.utils.logger import configure_logging, get_logger
from src.utils.rate_limit import (
    rate_limit_consult,
    rate_limit_ticket,
    rate_limit_login,
    rate_limit_transfer_report,
)
from src.db.session import close_db, ensure_pgvector, get_session_factory, init_db

configure_logging(settings.log_level, settings.log_json)

logger = get_logger(__name__)

_PULSE_TTL_SECONDS = 30.0


def _log_database_target() -> None:
    """Say out loud, at boot, where the data actually lives.

    Production ran for weeks on ``sqlite+aiosqlite:///ai_agent_system.db`` inside
    the container. The file is on the container's ephemeral filesystem, so every
    deploy and every restart silently destroyed every lead, client project and
    payment. Nothing failed, nothing warned: the site answered 200 the whole time,
    and three test payments created an hour apart were each gone after the next
    deploy.

    The check below changes no behaviour. It exists so the next occurrence is
    visible in the boot log instead of being discovered the way this one was.
    The database URL is never logged -- only the dialect and the target kind.
    """
    from src.db.session import engine

    dialect = engine.dialect.name
    database = str(engine.url.database or "")

    if dialect != "sqlite":
        logger.info("Database dialect: %s (persistent target)", dialect)
        return

    if database in ("", ":memory:"):
        logger.info("Database is SQLite in-memory: expected for tests and local runs.")
        return

    logger.warning(
        "Database is the SQLite file %s. Fine locally, unsafe on Render: the "
        "container filesystem is ephemeral, so every deploy and restart deletes "
        "all data. Point DATABASE_URL at a persistent store before taking real "
        "leads.",
        database,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await ensure_pgvector()  # RAG: pgvector when available, else in-process cosine
    _log_database_target()
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
    from src.automation.ceo_engine import CompanyBrain

    agent_registry = AgentRegistry(session_factory)
    # Fast startup: agents are served from YAML immediately; the DB upsert
    # (~35 agents, serialized) runs in the background so the port binds
    # quickly. Set SYNC_AGENTS_BLOCKING=true to restore the old behaviour.
    await agent_registry.prime_cache_from_yaml()
    from src.db.session import engine as _engine

    # SQLite (local/tests) keeps the blocking sync: its single-writer file lock
    # plus APScheduler's synchronous jobstore would deadlock the event loop.
    background_sync = _engine.dialect.name != "sqlite" and os.getenv(
        "SYNC_AGENTS_BLOCKING", "false").strip().lower() not in ("1", "true", "yes")
    if not background_sync:
        await agent_registry.sync_base_agents()

    model_provider = ModelProvider(settings)
    prompt_engine = PromptEngine()
    context_manager = ContextManager()
    state_manager = StateManager(session_factory)
    workflow_engine = WorkflowEngine(agent_registry, model_provider, state_manager, context_manager)
    queue_worker = QueueWorker(agent_registry, model_provider, state_manager, concurrency=settings.queue_worker_concurrency)
    scheduler = AgentScheduler(session_factory)
    trigger_engine = TriggerEngine(session_factory)
    company_brain = CompanyBrain(session_factory)

    from src.core.architecture.registry.agent_catalog import AgentCatalog
    from src.core.architecture.router.dynamic_router import DynamicRouter
    from src.core.architecture.validation.self_correction import OutputValidator, SelfCorrectionLoop

    agent_catalog = AgentCatalog()
    agent_catalog.load_dir()
    await agent_catalog.sync_from_registry(agent_registry)
    dynamic_router = DynamicRouter(agent_catalog, model_provider)
    self_correction_loop = SelfCorrectionLoop(
        dynamic_router, OutputValidator(), max_corrections=2
    )

    # Fast boot (Postgres): the scheduler starts empty and its ~25 DB-backed
    # jobs are registered in the background after the port binds. SQLite
    # (local/tests) keeps the blocking path (single-writer file lock).
    scheduler.offload_jobstore = background_sync
    await scheduler.start(load_schedules=not background_sync)
    await trigger_engine.start()
    await queue_worker.start()

    async def _register_scheduler_jobs(threaded: bool) -> None:
        started = time.monotonic()
        if threaded:
            await scheduler._load_schedules_from_db(threaded=True)
        steps = []
        from src.automation.ceo_engine import ensure_company_loops
        steps.append(ensure_company_loops)
        from src.services.renewals import ensure_renewal_schedule
        steps.append(ensure_renewal_schedule)
        from src.services.lead_pipeline import ensure_followup_schedule
        steps.append(ensure_followup_schedule)
        from src.services.ops_monitor import ensure_uptime_schedule
        steps.append(ensure_uptime_schedule)
        from src.services.weekly_reports import ensure_schedule as ensure_weekly_report_schedule
        steps.append(ensure_weekly_report_schedule)
        from src.services.live_demo import ensure_schedule as ensure_demo_purge_schedule
        steps.append(ensure_demo_purge_schedule)
        for step in steps:
            if threaded:
                try:
                    await step(scheduler)
                except asyncio.CancelledError:
                    raise
                except Exception:  # noqa: BLE001 - never crash the app
                    logger.exception("scheduler job registration step failed: %s", getattr(step, "__name__", step))
            else:
                await step(scheduler)
        logger.info("Scheduler jobs registered: %s jobs in %.1fs", scheduler.job_count(), time.monotonic() - started)

    scheduler_task = None
    if not background_sync:
        await _register_scheduler_jobs(threaded=False)
    try:
        from src.services import wa_templates
        async with session_factory() as _s:
            await wa_templates.seed_defaults(_s)
            await _s.commit()
    except Exception:  # pragma: no cover - seeding must never block startup
        logger.exception("WhatsApp template seed failed")
    try:
        from src.services.policies import seed_owner_faq
        async with session_factory() as _s:
            await seed_owner_faq(_s)
    except Exception:  # pragma: no cover - seeding must never block startup
        logger.exception("policy FAQ seed failed")

    app.state.agent_registry = agent_registry
    app.state.model_provider = model_provider
    app.state.prompt_engine = prompt_engine
    app.state.context_manager = context_manager
    app.state.state_manager = state_manager
    app.state.workflow_engine = workflow_engine
    app.state.queue_worker = queue_worker
    app.state.scheduler = scheduler
    app.state.trigger_engine = trigger_engine
    app.state.company_brain = company_brain
    app.state.session_factory = session_factory
    app.state.agent_catalog = agent_catalog
    app.state.dynamic_router = dynamic_router
    app.state.self_correction = self_correction_loop

    if background_sync:
        scheduler_task = asyncio.create_task(_register_scheduler_jobs(threaded=True), name="scheduler-jobs")
        # Started last, after every other startup DB write, so the port binds
        # right away and the upsert never contends with boot-time work.
        agent_registry.start_background_sync()

    async def _index_public_kb() -> None:
        """Build the public KB off the request path, retrying until it sticks."""
        from src.ai.rag import index_with_backoff

        await index_with_backoff(session_factory)

    kb_index_task = asyncio.create_task(_index_public_kb(), name="public-kb-index")

    yield

    if not kb_index_task.done():
        kb_index_task.cancel()
        try:
            await kb_index_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
    if scheduler_task is not None and not scheduler_task.done():
        scheduler_task.cancel()
        try:
            await scheduler_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
    await agent_registry.stop_background_sync()
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
    Unprefixed public pages 301 to the Arabic URL so the sitemap, canonical
    tags, and hreflang x-default all name the same host path. Private routes
    (the portal, login, APIs) stay unprefixed. ``/`` stays the owner dashboard.
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

        if locale is None and scope.get("method", "GET") in ("GET", "HEAD"):
            from src.services.seo import arabic_canonical_redirect

            target = arabic_canonical_redirect(path)
            if target:
                query = scope.get("query_string") or b""
                if query:
                    target = target + "?" + query.decode("latin-1", "ignore")
                payload = target.encode("latin-1")
                await send(
                    {
                        "type": "http.response.start",
                        "status": 301,
                        "headers": [
                            (b"location", payload),
                            (b"content-length", b"0"),
                            (b"cache-control", b"public, max-age=86400"),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": b""})
                return

        cookies = _parse_request_cookies(scope)
        if locale:
            scope["path"] = rest
            _inject_locale_cookie(scope, locale)
        elif not cookies.get(_LOCALE_COOKIE) and not path.startswith("/static"):
            _inject_locale_cookie(scope, _detect_accepted_language(scope))

        is_html = not (
            path.startswith("/static")
            or path.startswith("/brand/")
            or path.startswith("/api")
            or path.startswith("/webhooks")
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

from src.services.ops_monitor import OpsAlertMiddleware  # noqa: E402

app.add_middleware(OpsAlertMiddleware)

try:
    from src.core.architecture.middleware import TenantMiddleware

    app.add_middleware(TenantMiddleware)
except Exception:  # pragma: no cover - defensive; must never block startup
    pass

try:
    app.mount("/static", StaticFiles(directory="src/web/static"), name="static")
except Exception:
    pass

# Static assets are content-addressed by deploy, not by filename, so a browser
# that already has narjis.css must not re-download it on every page view.
# StaticFiles already sends ETag and Last-Modified and honours conditional
# requests; what was missing was an explicit Cache-Control, so a repeat visit
# still paid a full round trip per asset. Fingerprinted and non-fingerprinted
# assets are treated differently on purpose -- see _static_cache_control.
_STATIC_IMMUTABLE = {"max-age=31536000", "immutable"}
_STATIC_REVALIDATE = {"max-age=3600", "public", "must-revalidate"}
# CSS/JS that ship under a stable name and change on deploy. Cached for an hour
# with revalidation, so a deploy is picked up without a hard reload.
_STATIC_REVALIDATE_DIRS = ("/css/", "/js/")
_STATIC_REVALIDATE_SUFFIXES = (".css", ".js")


def _static_cache_control(path: str) -> str:
    """Choose a cache policy for one static asset.

    Long-lived, immutable assets (images, fonts, vendor bundles) are cached for a
    year. Hand-edited CSS/JS keep their filename across deploys, so caching them
    for a year would serve stale code after a release -- they get a bounded,
    revalidated cache instead. HTML is never touched here; that would pin a page
    to an old shell.
    """
    lowered = path.lower()
    if lowered.endswith(_STATIC_REVALIDATE_SUFFIXES):
        if any(marker in lowered for marker in _STATIC_REVALIDATE_DIRS):
            return ", ".join(sorted(_STATIC_REVALIDATE))
    return ", ".join(sorted(_STATIC_IMMUTABLE))


class StaticCacheMiddleware:
    """Attach Cache-Control to /static responses, and only to /static.

    Pure ASGI so the body is forwarded unchanged. ``BaseHTTPMiddleware`` buffers
    the body and sends it again under the original Content-Length; uvicorn then
    closes the connection if those lengths disagree.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""

        async def send_wrapper(message):
            if message["type"] == "http.response.start" and path.startswith("/static/"):
                headers = MutableHeaders(scope=message)
                headers.setdefault("Cache-Control", _static_cache_control(path))
            await send(message)

        await self.app(scope, receive, send_wrapper)


app.add_middleware(StaticCacheMiddleware)


# Security headers on every response. The CSP allow-list is exactly what the
# public pages load: Google Fonts, cdnjs (Font Awesome), the consent-gated Meta
# pixel and Google tag, and Moyasar/PayPal for checkout. Tailwind is served as
# compiled static CSS (no CDN). Inline scripts/styles are still used by the templates, so
# 'unsafe-inline' stays until they are moved to files. frame-ancestors 'none'
# (plus X-Frame-Options for old browsers) stops clickjacking.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com "
        "https://connect.facebook.net https://www.googletagmanager.com https://www.paypal.com https://*.paypal.com "
        "https://cdn.moyasar.com https://*.moyasar.com",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com "
        "https://cdn.moyasar.com https://*.moyasar.com",
        "font-src 'self' data: https://fonts.gstatic.com https://cdnjs.cloudflare.com",
        "img-src 'self' data: blob: https:",
        "connect-src 'self' https://www.facebook.com https://connect.facebook.net "
        "https://www.googletagmanager.com https://*.google-analytics.com https://*.analytics.google.com "
        "https://www.paypal.com https://*.paypal.com https://api.moyasar.com https://*.moyasar.com",
        "frame-src 'self' https://www.paypal.com https://*.paypal.com https://www.facebook.com "
        "https://*.moyasar.com",
        "form-action 'self' https://www.paypal.com https://*.paypal.com https://api.moyasar.com https://*.moyasar.com",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "object-src 'none'",
    ]
)
SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
}


class SecurityHeadersMiddleware:
    """Stamp the security headers onto the start message and forward the body unchanged."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS.items():
                    headers.setdefault(name, value)
            await send(message)

        await self.app(scope, receive, send_wrapper)


app.add_middleware(SecurityHeadersMiddleware)

from src.utils.request_log import RequestLogMiddleware  # noqa: E402

app.add_middleware(RequestLogMiddleware)


templates = Jinja2Templates(directory="src/web/templates")


def _page_lang(request: Request) -> str:
    return request.cookies.get(_LOCALE_COOKIE, "ar")


templates.env.globals["page_lang"] = _page_lang
from src.services.support import support_contact as _support_contact  # noqa: E402

templates.env.globals["support_contact"] = _support_contact
templates.env.globals["settings"] = get_settings()


def _promo_info() -> dict:
    from src.services.payments import promo_info
    return promo_info()


templates.env.globals["promo_info"] = _promo_info

from src.interfaces.sales_routes import router as sales_router  # noqa: E402

app.include_router(sales_router)

from src.interfaces.company_routes import router as company_router  # noqa: E402

app.include_router(company_router)

# Telegram is the primary channel. The WhatsApp Cloud API is registered as a
# second, owner-enabled channel (reinstated on request): it shares the same CRM
# and intent engine, and stays inert until WHATSAPP_TOKEN + WHATSAPP_PHONE_ID
# hold a valid Meta credential.
from src.interfaces.telegram_routes import router as telegram_router  # noqa: E402

app.include_router(telegram_router)

from src.interfaces.whatsapp_routes import router as whatsapp_router  # noqa: E402

app.include_router(whatsapp_router)

# Botpress is a third channel: it only carries closed sales from the social
# media agent into the CRM, the CEO brain and the queue. It is signed with its
# own secret and inert until BOTPRESS_WEBHOOK_SECRET is set.
from src.interfaces.botpress_routes import router as botpress_router  # noqa: E402

app.include_router(botpress_router)

# Owner-gated smart replies, lead pipeline, social drafts + the Messenger webhook.
from src.interfaces.automation_routes import router as automation_router  # noqa: E402

app.include_router(automation_router)

from src.interfaces.portal_routes import router as portal_router  # noqa: E402

app.include_router(portal_router)

# Agent tools: web search, CSV/XLSX uploads, Salla/Zid read-only, knowledge base.
from src.interfaces.agent_tools_routes import router as agent_tools_router  # noqa: E402

app.include_router(agent_tools_router)

from src.interfaces.ops_routes import api as ops_api, router as ops_router  # noqa: E402

app.include_router(ops_router)
app.include_router(ops_api)

# LLM router + pgvector RAG: POST /api/ai/ask (fast/deep routing, review, handoff).
from src.interfaces.ai_routes import router as ai_ask_router  # noqa: E402

app.include_router(ai_ask_router)


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


async def _record_agent_run(
    slug: str,
    status: str,
    started,
    error_type: Optional[str],
    latency_ms: Optional[int],
) -> None:
    """Record an agent run so the console can answer "is this one working?".

    Without this the dashboard's per-agent columns stay at zero forever, because
    a direct agent run never touched the execution table. A failure to record
    must never fail the run itself, so every error here is swallowed.
    """
    try:
        from datetime import datetime, timezone

        from src.models import WorkflowExecution
        from src.utils.logger import get_logger

        async with app.state.session_factory() as session:
            session.add(
                WorkflowExecution(
                    workflow_id=slug,
                    trigger_type="agent",
                    status=status,
                    started_at=started,
                    completed_at=datetime.now(timezone.utc),
                    error=error_type,
                    context={"latency_ms": latency_ms} if latency_ms is not None else {},
                )
            )
            await session.commit()
    except Exception:
        pass


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
        # permanent: the public root is /home for every visitor
        # no-store so a browser never caches the 301 for the owner, who gets
        # the dashboard on "/" once signed in
        return RedirectResponse("/ar/home", status_code=301, headers={"Cache-Control": "no-store"})
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

    try:
        body = await request.json()
    except Exception:
        body = None
    if not isinstance(body, dict):
        return JSONResponse({"error": "wrong_password"}, status_code=400)
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


@app.get("/owner", response_class=HTMLResponse)
async def owner_entry(request: Request):
    from src.core.owner_auth import check_owner
    if not check_owner(request):
        return RedirectResponse("/login")
    return RedirectResponse("/")


async def _pricing_context() -> dict:
    """Plans, enterprise, add-ons and setup fees: shared by /home and /pricing."""
    from src.services import catalog
    from src.services import payments as _pm

    return {
        "packages": catalog.PACKAGES,
        # CEO-advisor rebrand: tiers in display order with VAT-inclusive totals
        "plans": [
            {
                "key": key,
                **catalog.PACKAGES[key],
                "total_halalas": _pm.total_with_vat(catalog.PACKAGES[key]["amount"]),
                "annual_halalas": catalog.plan_amount(key, "annual"),
                "annual_total_halalas": _pm.total_with_vat(catalog.plan_amount(key, "annual")),
                "annual_price": str(catalog.plan_amount(key, "annual") // 100),
                "recommended": key == catalog.RECOMMENDED_PACKAGE,
            }
            for key in catalog.PACKAGE_ORDER
        ],
        "addon": catalog.ADDON_AGENT,
        "usage_addons": catalog.USAGE_ADDONS,
        "enterprise": None,
        "founding_offer": catalog.FOUNDING_OFFER if catalog.founding_enabled() else None,
        "founding": await _founding_status_safe() if catalog.founding_enabled() else None,
        "setup_guarantee": catalog.SETUP_GUARANTEE,
    }


@app.get("/home", response_class=HTMLResponse)
async def landing_page(request: Request):
    from src.services import catalog, transfer
    from src.services import public_services
    from src.services import testimonials as _testimonials
    from src.services import payments as _pm
    employees = list(catalog.EMPLOYEES.values())
    agent_count = len(employees)
    registry = getattr(app.state, "agent_registry", None)
    if registry is not None:
        try:
            registered = await registry.list_agents()
            if registered:
                agent_count = len(registered)
        except Exception:  # DB unavailable -> catalog stays the source of truth
            pass
    return templates.TemplateResponse(
        request,
        "landing.html",
        {
            "agent_count": agent_count,
            "agents_preview": employees[:3],
            # divisions first: the public site never advertises a raw roster size
            "divisions": catalog.DIVISIONS,
            "division_count": catalog.DIVISION_COUNT,
            "catalog_employees": catalog.EMPLOYEES,
            # published contact channels: WhatsApp renders above Telegram, and the
            # number must be the same one the invoices print
            "contact": transfer.contact_channels(),
            # one leader above a sample of the team, for the orchestrator visual
            "orch_team": [
                {"slug": slug, **emp} for slug, emp in list(catalog.EMPLOYEES.items())[:6]
            ],
            **(await _pricing_context()),
            "testimonials": _testimonials.load(),
            "services": public_services.SERVICES,
            "internal_tests": __import__("src.services.internal_tests", fromlist=["load"]).load(),
            "ceo": catalog.EMPLOYEES[catalog.CEO_SLUG],
            "contact_prefilled": transfer.contact_channels(
                "مرحباً، أريد التحدث مع الرئيس التنفيذي الذكي عن مشروعي"
            ),
            "telegram_handle": transfer.telegram_contact_handle(),
        },
    )


@app.get("/api/pulse")
async def public_pulse():
    """Live, aggregate-only numbers for the public site.

    Truthfulness rules for this endpoint:
      * only COUNT(*) style aggregates are ever returned, never rows or names;
      * any metric that cannot be read is returned as ``None`` so the page can
        show capability copy instead of an invented number;
      * counts are cached briefly so a public page view cannot hammer the DB.
    """
    from src.db.session import get_session_factory
    from src.services import catalog
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    now = time.monotonic()
    cached = getattr(app.state, "public_pulse_cache", None)
    if cached and cached["at"] > now - _PULSE_TTL_SECONDS:
        return cached["payload"]

    session_factory = await get_session_factory()

    async def count(table: str) -> int | None:
        # table names are literals from this module, never user input
        async with session_factory() as session:
            result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
            return int(result.scalar_one())

    payload = {
        "divisions": catalog.DIVISION_COUNT,
        "agents": len(catalog.EMPLOYEES),
        "plans": len(catalog.PACKAGES),
        "leads_received": None,
        "projects": None,
    }

    try:
        payload["leads_received"] = await count("acquisition_leads")
    except Exception:  # a public page must never 500 on a database problem
        logger.warning("pulse: leads_received unavailable", exc_info=True)
    try:
        payload["projects"] = await count("client_projects")
    except Exception:
        logger.warning("pulse: projects unavailable", exc_info=True)

    app.state.public_pulse_cache = {"at": now, "payload": payload}
    return payload


@app.get("/robots.txt", response_class=HTMLResponse)
async def robots_txt():
    from fastapi.responses import PlainTextResponse

    from src.services.seo import build_robots

    return PlainTextResponse(build_robots(), media_type="text/plain")


@app.get("/sitemap.xml", response_class=HTMLResponse)
async def sitemap_xml():
    from fastapi.responses import Response

    from src.services import blog_articles_1, catalog, seo

    xml = seo.build_sitemap(list(catalog.EMPLOYEES.keys()), blog_articles_1.ARTICLES)
    return Response(content=xml, media_type="application/xml")


@app.get("/ai-agent/{slug}", response_class=HTMLResponse)
async def public_agent_page(slug: str, request: Request):
    """One indexable page per agent — the SEO surface for the team."""
    from src.services import catalog

    employee = catalog.get_employee(slug)
    if not employee:
        raise HTTPException(404, "Agent not found")

    same_dept = [
        emp
        for key, emp in catalog.EMPLOYEES.items()
        if key != slug and emp.get("dept") == employee.get("dept")
    ]
    related = same_dept[:6]
    if len(related) < 6:
        for key, emp in catalog.EMPLOYEES.items():
            if key != slug and emp not in related:
                related.append(emp)
            if len(related) >= 6:
                break

    recommended_pkg = catalog.PACKAGE_ORDER[0]
    for pkg_key, team in catalog.PACKAGE_TEAMS.items():
        if slug in team:
            recommended_pkg = pkg_key
            break

    return templates.TemplateResponse(
        request,
        "agent_public.html",
        {
            "agent": employee,
            "related": related,
            "recommended_pkg": recommended_pkg,
            "outputs": employee.get("outputs", []),
        },
    )


@app.get("/blog", response_class=HTMLResponse)
async def blog_index_page(request: Request):
    from src.services import blog_articles_1

    return templates.TemplateResponse(
        request, "blog_index.html", {"articles": blog_articles_1.ARTICLES}
    )


@app.get("/blog/{slug}", response_class=HTMLResponse)
async def blog_post_page(slug: str, request: Request):
    from src.services import blog_articles_1, public_services

    articles = blog_articles_1.ARTICLES
    article = next((a for a in articles if a["slug"] == slug), None)
    if not article:
        raise HTTPException(404, "Article not found")
    more = [a for a in articles if a["slug"] != slug][:4]
    return templates.TemplateResponse(
        request,
        "blog_post.html",
        {
            "article": article,
            "more": more,
            "related_services": public_services.links_for_article(slug),
        },
    )


@app.get("/services/{slug}", response_class=HTMLResponse)
async def service_page(slug: str, request: Request):
    from src.services import public_services

    service = public_services.get_service(slug)
    if service is None:
        raise HTTPException(404, "Service not found")
    lang = _page_lang(request)
    return templates.TemplateResponse(
        request,
        "service.html",
        {
            "ar": lang == "ar",
            "service": service,
            "related": public_services.related_services(service),
            "service_jsonld": public_services.service_jsonld(service, lang),
        },
    )


@app.get("/ai-agents-saudi-businesses", response_class=HTMLResponse)
async def intent_page(request: Request):
    """Search-intent landing page: 'AI agents for Saudi businesses'."""
    from src.services import catalog

    teams = []
    for key, pkg in catalog.PACKAGES.items():
        members = []
        for slug in catalog.PACKAGE_TEAMS.get(key, []):
            emp = catalog.get_employee(slug)
            if emp:
                members.append({"slug": slug, **emp})
        teams.append(
            {
                "key": key,
                "name": pkg["name"],
                "name_en": pkg["name_en"],
                "price": pkg["price"],
                "tagline": pkg["tagline"],
                "tagline_en": pkg["tagline_en"],
                "members": members,
            }
        )
    return templates.TemplateResponse(
        request,
        "intent_agents.html",
        {
            "teams": teams,
            "agent_count": len(catalog.EMPLOYEES),
            "agents": [
                {"slug": slug, **emp} for slug, emp in catalog.EMPLOYEES.items()
            ],
        },
    )


@app.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    return templates.TemplateResponse(request, "privacy.html")


@app.get("/data-deletion", response_class=HTMLResponse)
async def data_deletion_page(request: Request):
    return templates.TemplateResponse(request, "data_deletion.html")


@app.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    return templates.TemplateResponse(request, "terms.html")


@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request):
    """A real pricing page (SEO/ads landing): plans, enterprise, setup fees, add-ons."""
    return templates.TemplateResponse(
        request,
        "pricing.html",
        {**(await _pricing_context()), "ar": _page_lang(request) == "ar"},
    )


@app.get("/refund-policy", response_class=HTMLResponse)
async def refund_policy_page(request: Request):
    from src.services import catalog, policies

    return templates.TemplateResponse(
        request,
        "refund_policy.html",
        {
            "ar": _page_lang(request) == "ar",
            "refund_consent_ar": policies.REFUND_CONSENT_AR,
            "refund_consent_en": policies.REFUND_CONSENT_EN,
            "setup_guarantee": catalog.SETUP_GUARANTEE,
        },
    )


@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    from src.services import testimonials as _testimonials

    return templates.TemplateResponse(
        request,
        "about.html",
        {"ar": _page_lang(request) == "ar", "testimonials": _testimonials.load()},
    )


_BRAND_DIR = Path(__file__).resolve().parent / "web" / "brand"
_BRAND_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".ico": "image/x-icon"}


@lru_cache(maxsize=16)
def _brand_bytes(name: str) -> bytes | None:
    """Raster brand assets are stored base64-encoded (text) in src/web/brand."""
    import base64

    path = _BRAND_DIR / f"{name}.b64"
    if "/" in name or not path.is_file():
        return None
    return base64.b64decode(path.read_text(encoding="ascii"))


def _brand_response(name: str):
    data = _brand_bytes(name)
    if data is None:
        raise HTTPException(status_code=404)
    return Response(
        content=data,
        media_type=_BRAND_TYPES.get(Path(name).suffix, "application/octet-stream"),
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return _brand_response("favicon.ico")


@app.get("/brand/{name}", include_in_schema=False)
async def brand_asset(name: str):
    return _brand_response(name)


@app.get("/packages/{package_key}", response_class=HTMLResponse)
async def package_detail_page(package_key: str, request: Request):
    from src.services.demo_content import get_package_detail

    detail = get_package_detail(package_key)
    if not detail:
        raise HTTPException(404, "Package not found")
    return templates.TemplateResponse(request, "package.html", {"detail": detail})


@app.get("/portal", response_class=HTMLResponse)
async def client_portal_page(request: Request):
    from src.services import transfer

    # The checkout renders a WhatsApp escape hatch, so the number comes from the
    # same published contact source as the invoice rather than a second copy.
    from src.services import payments as _pm

    return templates.TemplateResponse(
        request, "portal.html", {
            "contact": transfer.contact_channels(),
            "bank_transfer_enabled": _pm.customer_bank_transfer_enabled(),
            "paypal_customer_enabled": _pm.customer_paypal_enabled(),
        },
    )


@app.get("/consult", response_class=HTMLResponse)
async def consult_page(request: Request):
    return templates.TemplateResponse(request, "consult.html")


@app.get("/guide", response_class=HTMLResponse)
async def guide_page(request: Request):
    return templates.TemplateResponse(request, "guide.html")


@app.get("/early-access", response_class=HTMLResponse)
async def early_access_page(request: Request):
    from src.services import catalog

    agent_count = len(catalog.EMPLOYEES)
    registry = getattr(app.state, "agent_registry", None)
    if registry is not None:
        try:
            registered = await registry.list_agents()
            if registered:
                agent_count = len(registered)
        except Exception:  # DB unavailable -> catalog stays the source of truth
            pass
    return templates.TemplateResponse(
        request,
        "early_access.html",
        {
            "agent_count": agent_count,
            "packages": catalog.PACKAGES,
        },
    )


@app.get("/agents", response_class=HTMLResponse)
async def agents_page(request: Request):
    from src.core.owner_auth import check_owner
    if not check_owner(request):
        return RedirectResponse("/login")
    return templates.TemplateResponse(request, "agents.html", {"active": "agents"})


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


@app.get("/company", response_class=HTMLResponse)
async def company_page(request: Request):
    from src.core.owner_auth import check_owner
    if not check_owner(request):
        return RedirectResponse("/login")
    return templates.TemplateResponse(request, "company.html", {"active": "company"})


# Fields the owner console needs but that must never reach an anonymous
# caller: model routing, which agents are internal machinery, employee
# numbers, and the interview script.
_AGENT_INTERNAL_FIELDS = ("default_model", "is_system", "employee_no", "questions")


@app.get("/api/agents")
async def list_agents(request: Request, category: Optional[str] = None):
    from src.core.agent_registry import AgentCategory
    from src.core.owner_auth import check_owner
    from src.services import catalog

    is_owner = check_owner(request)
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
            "title_ar": emp.get("title_ar", a.name),
            "title_en": emp.get("title_en", a.name),
            "dept": emp.get("dept", ""),
            "intro_ar": emp.get("intro_ar", a.description),
            "intro_en": emp.get("intro_en", a.description),
        }
        if is_owner:
            item.update(
                {
                    "default_model": a.default_model,
                    "is_system": a.is_system,
                    "employee_no": emp.get("no", ""),
                    "questions": emp.get("questions", []),
                }
            )
        result.append(item)
    return {"agents": result}


# A provider that is out of credit or holding a revoked key makes every agent
# look alive in the registry while none of them can answer. One cached
# round-trip per provider is what separates "registered" from "actually works".
_PROVIDER_PROBE_CACHE: dict = {}
_PROVIDER_PROBE_TTL = 120.0


async def _probe_provider(provider: str, model_spec: str) -> dict:
    cached = _PROVIDER_PROBE_CACHE.get(provider)
    now = time.monotonic()
    if cached and now - cached[0] < _PROVIDER_PROBE_TTL:
        return cached[1]

    outcome = {"provider": provider, "model": model_spec, "reachable": False, "detail": ""}
    try:
        from src.core.model_provider import ModelRequest

        started = time.monotonic()
        await app.state.model_provider.complete(
            model_spec, ModelRequest(prompt="ping", system_prompt="", max_tokens=1)
        )
        outcome["reachable"] = True
        outcome["latency_ms"] = int((time.monotonic() - started) * 1000)
    except Exception as e:
        # Type only: the message is where a provider may echo its own key.
        outcome["detail"] = type(e).__name__

    _PROVIDER_PROBE_CACHE[provider] = (now, outcome)
    return outcome


@app.get("/api/owner/agents/status", dependencies=[Depends(require_owner_api)])
async def owner_agents_status(limit: int = 500):
    """What the owner actually asked for: is each agent working, or not."""
    import asyncio

    from sqlalchemy import desc, select

    from src.core.model_provider import ModelSpec
    from src.models import WorkflowExecution
    from src.services import catalog

    agents = await app.state.agent_registry.list_agents()

    async with app.state.session_factory() as session:
        rows = (
            await session.execute(
                select(WorkflowExecution)
                .order_by(desc(WorkflowExecution.created_at))
                .limit(limit)
            )
        ).scalars().all()

    history: dict = {}
    for e in rows:
        h = history.setdefault(
            e.workflow_id, {"runs": 0, "failures": 0, "last_status": None, "last_at": None}
        )
        h["runs"] += 1
        if e.status == "failed":
            h["failures"] += 1
        if e.created_at and (h["last_at"] is None or e.created_at > h["last_at"]):
            h["last_at"] = e.created_at
            h["last_status"] = e.status

    providers: dict = {}
    for a in agents:
        spec = getattr(a, "default_model", "") or ""
        try:
            providers.setdefault(ModelSpec.parse(spec).provider.value, spec)
        except Exception:
            continue

    probes = await asyncio.gather(
        *[_probe_provider(p, s) for p, s in providers.items()]
    )
    reach = {p["provider"]: p for p in probes}

    items = []
    for a in agents:
        emp = catalog.get_employee(a.slug) or {}
        h = history.get(a.slug, {})
        spec = getattr(a, "default_model", "") or ""
        try:
            provider = ModelSpec.parse(spec).provider.value
        except Exception:
            provider = ""

        runs, failures = h.get("runs", 0), h.get("failures", 0)
        if failures and runs and failures >= runs:
            state = "failing"
        elif runs:
            state = "healthy"
        else:
            state = "idle"

        items.append(
            {
                "slug": a.slug,
                "name": a.name,
                "title_ar": emp.get("title_ar", a.name),
                "dept": emp.get("dept", ""),
                "is_system": getattr(a, "is_system", False),
                "default_model": spec,
                "provider": provider,
                "provider_reachable": bool(reach.get(provider, {}).get("reachable")),
                "state": state,
                "runs": runs,
                "failures": failures,
                "last_status": h.get("last_status"),
                "last_at": h["last_at"].isoformat() if h.get("last_at") else None,
            }
        )

    return {
        "summary": {
            "total": len(items),
            "healthy": sum(1 for i in items if i["state"] == "healthy"),
            "failing": sum(1 for i in items if i["state"] == "failing"),
            "idle": sum(1 for i in items if i["state"] == "idle"),
            "providers_total": len(probes),
            "providers_reachable": sum(1 for p in probes if p.get("reachable")),
        },
        "providers": list(probes),
        "agents": items,
    }


@app.get("/api/agents/{slug}", dependencies=[Depends(require_owner_api)])
async def get_agent(slug: str):
    agent = await app.state.agent_registry.get_agent(slug)
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent.model_dump()


class AgentUpsertRequest(BaseModel):
    name: str
    slug: Optional[str] = None
    description: str = ""
    category: str = "general"
    default_model: Optional[str] = None
    default_parameters: dict = {}


@app.post("/api/agents", dependencies=[Depends(require_owner_api)])
async def create_agent(request: AgentUpsertRequest):
    from src.core.agent_registry import AgentCategory, AgentDefinition, PromptTemplate

    slug = (request.slug or request.name.strip()).lower().replace(" ", "-")
    if await app.state.agent_registry.get_agent(slug):
        raise HTTPException(409, "Agent with this slug already exists")
    cat = _agent_category(request.category)
    templates = {
        "default": PromptTemplate(
            name="default",
            version=1,
            template_text=(
                "You are {name}, part of the Al-Narjis AI team. "
                "Concentrate on the single assignment below and deliver direct, practical value.\n\n"
                "Business context:\n{{ context or 'No context provided.' }}\n\n"
                "Assignment:\n{{ task or 'Help with your specialty.' }}"
            ),
            variables=["context", "task"],
            is_default=True,
        )
    }
    defn = AgentDefinition(
        slug=slug,
        name=request.name.strip() or slug,
        description=request.description or "",
        category=cat,
        default_model=(request.default_model or get_settings().moonshot_default_model),
        default_parameters=request.default_parameters or {},
        prompt_templates=templates,
    )
    agent = await app.state.agent_registry.upsert_agent(defn)
    return agent.model_dump()


@app.put("/api/agents/{slug}", dependencies=[Depends(require_owner_api)])
async def update_agent(slug: str, request: AgentUpsertRequest):
    from src.core.agent_registry import AgentDefinition, AgentCategory

    existing = await app.state.agent_registry.get_agent(slug)
    if not existing:
        raise HTTPException(404, "Agent not found")
    new_slug = (request.slug or slug).strip() if request.slug else slug
    if new_slug != slug and await app.state.agent_registry.get_agent(new_slug):
        raise HTTPException(409, "Agent with this slug already exists")
    defn = AgentDefinition(
        slug=new_slug,
        name=request.name.strip() or existing.name,
        description=request.description if request.description is not None else existing.description,
        category=_agent_category(request.category) if request.category else existing.category,
        default_model=request.default_model or existing.default_model,
        default_parameters=request.default_parameters or existing.default_parameters,
        prompt_templates=existing.prompt_templates,
        is_system=existing.is_system,
        created_by=existing.created_by,
    )
    agent = await app.state.agent_registry.upsert_agent(defn)
    if new_slug != slug:
        await app.state.agent_registry.delete_agent(slug)
    return agent.model_dump()


@app.delete("/api/agents/{slug}", dependencies=[Depends(require_owner_api)])
async def delete_agent(slug: str):
    ok = await app.state.agent_registry.delete_agent(slug)
    if not ok:
        raise HTTPException(404, "Agent not found")
    return {"success": True}


def _agent_category(value: str):
    from src.core.agent_registry import AgentCategory
    try:
        return AgentCategory(value.lower())
    except ValueError:
        raise HTTPException(400, f"Unknown category: {value}")


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

    from datetime import datetime, timezone

    started = datetime.now(timezone.utc)
    try:
        response = await app.state.model_provider.complete(agent.default_model, model_request)
    except Exception as e:
        await _record_agent_run(
            agent.slug, "failed", started, type(e).__name__, None
        )
        raise

    await _record_agent_run(
        agent.slug, "completed", started, None, response.latency_ms
    )
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
                "definition": w.definition,
                "version": w.version,
                "is_active": w.is_active,
                "created_at": w.created_at.isoformat() if w.created_at else None,
            } for w in workflows
        ]}


class WorkflowUpsertRequest(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    definition: dict


def _workflow_json(wf) -> dict:
    return {
        "id": str(wf.id),
        "slug": wf.slug,
        "name": wf.name,
        "description": wf.description,
        "definition": wf.definition,
        "version": wf.version,
        "is_active": wf.is_active,
        "created_at": wf.created_at.isoformat() if wf.created_at else None,
    }


async def _get_workflow(session, slug):
    from src.models import Workflow as DBWorkflow
    from sqlalchemy import select
    return (await session.execute(select(DBWorkflow).where(DBWorkflow.slug == slug))).scalar_one_or_none()


@app.post("/api/workflows", dependencies=[Depends(require_owner_api)])
async def create_workflow(request: WorkflowUpsertRequest):
    from src.models import Workflow as DBWorkflow

    slug = request.slug.strip()
    async with app.state.session_factory() as session:
        if await _get_workflow(session, slug):
            raise HTTPException(409, "Workflow with this slug already exists")
        wf = DBWorkflow(
            slug=slug,
            name=request.name.strip(),
            description=request.description,
            definition=request.definition,
            version=1,
            is_active=True,
        )
        session.add(wf)
        await session.commit()
        await session.refresh(wf)
    return _workflow_json(wf)


@app.get("/api/workflows/{slug}", dependencies=[Depends(require_owner_api)])
async def get_workflow(slug: str):
    async with app.state.session_factory() as session:
        wf = await _get_workflow(session, slug)
    if not wf:
        raise HTTPException(404, "Workflow not found")
    return _workflow_json(wf)


@app.put("/api/workflows/{slug}", dependencies=[Depends(require_owner_api)])
async def update_workflow(slug: str, request: WorkflowUpsertRequest):
    new_slug = request.slug.strip()
    async with app.state.session_factory() as session:
        wf = await _get_workflow(session, slug)
        if not wf:
            raise HTTPException(404, "Workflow not found")
        if new_slug != slug and await _get_workflow(session, new_slug):
            raise HTTPException(409, "Workflow with this slug already exists")
        if request.definition != wf.definition:
            wf.version += 1
        wf.slug = new_slug
        wf.name = request.name.strip()
        wf.description = request.description
        wf.definition = request.definition
        await session.commit()
        await session.refresh(wf)
    return _workflow_json(wf)


@app.delete("/api/workflows/{slug}", dependencies=[Depends(require_owner_api)])
async def delete_workflow(slug: str):
    async with app.state.session_factory() as session:
        wf = await _get_workflow(session, slug)
        if not wf:
            raise HTTPException(404, "Workflow not found")
        await session.delete(wf)
        await session.commit()
    return {"success": True}


# ---------------- Client Portal (System 1: package -> dormant team -> wake -> interview) ----------------

@app.get("/api/portal/packages")
async def portal_packages():
    from src.services import catalog

    icons = {"bidaya": "fa-comments", "numuw": "fa-seedling", "sharikat": "fa-building"}
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
            "team_size": p.get("display_agents") or p["agent_count"],
            "agents": p.get("display_agents") or p["agent_count"],
            "icon": icons.get(key, "fa-robot"),
            "amount": p["amount"],
            "annual_amount": catalog.plan_amount(key, "annual"),
            "setup_fee": p["setup_fee"],
            "limits": p["limits"],
            "recommended": key == catalog.RECOMMENDED_PACKAGE,
            "features": p["scope"],
            "features_en": p["scope_en"],
            "coming": p.get("coming", []),
            "coming_en": p.get("coming_en", []),
        })
    return {
        "packages": result,
        "enterprise": None,
        "addon": {**catalog.ADDON_AGENT, "max": catalog.MAX_ADDON_AGENTS},
        "usage_addons": catalog.USAGE_ADDONS,
        **({"founding_offer": catalog.FOUNDING_OFFER, "founding": await _founding_status_safe()}
           if catalog.founding_enabled() else {}),
        "usage_packs_max": catalog.MAX_USAGE_PACKS,
        "setup_guarantee": catalog.SETUP_GUARANTEE,
        "billing_periods": catalog.BILLING_PERIODS,
    }


async def _founding_status_safe() -> dict:
    """Founding seats for public pages; falls back to "unknown" without a DB."""
    from src.services import catalog, founding

    try:
        async with app.state.session_factory() as session:
            return await founding.status(session)
    except Exception:
        return {**catalog.FOUNDING_OFFER, "seats_total": catalog.FOUNDING_OFFER["seats"],
                "seats_used": None, "seats_remaining": None, "available": False}


class LiveDemoChatRequest(BaseModel):
    session_id: str = Field(default="", max_length=64)
    text: str = Field(..., min_length=1, max_length=1000)


@app.get("/api/live-demo")
async def live_demo_info():
    from src.services import live_demo

    return live_demo.info()


@app.post("/api/live-demo/chat")
async def live_demo_chat(request: Request, body: LiveDemoChatRequest):
    """Public «جرّب الوكيل الآن» chat: fictional clinic, tenant reply agent, no payments, 24h retention."""
    from src.services import live_demo
    from src.utils.rate_limit import client_ip

    ok, retry = live_demo.check_rate(client_ip(request))
    if not ok:
        raise HTTPException(429, detail={"error": "Too many demo messages", "retry_after_seconds": retry},
                            headers={"Retry-After": str(retry)})
    async with app.state.session_factory() as session:
        return await live_demo.chat(session, body.session_id, body.text)


@app.get("/api/portal/packages/{package_key}/demo")
async def portal_package_demo(package_key: str):
    from src.services.demo_content import get_package_detail

    detail = get_package_detail(package_key)
    if not detail:
        raise HTTPException(404, "Package not found")
    return detail


class PortalProjectCreate(BaseModel):
    client_name: str
    phone: str
    email: Optional[str] = None
    package: str
    # Agents the CEO diagnosis recommended (?agents=a,b) and paid add-ons.
    agents: Optional[list[str]] = None
    addons: int = 0


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
            status="pending",
        )
        session.add(project)
        await session.flush()

        addons = max(0, min(int(request.addons or 0), catalog.MAX_ADDON_AGENTS))
        project.addon_agents = addons
        for slug in catalog.staff_team(request.package, addons, preferred=request.agents or []):
            session.add(ClientAgent(project_id=project.id, slug=slug, status="dormant"))
        await session.commit()
        await session.refresh(project)

        payload = await portal_project_payload(session, project)
    # The creator gets the portal session for this project (the UUID alone is no
    # longer a credential; see src/core/portal_auth.py).
    from src.core import portal_auth

    return portal_auth.set_session_cookie(JSONResponse(payload), project)


@app.get("/api/portal/projects/{project_id}")
async def portal_get_project(project_id: str, http_request: Request):
    from src.core.portal_auth import require_portal_project

    async with app.state.session_factory() as session:
        project = await require_portal_project(session, http_request, project_id)
        return await portal_project_payload(session, project)


class PortalAnswers(BaseModel):
    answers: dict


@app.post("/api/portal/projects/{project_id}/agents/{slug}/wake")
async def portal_wake_agent(project_id: str, slug: str, http_request: Request):
    from src.services import catalog
    from src.models import ClientAgent, ClientProject
    from sqlalchemy import select
    from uuid import UUID
    from src.core.portal_auth import require_portal_project

    async with app.state.session_factory() as session:
        await require_portal_project(session, http_request, project_id)
        result = await session.execute(
            select(ClientAgent).where(
                ClientAgent.project_id == UUID(project_id),
                ClientAgent.slug == slug,
            )
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(404, "Agent not part of this project")

        project = (
            await session.execute(select(ClientProject).where(ClientProject.id == UUID(project_id)))
        ).scalar_one_or_none()
        if not project:
            raise HTTPException(404, "Project not found")
        if project.status != "active":
            raise HTTPException(402, "Subscription not active — activate your plan first")

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
    from src.core.portal_auth import require_portal_project

    async with app.state.session_factory() as session:
        await require_portal_project(session, http_request, project_id)
        result = await session.execute(
            select(ClientAgent).where(
                ClientAgent.project_id == UUID(project_id),
                ClientAgent.slug == slug,
            )
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(404, "Agent not part of this project")

        project = (
            await session.execute(select(ClientProject).where(ClientProject.id == UUID(project_id)))
        ).scalar_one_or_none()
        if not project:
            raise HTTPException(404, "Project not found")
        if project.status != "active":
            raise HTTPException(402, "Subscription not active — activate your plan first")

        agent_def = await app.state.agent_registry.get_agent(slug)
        if not agent_def:
            raise HTTPException(404, "Agent definition missing")

        agent.answers = request.answers
        agent.status = "running"
        await session.commit()

        tmpl = agent_def.prompt_templates.get("default")
        if not tmpl:
            raise HTTPException(404, "Prompt template not found")

        from src.services import agent_brief, catalog as _catalog

        variables = agent_brief.build_variables(tmpl.template_text, request.answers, project.client_name)
        rendered = app.state.prompt_engine.render(tmpl.template_text, variables)
        brief = agent_brief.brief_block(
            request.answers, (_catalog.EMPLOYEES.get(slug) or {}).get("questions"), project.client_name
        )

        from src.services import agent_tools as _tools
        brief += await _tools.run_context(session, slug, project, request.answers)

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
            prompt=rendered.user_prompt + brief,
            system_prompt=(
                rendered.system_prompt + "\n\n" + agent_brief.SAUDI_CONTEXT + "\n\n" + lang_instruction
            ).strip(),
            temperature=agent_def.default_parameters.get("temperature", 0.7),
            max_tokens=max(agent_def.default_parameters.get("max_tokens", 2000), agent_brief.MIN_MAX_TOKENS),
        )
        response = await app.state.model_provider.complete_with_fallback("gemini", model_request)

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

    pkg = catalog.get_package(project.package) or {}
    return {
        "project_id": str(project.id),
        "package": project.package,
        "package_name": pkg.get("name", project.package),
        "package_en": pkg.get("name_en", project.package),
        "client_name": project.client_name,
        "status": project.status,
        "requires_payment": project.status != "active",
        "billing_period": getattr(project, "billing_period", None) or "monthly",
        "addon_agents": int(getattr(project, "addon_agents", 0) or 0),
        "current_period_end": project.current_period_end.isoformat() if getattr(project, "current_period_end", None) else None,
        "team": team,
    }


# ---------------- Smart Consultant (System 2: conversational solutions guide) ----------------

class ConsultMessage(BaseModel):
    role: str
    content: str


class ConsultRequest(BaseModel):
    messages: list[ConsultMessage]


class CeoConsultRequest(BaseModel):
    problem: str
    lang: Optional[str] = None


@app.post("/api/ceo/consult", dependencies=[Depends(rate_limit_consult)])
async def ceo_consult(request: CeoConsultRequest, http_request: Request):
    """The CEO advisor: diagnose, staff with real agents, recommend a tier.

    Works without any API key (deterministic rules); a configured model chain
    only refines the wording and agent choice, and is validated against the
    catalog. The plan and its VAT-inclusive total are always computed here.
    """
    from src.services import ceo_advisor

    try:
        problem = ceo_advisor.validate_problem(request.problem)
    except ValueError:
        raise HTTPException(400, "Describe the problem in a sentence or two")
    locale = request.lang or http_request.cookies.get(_LOCALE_COOKIE, "ar")
    provider = getattr(app.state, "model_provider", None)
    return await ceo_advisor.diagnose(problem, provider=provider, locale=locale)


class SupportTicketRequest(BaseModel):
    name: str = ""
    email: str = ""
    question: str = ""
    consent: bool = False
    page: Optional[str] = None
    lang: Optional[str] = None


def _ticket_lang(body: "SupportTicketRequest", request: Request) -> str:
    # The page the visitor wrote from decides the reply language; a stale
    # locale cookie from another tab must not flip an Arabic visitor to English.
    if body.lang in ("ar", "en"):
        return body.lang
    page = (body.page or "").lower()
    if page == "/en" or page.startswith("/en/"):
        return "en"
    if page == "/ar" or page.startswith("/ar/"):
        return "ar"
    return "en" if request.cookies.get(_LOCALE_COOKIE) == "en" else "ar"


@app.post("/api/support/ticket", dependencies=[Depends(rate_limit_ticket)])
async def create_support_ticket(body: SupportTicketRequest, request: Request):
    """Human handoff from the site assistant: store a ticket, notify the owner."""
    from src.services import tickets

    lang = _ticket_lang(body, request)
    try:
        async with app.state.session_factory() as session:
            t = await tickets.create(session, name=body.name, email=body.email, question=body.question,
                                     consent=body.consent, lang=lang, page=body.page)
    except tickets.TicketError as exc:
        return JSONResponse(status_code=422, content={"ok": False, "field": exc.field})
    return {"ok": True, "reference": t.reference,
            "response_time": tickets.RESPONSE_TIME_EN if lang == "en" else tickets.RESPONSE_TIME_AR}


@app.get("/api/owner/tickets")
async def owner_list_tickets(request: Request):
    from src.core.owner_auth import check_owner
    from src.services import tickets

    if not check_owner(request):
        raise HTTPException(401, "owner only")
    async with app.state.session_factory() as session:
        return {"tickets": await tickets.list_recent(session)}


_CONSULT_HANDOFF_AR = ("ما أقدر أأكد هذه المعلومة من مصادرنا الآن. أقدر أحوّلك لخدمة العملاء "
                       "ويرد عليك فريقنا بالبريد.")
_CONSULT_HANDOFF_EN = ("I can't confirm that from our sources right now. I can transfer you to customer service "
                       "and our team will reply by email.")


async def _consult_sources(history: list[dict]) -> list[dict]:
    """Top KB chunks of Al-Narjis's own KB for the latest visitor message (best effort)."""
    q = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
    if not q.strip():
        return []
    try:
        from src.services import rag

        from src.services.rag import site_kb

        async with app.state.session_factory() as session:
            hits = await rag.retrieve(session, q, project_id=None, k=3)
            await session.commit()  # lazy index backfill
        hits += await site_kb.retrieve(q, k=3)  # catalog facts (prices etc.), generated from catalog.py
        hits.sort(key=lambda h: -h["score"])
        return [h for h in hits if h["score"] >= rag.min_confidence()][:4]
    except Exception as exc:  # noqa: BLE001
        from src.utils.logger import get_logger

        get_logger(__name__).warning("consult: RAG retrieval failed (%s)", type(exc).__name__)
        return []


def _consult_grounded(reply: str, hits: list[dict], packages_text: str) -> bool:
    from src.services import catalog as _cat
    from src.services.rag.generate import grounded
    from src.services.support import SUPPORT_EMAIL

    facts = " ".join([packages_text, SUPPORT_EMAIL, "https://karmaai.online", "/portal", "15",
                      repr(_cat.PACKAGES), repr(_cat.ADDON_AGENT), repr(_cat.USAGE_ADDONS),
                      repr(_cat.SETUP_GUARANTEE), str(_cat.MAX_ADDON_AGENTS)])
    # Markdown list markers ("1." / "2)") at line start are not facts.
    reply = re.sub(r"(?m)^\s*\d{1,2}[.)]\s", "- ", reply)
    return grounded(reply, hits, extra_facts=facts)


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

    _pkgs = " | ".join(
        f"{p['name']} ({p['name_en']}): {p['price']} SAR/month before VAT, "
        f"{p.get('display_agents') or p['agent_count']} agents, "
        f"setup {int(p.get('setup_fee') or 0) // 100} SAR waived on annual billing. "
        + "; ".join(p.get("scope_en") or [])
        for p in _catalog.PACKAGES.values()
    )
    _emps = ", ".join(
        e["title_ar"] for e in _catalog.EMPLOYEES.values()
    )
    from src.core.karma_persona import build_consult_system_prompt, extract_lead
    system_prompt = build_consult_system_prompt(
        locale=locale,
        packages_text=_pkgs,
        employees_text=_emps,
    )

    # RAG: ground the assistant in Al-Narjis's own KB (project_id NULL only; never a tenant's docs).
    from src.ai.sanitize import sanitize_public_text

    rag_hits = await _consult_sources(history)
    if rag_hits:
        system_prompt += (
            "\n\nSOURCES (Al-Narjis knowledge base; state facts, numbers, policies and links ONLY from these "
            "sources or the REAL PRODUCT list above; if they do not cover the question, say so and offer "
            "«تحويل لخدمة العملاء»):\n"
            + "\n".join(
                f"[{i + 1}] {sanitize_public_text(str(h.get('title') or ''))}: "
                f"{sanitize_public_text(str(h.get('text') or ''))}"
                for i, h in enumerate(rag_hits)
            )
        )

    model_request = ModelRequest(
        prompt="\n".join(f"{m['role']}: {m['content']}" for m in history) + "\n\nassistant:",
        system_prompt=system_prompt,
        temperature=0.3,
        max_tokens=1200,
    )

    try:
        response = await app.state.model_provider.complete_with_fallback("gemini", model_request)
        lead_data, reply = extract_lead(response.content)
        if lead_data:
            import asyncio

            from src.services import karma_lead as _karma_lead
            asyncio.get_running_loop().create_task(
                _karma_lead.capture_consult_lead(app.state.session_factory, lead_data)
            )
        content = sanitize_public_text(reply or response.content.strip())
        if content and not _consult_grounded(content, rag_hits, _pkgs):
            # A number or link that is in neither the KB sources nor the real
            # price list is a hallucination: never show it, hand off instead.
            from src.utils.logger import get_logger

            get_logger(__name__).warning("consult: ungrounded number/link in reply; handing off")
            return {"reply": _CONSULT_HANDOFF_AR if locale == "ar" else _CONSULT_HANDOFF_EN, "handoff": "ungrounded"}
        if not content:
            # A model that answered with nothing usable is a failure, not a
            # success with an empty bubble in the transcript.
            raise RuntimeError("model returned empty content")
        return {"reply": content}
    except Exception as e:
        from src.utils.logger import get_logger

        # Failure type only. The exception text is not logged: provider errors
        # routinely echo the submitted key back in the response body.
        get_logger(__name__).error(
            "consult: every provider in the fallback chain failed (%s)",
            type(e).__name__,
        )
        # 503 rather than 200. The old contract answered 200 with an apology
        # string, which made a total outage indistinguishable from a working
        # conversation to every monitor, every uptime check and every log-based
        # alert. The body shape is unchanged -- {"reply": ...} -- so consult.html,
        # which renders data.reply without checking the status, keeps working.
        return JSONResponse(
            status_code=503,
            content={
                "reply": (
                    "المستشار الذكي غير متاح الآن. راسل فريقنا على "
                    "Al-Narjis@karmaai.online وسيرد عليك بالبريد."
                    if locale == "ar"
                    else
                    "The smart consultant is temporarily unavailable. Email our "
                    "team at Al-Narjis@karmaai.online and they will reply by email."
                ),
                "error": "consult_unavailable",
                "retryable": True,
            },
        )


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
    from src.models import Schedule
    from sqlalchemy import select, desc

    next_map = {str(j["id"]): j.get("next_run_time") for j in app.state.scheduler.get_jobs()}
    async with app.state.session_factory() as session:
        rows = (await session.execute(select(Schedule).order_by(desc(Schedule.created_at)))).scalars().all()
        out = []
        for s in rows:
            try:
                out.append({
                    "id": str(s.id),
                    "name": s.name,
                    "target_type": s.target_type,
                    "target_id": str(s.target_id),
                    "trigger": s.cron_expression or (f"interval:{s.interval_seconds}s" if s.interval_seconds else ("once" if s.run_once_at else "manual")),
                    "is_active": s.is_active,
                    "next_run_time": next_map.get(str(s.id)),
                    "run_count": s.run_count,
                    "max_runs": s.max_runs,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                })
            except Exception:
                continue
        return {"schedules": out}


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


@app.get("/api/schedules/{schedule_id}", dependencies=[Depends(require_owner_api)])
async def get_schedule(schedule_id: str):
    from uuid import UUID
    from src.models import Schedule
    from sqlalchemy import select

    async with app.state.session_factory() as session:
        sched = (await session.execute(select(Schedule).where(Schedule.id == UUID(schedule_id)))).scalar_one_or_none()
    if not sched:
        raise HTTPException(404, "Schedule not found")
    try:
        target_id = str(sched.target_id)
    except Exception:
        raise HTTPException(404, "Schedule not found")
    next_run = None
    for job in app.state.scheduler.get_jobs():
        if job["id"] == str(sched.id):
            next_run = job.get("next_run_time")
            break
    return {
        "id": str(sched.id),
        "name": sched.name,
        "target_type": sched.target_type,
        "target_id": target_id,
        "payload": sched.payload,
        "trigger": sched.cron_expression or (f"interval:{sched.interval_seconds}s" if sched.interval_seconds else ("once" if sched.run_once_at else "manual")),
        "is_active": sched.is_active,
        "next_run_time": next_run,
        "run_count": sched.run_count,
        "max_runs": sched.max_runs,
        "created_at": sched.created_at.isoformat() if sched.created_at else None,
    }


@app.post("/api/schedules/{schedule_id}/{action}", dependencies=[Depends(require_owner_api)])
async def schedule_action(schedule_id: str, action: str):
    from uuid import UUID
    if action in ("enable", "resume"):
        ok = await app.state.scheduler.enable_schedule(UUID(schedule_id))
    elif action in ("disable", "pause"):
        ok = await app.state.scheduler.disable_schedule(UUID(schedule_id))
    else:
        raise HTTPException(400, "Unknown schedule action")
    if not ok:
        raise HTTPException(404, "Schedule not found or inactive in registry")
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


@app.post("/api/executions/{execution_id}/retry", dependencies=[Depends(require_owner_api)])
async def retry_execution(execution_id: str):
    from uuid import UUID
    from src.models import WorkflowExecution
    from src.automation.workflow_engine import WorkflowDefinition
    from sqlalchemy import select

    async with app.state.session_factory() as session:
        exec_row = (await session.execute(
            select(WorkflowExecution).where(WorkflowExecution.id == UUID(execution_id))
        )).scalar_one_or_none()
        if not exec_row:
            raise HTTPException(404, "Execution not found")
        if exec_row.status == "running":
            raise HTTPException(409, "Execution is still running")
        wf = await _get_workflow(session, exec_row.workflow_id)
        if not wf:
            raise HTTPException(404, "Workflow not found")
        input_data = dict(exec_row.trigger_payload or {})
        ctx = exec_row.context or {}
        for key, value in ctx.items():
            if isinstance(value, (str, int, float, bool)) and key not in input_data:
                input_data[key] = value
        exec_row.status = "retried"
        await session.commit()

    definition = WorkflowDefinition.model_validate(wf.definition)
    result = await app.state.workflow_engine.execute(definition, input_data)
    return {
        "execution_id": str(result.workflow_id),
        "status": "completed" if result.success else "failed",
        "steps_completed": result.steps_completed,
        "steps_failed": result.steps_failed,
        "final_context": result.final_context,
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


@app.get("/api/promo")
async def promo_status():
    from src.services import payments as pm
    return {"promo": pm.promo_info()}


PHONE_INVALID_MESSAGE = (
    "رقم الجوال غير صحيح. اكتبه بالشكل 05XXXXXXXX أو ‎+9665XXXXXXXX."
)
PHONE_MOBILE_REQUIRED_MESSAGE = (
    "رقم الجوال مطلوب لتفعيل الوصول المبكر، ويجب أن يكون جوالًا سعوديًا صحيحًا "
    "(05XXXXXXXX أو ‎+9665XXXXXXXX)."
)


@app.post("/api/leads")
async def create_lead(request: Request, background_tasks: BackgroundTasks):
    """Public website capture — writes one canonical CRM record.

    Phone quality gate: a supplied number must be a real number, and the
    early-access programme additionally requires a reachable Saudi mobile
    (``05XXXXXXXX`` / ``+9665XXXXXXXX``). Nothing is written, no welcome email
    and no owner alert happen for a rejected number.
    """
    body = await request.json()
    from src.models import AcquisitionLead, LeadEvent
    from src.services.lead_normalize import (
        is_reachable_mobile,
        is_valid_phone,
        normalize_email,
        normalize_phone,
    )
    from src.services.lead_priority import score_lead
    from src.services.lead_segmentation import classify, suggest_package

    name = (body.get("name") or "").strip()
    raw_phone = (body.get("phone") or "").strip()
    email = normalize_email(body.get("email"))
    message = (body.get("message") or "").strip() or None
    package = (body.get("package") or "").strip() or None

    if raw_phone and not is_valid_phone(raw_phone):
        raise HTTPException(400, PHONE_INVALID_MESSAGE)
    if package == "early_access" and not is_reachable_mobile(raw_phone):
        raise HTTPException(400, PHONE_MOBILE_REQUIRED_MESSAGE)
    phone = normalize_phone(raw_phone)

    segment, _reason = classify(name)
    priority = score_lead(company_name=name, phone=phone, email=email, segment=segment)

    async with app.state.session_factory() as session:
        lead = AcquisitionLead(
            company_name=name or "عميل محتمل",
            contact_name=name or None,
            phone=phone,
            phone_raw=(body.get("phone") or None),
            email=email,
            source="website",
            segment=segment,
            suggested_package=package or suggest_package(segment),
            lead_status="NEW",
            priority=priority.priority,
            priority_score=priority.score,
            priority_reason=priority.reasons,
            notes=message,
        )
        session.add(lead)
        await session.flush()
        session.add(LeadEvent(
            lead_id=lead.id,
            event_type="captured",
            status_after="NEW",
            channel="website",
            message=message,
        ))
        await session.commit()
        await session.refresh(lead)
        lead_id = lead.id
        lead_email = lead.email
        lead_name = lead.contact_name or lead.company_name

    _name = body.get("name") or "عميل جديد"
    _phone = body.get("phone") or "—"
    _email = email or "—"
    _agent = message or package or "—"
    alert_text = (
        "🚨 تسجيل وصول مبكر جديد — Al-Narjis AI\n"
        f"👤 العميل: {_name}\n"
        f"📞 الجوال: {_phone}\n"
        f"📧 البريد: {_email}\n"
        f"🤖 الطلب: {_agent}"
    )

    # The visitor is answered the moment the record is committed. Welcome email,
    # follow-up scheduling and the owner alert run after the response so a slow
    # SMTP or Telegram call can never stall the public form.
    background_tasks.add_task(
        _lead_side_effects, lead_id, lead_email, lead_name, alert_text
    )

    return {"success": True, "lead_id": str(lead_id), "email_queued": bool(lead_email)}


@app.post("/api/leads/{lead_id}/demo-viewed")
async def mark_demo_viewed(lead_id: str):
    """Public package page records that a captured lead opened its demo."""
    from uuid import UUID

    from sqlalchemy import select

    from src.models import AcquisitionLead, LeadEvent

    try:
        uid = UUID(lead_id)
    except ValueError:
        raise HTTPException(400, "Invalid id") from None

    async with app.state.session_factory() as session:
        lead = (
            await session.execute(select(AcquisitionLead).where(AcquisitionLead.id == uid))
        ).scalar_one_or_none()
        if lead is None:
            raise HTTPException(404, "Lead not found")
        session.add(LeadEvent(lead_id=lead.id, event_type="demo_viewed", channel="website"))
        await session.commit()
    return {"success": True}


async def _schedule_lead_followups(lead_id, email: str, name: str):
    from datetime import datetime, timedelta, timezone as _dt_tz
    from zoneinfo import ZoneInfo
    from src.automation.scheduler import ScheduleConfig

    try:
        scheduler = app.state.scheduler
    except Exception:
        scheduler = None
    if scheduler is None or not email:
        return

    now_ry = datetime.now(_dt_tz.utc).astimezone(ZoneInfo("Asia/Riyadh")).replace(tzinfo=None)
    steps = [1, 2, 3]
    hours = {1: 1, 2: 24, 3: 72}
    for step in steps:
        try:
            await scheduler.add_schedule(ScheduleConfig(
                name=f"Lead follow-up {str(lead_id)[:8]} step {step}",
                target_type="lead_email",
                target_id=lead_id,
                payload={
                    "step": step,
                    "email": email,
                    "name": name or "عميلنا العزيز",
                    "lead_id": str(lead_id),
                },
                run_once_at=now_ry + timedelta(hours=hours[step]),
                timezone="Asia/Riyadh",
            ))
        except Exception as e:
            logger.warning("Could not schedule lead follow-up step %s: %s", step, e)


async def _lead_side_effects(lead_id, email, name, alert_text: str) -> None:
    """Best-effort post-capture work: runs after the visitor already has a 200."""
    if email:
        try:
            from src.services import email_service

            await email_service.send_welcome(email, name or "عميلنا العزيز")
        except Exception as e:
            logger.warning("Lead welcome email failed for %s: %s", lead_id, e)
        try:
            await _schedule_lead_followups(lead_id, email, name)
        except Exception as e:
            logger.warning("Lead follow-up scheduling failed for %s: %s", lead_id, e)

    try:
        from src.services.telegram_sender import send_owner_alert

        await send_owner_alert(alert_text)
    except Exception as e:
        logger.warning("Owner alert failed for lead %s: %s", lead_id, e)


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
    from src.models import AcquisitionLead
    from sqlalchemy import select, desc

    async with app.state.session_factory() as session:
        result = await session.execute(
            select(AcquisitionLead).order_by(desc(AcquisitionLead.created_at)).limit(limit).offset(offset)
        )
        leads = result.scalars().all()
        return {"leads": [
            {
                "id": str(l.id),
                "name": l.company_name,
                "company": l.company_name,
                "phone": l.phone,
                "email": l.email,
                "package": l.suggested_package,
                "message": l.notes,
                "status": l.lead_status,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            } for l in leads
        ]}


@app.get("/api/owner/overview", dependencies=[Depends(require_owner_api)])
async def owner_overview():
    from src.models import AcquisitionLead, Payment, ClientProject
    from sqlalchemy import select, func, desc

    async with app.state.session_factory() as session:
        lead_counts = dict((await session.execute(
            select(AcquisitionLead.lead_status, func.count()).group_by(AcquisitionLead.lead_status)
        )).all())
        payment_by_status = dict((await session.execute(
            select(Payment.status, func.count()).group_by(Payment.status)
        )).all())
        paid_total = (await session.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "paid")
        )).scalar_one()

        projects = (await session.execute(
            select(func.count()).select_from(ClientProject)
        )).scalar_one()
        active_projects = (await session.execute(
            select(func.count()).select_from(ClientProject).where(ClientProject.status == "active")
        )).scalar_one()

        recent_payments_rows = (await session.execute(
            select(Payment).order_by(desc(Payment.created_at)).limit(10)
        )).scalars().all()
        recent_leads_rows = (await session.execute(
            select(AcquisitionLead).order_by(desc(AcquisitionLead.created_at)).limit(10)
        )).scalars().all()

    return {
        "leads": {
            "total": sum(lead_counts.values()),
            "by_status": {k: v for k, v in sorted(lead_counts.items())},
        },
        "payments": {
            "total": sum(payment_by_status.values()),
            "by_status": {k: v for k, v in sorted(payment_by_status.items())},
            "revenue_halalas": paid_total,
            "revenue_sar": round(paid_total / 100, 2),
        },
        "projects": {"total": projects, "active": active_projects},
        "recent_payments": [
            {
                "id": str(p.id),
                "package": p.package,
                "amount_sar": p.amount / 100,
                "currency": p.currency,
                "status": p.status,
                "customer": p.customer_name or p.customer_email or "-",
                "created_at": p.created_at.isoformat() if p.created_at else None,
            } for p in recent_payments_rows
        ],
        "recent_leads": [
            {
                "id": str(l.id),
                "name": l.company_name,
                "phone": l.phone,
                "package": l.suggested_package,
                "status": l.lead_status,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            } for l in recent_leads_rows
        ],
    }


@app.post("/api/leads/{lead_id}/status", dependencies=[Depends(require_owner_api)])
async def update_lead_status(lead_id: str, request: Request):
    from src.models import LEAD_STATUSES, AcquisitionLead, LeadEvent
    from sqlalchemy import select
    from uuid import UUID

    body = await request.json()
    new_status = body.get("status")
    if new_status not in LEAD_STATUSES:
        raise HTTPException(400, f"Unknown status: {new_status}")
    async with app.state.session_factory() as session:
        result = await session.execute(select(AcquisitionLead).where(AcquisitionLead.id == UUID(lead_id)))
        lead = result.scalar_one_or_none()
        if not lead:
            raise HTTPException(404, "Lead not found")
        before = lead.lead_status
        lead.lead_status = new_status
        session.add(LeadEvent(
            lead_id=lead.id, event_type="status_change",
            status_before=before, status_after=new_status,
        ))
        await session.commit()
    return {"success": True}


@app.get("/health")
async def health(request: Request, deep: bool = False, ai: bool = False):
    """Liveness for Render (cheap). ``?deep=1`` adds db + external checks (see /health/deep).

    ``?ai=1`` adds /api/ai/ask readiness for an owner session only: env-var
    presence as booleans, and whether pgvector and the public KB index are
    ready. Anyone else gets the plain liveness body. No secret values, no
    embedder name, and no handoff reason.
    """
    if ai:
        from src.core.owner_auth import check_owner

        if not check_owner(request):
            return {"status": "healthy", "version": "0.1.0"}
        from src.ai.status import snapshot

        body = {"status": "healthy", "version": "0.1.0"}
        body["ai_ask"] = await snapshot(getattr(app.state, "session_factory", None))
        return body
    if not deep:
        return {"status": "healthy", "version": "0.1.0"}
    from src.services import ops_monitor

    result = await ops_monitor.deep_health(app.state.session_factory)
    result["version"] = "0.1.0"
    return JSONResponse(result, status_code=503 if result["status"] == "unhealthy" else 200)


@app.get("/health/deep")
async def health_deep(request: Request):
    return await health(request, deep=True)


# ---------------- Payments (Moyasar) ----------------

class PaymentCreateRequest(BaseModel):
    package: str
    method: str = "creditcard"
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    promo: Optional[str] = None
    lead_id: Optional[str] = None
    project_id: Optional[str] = None
    billing_period: str = "monthly"  # "monthly" | "annual" (pay 10 months, get 12)
    addons: int = 0                  # extra agents on top of the tier, 299 SAR/month each (an integer count)
    conversation_packs: int = 0      # +1,000 conversations / month, 99 SAR each
    voice_packs: int = 0             # +100 voice minutes / month, 99 SAR each
    # Mandatory: buyer ticked «الخدمة تبدأ فوراً والمبلغ غير قابل للاسترداد بعد التفعيل».
    refund_consent: bool = False


def _require_refund_consent(consent) -> None:
    """422 unless the buyer ticked policies.REFUND_CONSENT_AR (checkout and invoice links)."""
    from src.services import policies

    if consent is not True:
        raise HTTPException(422, {
            "error": "refund_consent_required",
            "message_ar": "يجب الموافقة على: " + policies.REFUND_CONSENT_AR,
            "message_en": "You must agree to: " + policies.REFUND_CONSENT_EN,
        })


def _record_refund_consent(payment) -> None:
    """Stamp consent time + policy version once; the first acceptance is the record."""
    from datetime import datetime as _dt, timezone as _tz

    from src.services import policies

    if payment.refund_consent_at is None:
        payment.refund_consent_at = _dt.now(_tz.utc)
        payment.refund_consent_version = policies.POLICY_VERSION


class InvoiceConsentRequest(BaseModel):
    # Mandatory: buyer ticked «الخدمة تبدأ فوراً والمبلغ غير قابل للاسترداد بعد التفعيل».
    refund_consent: bool = False


def _request_locale(request: Request) -> str:
    return request.cookies.get("narjis_lang") or "ar"


# Declared before /api/payments/{payment_id} so the literal path wins.
@app.get("/api/payments/capabilities")
async def payment_capabilities():
    """Which payment methods are real right now. Booleans and public details only."""
    from src.services import payments as pm

    return await pm.capabilities_async()


@app.get("/api/owner/payments/readiness", dependencies=[Depends(require_owner_api)])
async def owner_payment_readiness():
    """Owner view of the same thing, plus what is missing to switch card on."""
    from src.services import payments as pm

    return await pm.readiness_async()


def _public_base_url(request: Request) -> str:
    """Origin for URLs handed to a gateway: PUBLIC_BASE_URL, else the request
    origin with the proxy's X-Forwarded-Proto honoured (TLS ends at the proxy)."""
    configured = (settings.public_base_url or "").strip().rstrip("/")
    if configured:
        return configured
    base = str(request.base_url).rstrip("/")
    proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    if proto == "https" and base.startswith("http://"):
        base = "https://" + base[len("http://"):]
    return base


# A double click on "pay" used to create two orders and two Moyasar invoices.
# Replays inside the window get the first response back. In-process only: with
# several workers a replay can still land on another process.
PAYMENT_IDEMPOTENCY_WINDOW_SECONDS = 120.0
_payment_replays: dict[str, tuple[float, dict]] = {}
_payment_locks: dict[str, asyncio.Lock] = {}


def _payment_replay_key(request: Request, body: "PaymentCreateRequest") -> Optional[str]:
    header = (request.headers.get("idempotency-key") or "").strip()
    if header:
        return "key:" + header[:128]
    who = (body.customer_phone or body.customer_email or "").strip().lower()
    if not who:
        return None
    return "|".join(("cust", who, body.package, body.method.lower(), (body.promo or "").strip().upper(), body.project_id or "", body.lead_id or "", body.billing_period.lower(), str(body.addons), str(body.conversation_packs), str(body.voice_packs)))


@app.post("/api/payments")
async def create_payment(request: Request, body: PaymentCreateRequest):
    key = _payment_replay_key(request, body)
    if key is None:
        return await _create_payment(request, body)
    lock = _payment_locks.setdefault(key, asyncio.Lock())
    async with lock:
        now = time.monotonic()
        for k, (at, _) in list(_payment_replays.items()):
            if now - at > PAYMENT_IDEMPOTENCY_WINDOW_SECONDS:
                _payment_replays.pop(k, None)
                if k != key and not _payment_locks.get(k, lock).locked():
                    _payment_locks.pop(k, None)
        cached = _payment_replays.get(key)
        if cached:
            return {**cached[1], "replayed": True}
        response = await _create_payment(request, body)
        _payment_replays[key] = (time.monotonic(), response)
        return response


async def _create_payment(request: Request, body: PaymentCreateRequest):
    from src.services import payments as pm

    from src.services import policies

    from src.core.owner_auth import check_owner

    # The owner dashboard raises bank-transfer invoices for a lead; the buyer is
    # not present, so that path records no consent (refund_consent_at stays NULL).
    owner_invoice = body.method.lower() == "invoice" and check_owner(request)
    if not owner_invoice:
        _require_refund_consent(body.refund_consent)
    locale = _request_locale(request)
    include_vat = locale == "ar"
    base = _public_base_url(request)
    from src.services import catalog as _cat_vp

    if body.voice_packs and not _cat_vp.USAGE_ADDONS["voice_minutes"].get("purchasable", True):
        raise HTTPException(400, "Voice-minute packs are not available yet (voice agent coming soon)")
    try:
        base_amount = pm.package_amount(body.package, body.billing_period, body.addons)
        packs_amount = pm.usage_packs_amount(body.conversation_packs, body.voice_packs, body.billing_period)
    except pm.PaymentError as exc:
        raise HTTPException(400, str(exc))

    # Refuse a method before any row exists. A test or missing Moyasar key,
    # and the disabled PayPal / bank-transfer paths, must not leave an orphan
    # payment that a webhook could later mark paid.
    method = body.method.lower()
    if method == "paypal" and not pm.customer_paypal_enabled():
        raise HTTPException(400, "PayPal is not available. Pay by card through Moyasar.")
    if method == "invoice" and not owner_invoice and not pm.customer_bank_transfer_enabled():
        raise HTTPException(400, "Bank transfer is not available. Pay by card through Moyasar.")
    if method in pm.CARD_METHODS and not pm.moyasar_collects_money():
        raise HTTPException(503, pm.CARD_ACTIVATING_AR)

    async with app.state.session_factory() as session:
        from uuid import UUID as _UUID

        lead_uuid = None
        if body.lead_id:
            try:
                lead_uuid = _UUID(body.lead_id)
            except ValueError:
                raise HTTPException(422, "lead_id must be a valid UUID")

        project_uuid = None
        if body.project_id:
            try:
                project_uuid = _UUID(body.project_id)
            except ValueError:
                raise HTTPException(422, "project_id must be a valid UUID")

        payment = await pm.create_payment(
            session,
            body.package,
            body.customer_name,
            body.customer_phone,
            body.customer_email,
            promo=body.promo,
            lead_id=lead_uuid,
            project_id=project_uuid,
            billing_period=body.billing_period,
            addons=body.addons,
            conversation_packs=body.conversation_packs,
            voice_packs=body.voice_packs,
            founding=None,  # founding price auto-applies while seats remain
        )
        # The order decides the price (promo or founding, never both).
        setup_halalas = pm.setup_fee_amount(body.package, body.billing_period, founding=payment.founding)
        discount_halalas = max(0, base_amount + packs_amount + setup_halalas - payment.amount)
        discount_pct = 1 if discount_halalas else 0
        founding_info = {"founding_applied": bool(payment.founding)}
        from datetime import datetime as _dt, timezone as _tz

        if body.refund_consent is True:
            payment.refund_consent_at = _dt.now(_tz.utc)
            payment.refund_consent_version = policies.POLICY_VERSION
            await session.commit()

        if method == "paypal":
            # Owner decision (option A): prices are VAT-inclusive and the invoice
            # document always bills base + 15%, so every automated charge must
            # equal total_with_vat. Previously the English locale charged the
            # pre-VAT base while the invoice showed the VAT-inclusive figure.
            charge = pm.total_with_vat(payment.amount)
            try:
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
                    "discount": discount_halalas,
                    "promo_applied": discount_pct > 0 and not payment.founding,
                    **founding_info,
                    "vat": pm.vat_amount(payment.amount) if include_vat else 0,
                    "total": charge,
                    # PayPal cannot charge SAR: the buyer pays this USD amount.
                    "charge_currency": order["currency"],
                    "charge_amount": order["amount_usd"],
                    "sar_per_usd": settings.paypal_sar_per_usd,
                }
            except pm.PaymentError as e:
                if not pm.customer_bank_transfer_enabled():
                    await session.delete(payment)
                    await session.commit()
                    raise HTTPException(502, "PayPal is unavailable. Pay by card through Moyasar.")
                payment.status = "invoice"
                await session.commit()
                return {
                    "payment_id": str(payment.id),
                    "status": "invoice",
                    "gateway": "invoice",
                    "message": str(e),
                    "amount": payment.amount,
                    "discount": discount_halalas,
                    "promo_applied": discount_pct > 0 and not payment.founding,
                    **founding_info,
                    "vat": pm.vat_amount(payment.amount),
                    "total": pm.total_with_vat(payment.amount),
                    "invoice_total": pm.total_with_vat(payment.amount),
                    "invoice_url": f"/invoice/{payment.id}",
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
                data = await pm.initiate_moyasar(
                    session,
                    payment,
                    source,
                    success_url=f"{base}/payment/success?id={payment.id}",
                    back_url=f"{base}/payment/failure?id={payment.id}",
                    callback_url=f"{base}/webhooks/moyasar",
                )
                return {
                    "payment_id": str(payment.id),
                    "status": payment.status,
                    "gateway": "moyasar",
                    "gateway_payment_id": payment.gateway_payment_id,
                    "redirect_url": data.get("checkout_url") or (data.get("source", {}).get("transaction_url") if isinstance(data.get("source"), dict) else None),
                    "publishable_key": pm.get_publishable_key(),
                    "amount": payment.amount,
                    "discount": discount_halalas,
                    "promo_applied": discount_pct > 0 and not payment.founding,
                    **founding_info,
                    "vat": pm.vat_amount(payment.amount),
                    "total": pm.total_with_vat(payment.amount),
                }
            except pm.PaymentError as e:
                if not pm.customer_bank_transfer_enabled():
                    await session.delete(payment)
                    await session.commit()
                    raise HTTPException(502, "Card payment is unavailable. Pay by card through Moyasar when it is live.")
                payment.status = "pending"
                await session.commit()
                return {
                    "payment_id": str(payment.id),
                    "status": "invoice",
                    "gateway": "invoice",
                    "message": str(e),
                    "amount": payment.amount,
                    "discount": discount_halalas,
                    "promo_applied": discount_pct > 0 and not payment.founding,
                    **founding_info,
                    "invoice_total": pm.total_with_vat(payment.amount),
                    "invoice_url": f"/invoice/{payment.id}",
                }

        # Invoice / bank-transfer fallback — customer path stays off unless the flag is on.
        if not owner_invoice and not pm.customer_bank_transfer_enabled():
            await session.delete(payment)
            await session.commit()
            raise HTTPException(400, "Bank transfer is not available. Pay by card through Moyasar.")
        payment.status = "invoice"
        await session.commit()
        return {
            "payment_id": str(payment.id),
            "status": "invoice",
            "gateway": "invoice",
            "amount": payment.amount,
            "discount": discount_halalas,
            "promo_applied": discount_pct > 0 and not payment.founding,
            **founding_info,
            "vat": pm.vat_amount(payment.amount),
            "total": pm.total_with_vat(payment.amount),
            "invoice_total": pm.total_with_vat(payment.amount),
            "invoice_url": f"/invoice/{payment.id}",
        }


@app.post("/api/payments/{payment_id}/capture")
async def capture_payment(payment_id: str, request: Request):
    from uuid import UUID
    from sqlalchemy import select
    from src.models import Payment
    from src.services import payments as pm

    locale = _request_locale(request)
    try:
        payment_uuid = UUID(payment_id)
    except ValueError:
        raise HTTPException(422, "invalid payment id")

    async with app.state.session_factory() as session:
        result = await session.execute(select(Payment).where(Payment.id == payment_uuid))
        payment = result.scalar_one_or_none()
        if not payment:
            raise HTTPException(404, "Payment not found")

        if payment.gateway == "paypal" and payment.gateway_payment_id:
            # The order id comes from our own record, never from the request body.
            try:
                await pm.finalize_paypal_payment(session, payment)
            except pm.PaymentError as exc:
                raise HTTPException(502, f"PayPal: {exc}")
        else:
            payment = (await session.execute(select(Payment).where(Payment.id == UUID(payment_id)))).scalar_one()
            if payment.status != "paid":
                await pm.verify_payment(session, payment.id)

    if payment.status == "paid":
        async with app.state.session_factory() as session:
            await _apply_paid_outcome(session, payment.id, note="مؤكد عبر بوابة الدفع")

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


async def _apply_paid_outcome(session, payment_id: UUID, *, note: str = "") -> dict:
    """Attach the verified-payment outcome: Decision Log, LeadEvent, lead WON.

    A lead is only moved to WON after a payment is actually ``paid`` (gateway
    capture or owner-confirmed receipt). Never before.
    """
    from collections import OrderedDict
    from sqlalchemy import select as _sel
    from src.models import AcquisitionLead, Decision, LeadEvent, Payment as _Payment
    from src.services import payments as _pm

    payment = (
        await session.execute(_sel(_Payment).where(_Payment.id == payment_id))
    ).scalar_one_or_none()
    if not payment or payment.status != "paid":
        return {"applied": False, "reason": "payment not paid"}

    marker = f"payment_ref:{payment.id}"
    existing = (
        await session.execute(_sel(Decision).where(Decision.reason == marker))
    ).scalar_one_or_none()
    if existing:
        return {"applied": True, "deduplicated": True}

    package = payment.package or "social"
    total_halalas = _pm.total_with_vat(payment.amount)

    session.add(
        Decision(
            decision=f"تم استلام دفعة ({package}) بقيمة {total_halalas // 100} ر.س",
            reason=marker,
            actor="owner",
            evidence=OrderedDict(
                payment_id=str(payment.id), package=package, amount=payment.amount, note=note
            ),
            expected="paid",
            actual="paid",
            status="resolved",
            learning=note or "تحقق يدوي من استلام الدفعة",
        )
    )

    if payment.lead_id:
        lead = (
            await session.execute(
                _sel(AcquisitionLead).where(AcquisitionLead.id == payment.lead_id)
            )
        ).scalar_one_or_none()
        if lead and (lead.lead_status or "NEW") != "WON":
            before = lead.lead_status or "NEW"
            from datetime import datetime, timezone
            lead.lead_status = "WON"
            lead.outreach_status = "WON"
            lead.last_contacted_at = datetime.now(timezone.utc)
            session.add(
                LeadEvent(
                    lead_id=lead.id,
                    event_type="status_change",
                    status_before=before,
                    status_after="WON",
                    channel="payment",
                    message=f"دفعة باكية {package} مؤكدة — تحويل العميل إلى WON",
                    note=note or "تم تأكيد استلام الدفعة",
                    created_at=datetime.now(timezone.utc),
                )
            )

    await session.commit()
    activation = await _pm.activate_subscription(session, payment)
    return {"applied": True, **activation}


@app.post("/api/owner/billing/renewals/run", dependencies=[Depends(require_owner_api)])
async def owner_run_renewals(request: Request, days_before: Optional[int] = None):
    """Owner-only: run one renewal pass now (the scheduler runs it daily).

    Raises renewal invoices for subscriptions ending within ``days_before``
    days, records draft reminders (never sent automatically) and expires
    subscriptions whose 3-day grace has elapsed. Idempotent.
    """
    from src.services import renewals

    days = renewals.RENEWAL_LEAD_DAYS if days_before is None else max(0, min(int(days_before), 60))
    async with app.state.session_factory() as session:
        return await renewals.run_renewals(session, days_before=days, base_url=_public_base_url(request))


@app.post("/api/owner/billing/collections/run", dependencies=[Depends(require_owner_api)])
async def owner_run_collections(request: Request):
    """Owner-only: reminder sequence (D-5/D-1/D0/D+3), failed-payment recovery
    links and overage invoices. Customer messages stay drafts unless
    BILLING_AUTO_SEND is enabled; owner Telegram alerts are always sent."""
    from src.services import collections

    async with app.state.session_factory() as session:
        return await collections.run_collections(session, base_url=_public_base_url(request))


@app.get("/api/owner/billing/zatca/status", dependencies=[Depends(require_owner_api)])
async def owner_zatca_status():
    """Owner-only: which seller details are still missing for ZATCA phase 1."""
    from src.services import zatca

    async with app.state.session_factory() as session:
        return {**zatca.readiness(), "issued": await zatca.count_issued(session)}


@app.post("/api/owner/billing/invoices/{payment_id}/credit-note", dependencies=[Depends(require_owner_api)])
async def owner_credit_note(payment_id: str, request: Request):
    """Owner-only: issue a credit note (إشعار دائن) for a refund. Body:
    ``{"amount": <pre-VAT halalas, optional = full>, "reason": "..."}``."""
    from uuid import UUID

    from sqlalchemy import select

    from src.models import Payment
    from src.services import zatca

    try:
        body = await request.json()
    except Exception:
        body = {}
    body = body if isinstance(body, dict) else {}
    try:
        pid = UUID(payment_id)
    except ValueError:
        raise HTTPException(404, "payment not found")
    async with app.state.session_factory() as session:
        payment = (await session.execute(select(Payment).where(Payment.id == pid))).scalar_one_or_none()
        if payment is None:
            raise HTTPException(404, "payment not found")
        try:
            note = await zatca.issue_credit_note(
                session, payment, amount=body.get("amount"), reason=str(body.get("reason") or "استرداد")[:500]
            )
        except (zatca.ZatcaError, TypeError, ValueError) as exc:
            raise HTTPException(422, str(exc))
        return zatca.to_dict(note)


# ---------------------------------------------------------------------------
#  Usage metering (per subscription, monthly) and the founding offer
# ---------------------------------------------------------------------------

def _project_uuid(project_id: str):
    from uuid import UUID as _UUID

    try:
        return _UUID(project_id)
    except (TypeError, ValueError):
        raise HTTPException(422, "project_id must be a valid UUID")


async def _load_project(session, project_id: str):
    from sqlalchemy import select as _sel

    from src.models import ClientProject

    project = (await session.execute(
        _sel(ClientProject).where(ClientProject.id == _project_uuid(project_id))
    )).scalar_one_or_none()
    if project is None:
        raise HTTPException(404, "Project not found")
    return project


@app.get("/api/owner/usage", dependencies=[Depends(require_owner_api)])
async def owner_usage(include_inactive: bool = False):
    """Owner console: current-window usage for every subscription (over-limit first)."""
    from src.services import catalog, usage

    async with app.state.session_factory() as session:
        rows = await usage.owner_usage_report(session, include_inactive=include_inactive)
        await session.commit()
    return {"customers": rows, "over_limit": sum(1 for r in rows if r["over_limit"]),
            "alert_thresholds": list(catalog.USAGE_ALERT_THRESHOLDS)}


@app.get("/api/owner/usage/{project_id}", dependencies=[Depends(require_owner_api)])
async def owner_usage_project(project_id: str):
    from src.services import usage

    async with app.state.session_factory() as session:
        project = await _load_project(session, project_id)
        row = await usage.current_usage(session, project)
        await session.commit()
        return usage.usage_summary(project, row)


class UsageEventRequest(BaseModel):
    kind: str                      # "conversation" | "voice" | "meta_fee"
    quantity: int = 1              # conversation: ignored; voice: seconds; meta_fee: halalas
    contact: Optional[str] = None  # conversation: the customer's handle/number
    channel: str = "whatsapp"
    ref: Optional[str] = None      # call id / message id: counted once


@app.post("/api/owner/usage/{project_id}/events", dependencies=[Depends(require_owner_api)])
async def owner_record_usage(project_id: str, body: UsageEventRequest):
    """Record usage from a channel that is not wired to a webhook yet (e.g. the
    voice provider's call log) or a manual correction. Never cuts service."""
    from src.services import usage

    async with app.state.session_factory() as session:
        project = await _load_project(session, project_id)
        if body.kind == "conversation":
            result = await usage.record_conversation(session, project, body.contact or "", body.channel, ref=body.ref)
        elif body.kind == "voice":
            result = await usage.record_voice(session, project, body.quantity, contact=body.contact, ref=body.ref)
        elif body.kind == "meta_fee":
            result = await usage.record_meta_fee(session, project, body.quantity, ref=body.ref)
        else:
            raise HTTPException(422, "kind must be conversation, voice or meta_fee")
        await session.commit()
        return result


class WhatsAppNumberRequest(BaseModel):
    phone_number_id: Optional[str] = None


@app.post("/api/owner/projects/{project_id}/whatsapp-number", dependencies=[Depends(require_owner_api)])
async def owner_link_whatsapp_number(project_id: str, body: WhatsAppNumberRequest):
    """Link the subscriber's own WhatsApp Cloud number (Meta phone_number_id) so
    its webhook traffic is metered against this subscription. Empty unlinks."""
    async with app.state.session_factory() as session:
        project = await _load_project(session, project_id)
        value = (body.phone_number_id or "").strip()[:64] or None
        if value and not value.isdigit():
            raise HTTPException(422, "phone_number_id must be digits")
        project.wa_phone_number_id = value
        await session.commit()
        return {"project_id": str(project.id), "wa_phone_number_id": value}


@app.get("/api/founding")
async def founding_public():
    """Public: founding seats left (pricing page / portal)."""
    from src.services import catalog, founding

    if not catalog.founding_enabled():
        return {"enabled": False}
    async with app.state.session_factory() as session:
        st = await founding.status(session)
    return {"enabled": True} | {k: st[k] for k in ("seats_total", "seats_remaining", "available", "annual_pct", "monthly_pct",
                               "monthly_commitment_months", "waives_setup_fee")}


@app.get("/api/owner/founding", dependencies=[Depends(require_owner_api)])
async def owner_founding():
    from src.services import founding

    async with app.state.session_factory() as session:
        return {"status": await founding.status(session), "customers": await founding.founding_projects(session)}


@app.post("/api/owner/founding/{project_id}/revoke", dependencies=[Depends(require_owner_api)])
async def owner_revoke_founding(project_id: str):
    """Revoke a founding seat: frees it and ends the discount on future renewals."""
    from src.services import founding

    async with app.state.session_factory() as session:
        project = await _load_project(session, project_id)
        result = await founding.revoke(session, project)
        if not result["revoked"]:
            raise HTTPException(409, result["reason"])
        return result


@app.get("/api/owner/summary", dependencies=[Depends(require_owner_api)])
async def owner_summary():
    """Owner-only, read-only snapshot for the command center and assistant bots:
    revenue/MRR, plans, renewals due in 7 days, unpaid orders and bank transfers
    awaiting confirmation, founding seats, usage flags (80/100%), review queue,
    leads pipeline and site health. No secrets, no writes."""
    from src.services import owner_summary as _os

    async with app.state.session_factory() as session:
        data = await _os.build_summary(session)
        await session.rollback()
    return data


@app.get("/owner/command", response_class=HTMLResponse)
async def owner_command_center(request: Request):
    from src.core.owner_auth import check_owner

    if not check_owner(request):
        return RedirectResponse("/login")
    return templates.TemplateResponse(request, "owner_command.html", {})


@app.post("/api/owner/billing/backfill", dependencies=[Depends(require_owner_api)])
async def owner_backfill_subscriptions(apply: bool = False):
    """Owner-only: put legacy active subscribers (no period end) on the renewal
    cycle and staff paid add-on agents. Dry run unless ``apply=true``."""
    from src.services import renewals

    async with app.state.session_factory() as session:
        return await renewals.backfill_legacy_subscriptions(session, dry_run=not apply)


class ConfirmReceivedRequest(BaseModel):
    confirmed_by: str = "owner"
    note: Optional[str] = None


@app.post("/api/payments/{payment_id}/confirm-received", dependencies=[Depends(require_owner_api)])
async def confirm_payment_received(payment_id: str, body: ConfirmReceivedRequest, request: Request):
    """Owner-only: mark a manual (bank-transfer/invoice) payment as actually received."""
    from uuid import UUID as _UUID

    from sqlalchemy import select as _select
    from src.models import Payment as _Payment
    from src.services import payments as _pm

    try:
        payment_uuid = _UUID(payment_id)
    except ValueError:
        raise HTTPException(422, "invalid payment id")

    async with app.state.session_factory() as session:
        payment = (
            await session.execute(_select(_Payment).where(_Payment.id == payment_uuid))
        ).scalar_one_or_none()
        if not payment:
            raise HTTPException(404, "Payment not found")

        if payment.status == "paid":
            return {"payment_id": str(payment.id), "status": "paid", "already_paid": True}

        if payment.gateway in ("moyasar", "paypal") and payment.gateway_payment_id:
            raise HTTPException(409, "Gateway payment must be captured through its gateway")

        payment.status = "paid"
        await session.commit()

        note = (body.note or "التحقق يدوي من استلام التحويل البنكي/فاتورة").strip()
        outcome = await _apply_paid_outcome(session, payment.id, note=note)

        return {
            "payment_id": str(payment.id),
            "status": "paid",
            "amount": payment.amount,
            "vat": _pm.vat_amount(payment.amount),
            "total": _pm.total_with_vat(payment.amount),
            "invoice_url": f"/invoice/{payment.id}",
            "outcome": outcome,
        }


@app.post(
    "/api/payments/{payment_id}/transfer-reported",
    dependencies=[Depends(rate_limit_transfer_report)],
)
async def report_transfer_sent(payment_id: str, request: Request):
    """The buyer says they sent the money: record it and alert the owner.

    This never marks the payment paid. Only the owner does that, through
    confirm-received, after the money is actually in the account.
    """
    from uuid import UUID as _UUID

    from sqlalchemy import select as _select

    from src.models import Payment as _Payment
    from src.services import payments as _pm

    try:
        payment_uuid = _UUID(payment_id)
    except ValueError:
        raise HTTPException(422, "invalid payment id")

    async with app.state.session_factory() as session:
        payment = (
            await session.execute(_select(_Payment).where(_Payment.id == payment_uuid))
        ).scalar_one_or_none()
        if not payment:
            raise HTTPException(404, "Payment not found")
        if payment.gateway in ("moyasar", "paypal") and payment.gateway_payment_id:
            raise HTTPException(409, "This invoice is settled through its payment gateway")
        if payment.status != "paid" and payment.refund_consent_at is None:
            # Owner-raised invoices reach the buyer without checkout, so the
            # non-refundable consent is collected here, on the invoice page.
            try:
                body = await request.json()
            except Exception:  # noqa: BLE001 - empty / non-JSON body = no consent
                body = {}
            _require_refund_consent(body.get("refund_consent") if isinstance(body, dict) else None)
            _record_refund_consent(payment)
            await session.commit()
        already = payment.gateway_source == "transfer_reported"
        if not already and payment.status != "paid":
            payment.gateway_source = "transfer_reported"
            await session.commit()
        instructions = _pm.transfer_instructions(payment)
        was_paid = payment.status == "paid"

    notified = False
    if not already and not was_paid:
        try:
            from src.services import telegram_sender

            await telegram_sender.send_owner_alert(
                "💰 تحويل بنكي معلَن\n"
                f"فاتورة: {instructions['reference']}\n"
                f"المبلغ: {instructions['total_sar']} {instructions['currency']}\n"
                f"العميل: {payment.customer_name or '-'} · {payment.customer_phone or '-'}\n"
                "العميل يقول إنه أرسل التحويل. فعّلها من /api/payments/"
                f"{instructions['payment_id']}/confirm-received بعد التأكد من الإيداع."
            )
            notified = True
        except Exception:  # noqa: BLE001 - an alert failure must not lose the record
            notified = False

    return {
        **instructions,
        "already_reported": already,
        "notified_owner": notified,
        "awaiting_verification": not was_paid,
    }


@app.post(
    "/api/payments/{payment_id}/pay-card",
    dependencies=[Depends(rate_limit_transfer_report)],
)
async def pay_invoice_by_card(payment_id: str, body: InvoiceConsentRequest, request: Request):
    """Buyer pays an owner-raised invoice by card (Moyasar) from /invoice/<id>.

    Requires the same refund consent as portal checkout (422 without it) and
    stores its timestamp + policy version on the payment before any charge.
    """
    from uuid import UUID as _UUID

    from sqlalchemy import select as _select

    from src.models import Payment as _Payment
    from src.services import payments as _pm

    try:
        payment_uuid = _UUID(payment_id)
    except ValueError:
        raise HTTPException(422, "invalid payment id")
    _require_refund_consent(body.refund_consent)

    base = _public_base_url(request)
    async with app.state.session_factory() as session:
        payment = (
            await session.execute(_select(_Payment).where(_Payment.id == payment_uuid))
        ).scalar_one_or_none()
        if not payment:
            raise HTTPException(404, "Payment not found")
        if payment.status == "paid":
            raise HTTPException(409, "This invoice is already paid")
        _record_refund_consent(payment)
        await session.commit()

        if not _pm.moyasar_collects_money():
            raise HTTPException(503, _pm.CARD_ACTIVATING_AR)

        if payment.gateway == "moyasar" and payment.gateway_payment_id:
            return {
                "payment_id": str(payment.id),
                "gateway": "moyasar",
                "redirect_url": f"https://checkout.moyasar.com/invoices/{payment.gateway_payment_id}?lang=ar",
            }
        if payment.gateway == "paypal" and payment.gateway_payment_id:
            raise HTTPException(409, "This invoice is settled through PayPal")
        if not settings.moyasar_api_secret:
            raise HTTPException(503, "Card payment is not available; use bank transfer")
        try:
            data = await _pm.initiate_moyasar(
                session,
                payment,
                _pm.source_credit_card(),
                success_url=f"{base}/payment/success?id={payment.id}",
                back_url=f"{base}/invoice/{payment.id}",
                callback_url=f"{base}/webhooks/moyasar",
            )
        except _pm.PaymentError as e:
            raise HTTPException(502, f"card payment unavailable: {str(e)[:200]}")
        return {
            "payment_id": str(payment.id),
            "gateway": "moyasar",
            "redirect_url": data["checkout_url"],
        }


@app.get("/invoice/{payment_id}")
async def invoice_page(request: Request, payment_id: str):
    from uuid import UUID

    from sqlalchemy import select

    from src.models import Payment
    from src.services import payments as pm
    from src.services import policies

    locale = _request_locale(request)

    # A malformed id used to raise ValueError and answer 500. Anything that is
    # not a resolvable invoice lands on the recovery page below instead, because
    # this URL is handed to a buyer at the exact moment they decide to pay.
    payment = None
    tax_invoice, credit_notes = None, []
    try:
        parsed = UUID(payment_id)
    except (ValueError, AttributeError, TypeError):
        parsed = None
    if parsed is not None:
        async with app.state.session_factory() as session:
            result = await session.execute(select(Payment).where(Payment.id == parsed))
            payment = result.scalar_one_or_none()
            if payment is not None:
                # ZATCA phase 1: a paid order gets its numbered simplified tax
                # invoice (issued once); unpaid orders render as a pro-forma.
                from src.services import zatca

                tax_invoice = await zatca.ensure_invoice(session, payment)
                credit_notes = await zatca.credit_notes_for(session, payment.id) if tax_invoice else []

    if not payment:
        return templates.TemplateResponse(
            request,
            "invoice_missing.html" if locale == "ar" else "invoice_missing_en.html",
            {"missing_ref": payment_id[:8]},
            status_code=404,
        )

    from datetime import timedelta as _td

    from src.services import zatca

    zp = zatca.preview(payment)
    template = "invoice.html" if locale == "ar" else "invoice_en.html"
    return templates.TemplateResponse(
        request,
        template,
        {
            "payment": payment,
            "tax_invoice": tax_invoice,
            "credit_notes": credit_notes,
            "seller": tax_invoice.seller if tax_invoice else zatca.seller(),
            "lines": tax_invoice.lines if tax_invoice else zp["lines"],
            "qr_svg": zatca.qr_svg(tax_invoice.qr_tlv) if tax_invoice else None,
            "issued_riyadh": (tax_invoice.issued_at + _td(hours=3)).strftime("%Y-%m-%d %H:%M")
            if tax_invoice and tax_invoice.issued_at else None,
            "base": payment.amount,
            "vat": pm.vat_amount(payment.amount),
            "total": pm.total_with_vat(payment.amount),
            "xfer": pm.transfer_instructions(payment) if payment.status != "paid" and pm.customer_bank_transfer_enabled() else None,
            "consent_needed": payment.status != "paid" and payment.refund_consent_at is None,
            "refund_consent_ar": policies.REFUND_CONSENT_AR,
            "refund_consent_en": policies.REFUND_CONSENT_EN,
            "card_enabled": payment.status != "paid" and (
                (payment.gateway == "moyasar" and bool(payment.gateway_payment_id))
                or (payment.gateway == "invoice" and bool(settings.moyasar_api_secret))
            ),
            "paypal_enabled": payment.status not in ("paid", pm.REVIEW_STATUS)
            and payment.gateway in ("invoice", "paypal")
            and pm.customer_paypal_enabled()
            and pm.paypal_collects_money(),
            "paypal_usd": (
                f"{pm.sar_halalas_to_usd_cents(pm.total_with_vat(payment.amount)) / 100:.2f}"
                if pm.paypal_collects_money() else None
            ),
        },
    )


@app.get("/api/payments/{payment_id}")
async def get_payment(payment_id: str):
    from uuid import UUID
    from src.services import payments as pm

    async with app.state.session_factory() as session:
        try:
            payment = await pm.verify_payment(session, UUID(payment_id))
        except ValueError:
            raise HTTPException(404, "Payment not found")
        except pm.PaymentNotFound as e:
            raise HTTPException(404, str(e))
        except pm.PaymentError as e:
            # Gateway unreachable/erroring: report it, never as "not found".
            raise HTTPException(502, str(e))

        if payment.status == "paid":
            await _apply_paid_outcome(session, payment.id, note="مؤكد عبر بوابة الدفع")

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


@app.post("/webhooks/moyasar")
async def moyasar_webhook(request: Request):
    """Server-to-server notification from Moyasar (payment_paid / payment_failed).

    Authenticated by the dashboard secret_token; the order is then decided from
    a fresh API fetch, never from the body alone. Replays are a 200 no-op.
    """
    import hmac

    from src.services import payments as pm

    try:
        event = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "invalid JSON")
    if not isinstance(event, dict):
        raise HTTPException(400, "invalid payload")

    expected = (settings.moyasar_webhook_secret or "").encode()
    supplied = str(event.get("secret_token") or "").encode()
    if not expected or not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(401, "invalid secret_token")

    async with app.state.session_factory() as session:
        try:
            result = await pm.handle_moyasar_webhook(session, event)
        except pm.PaymentError as exc:
            # Non-2xx makes Moyasar retry later.
            raise HTTPException(502, f"could not verify with Moyasar: {exc}")
        if result.get("status") == "paid" and not result.get("already"):
            from uuid import UUID as _UUID

            await _apply_paid_outcome(session, _UUID(result["payment_id"]), note="webhook ميسر")
    return result


@app.post(
    "/api/payments/{payment_id}/pay-paypal",
    dependencies=[Depends(rate_limit_transfer_report)],
)
async def pay_invoice_with_paypal(payment_id: str, body: InvoiceConsentRequest, request: Request):
    """Buyer pays an invoice with PayPal (charged in USD at the riyal peg).

    Same refund consent as checkout and /pay-card (422 without it). Returns the
    PayPal approval URL plus the USD amount that will be charged.
    """
    from uuid import UUID as _UUID

    from sqlalchemy import select as _select

    from src.models import Payment as _Payment
    from src.services import payments as pm

    try:
        payment_uuid = _UUID(payment_id)
    except ValueError:
        raise HTTPException(422, "invalid payment id")
    _require_refund_consent(body.refund_consent)
    if not pm.customer_paypal_enabled() or not pm.paypal_collects_money():
        raise HTTPException(503, "PayPal is not available. Pay by card through Moyasar.")
    base = _public_base_url(request)
    async with app.state.session_factory() as session:
        payment = (
            await session.execute(_select(_Payment).where(_Payment.id == payment_uuid))
        ).scalar_one_or_none()
        if not payment:
            raise HTTPException(404, "Payment not found")
        if payment.status in ("paid", pm.REVIEW_STATUS):
            raise HTTPException(409, "This invoice is already paid")
        if payment.gateway == "moyasar" and payment.gateway_payment_id:
            raise HTTPException(409, "This invoice is settled through its card gateway")
        _record_refund_consent(payment)
        await session.commit()
        try:
            order = await pm.create_paypal_order(
                session,
                payment,
                return_url=f"{base}/payment/success?id={payment.id}",
                cancel_url=f"{base}/invoice/{payment.id}",
            )
        except pm.PaymentError as exc:
            raise HTTPException(502, f"PayPal unavailable: {str(exc)[:200]}")
        return {
            "payment_id": str(payment.id),
            "status": payment.status,
            "gateway": "paypal",
            "order_id": order["order_id"],
            "redirect_url": order["approval_url"],
            "total": pm.total_with_vat(payment.amount),
            "charge_currency": order["currency"],
            "charge_amount": order["amount_usd"],
            "sar_per_usd": settings.paypal_sar_per_usd,
        }


@app.post("/webhooks/paypal")
async def paypal_webhook(request: Request):
    """PayPal webhook. Signature verified with PayPal (PAYPAL_WEBHOOK_ID); the
    order is then re-fetched and decided server-side. Replays are a 200 no-op."""
    from src.services import payments as pm

    try:
        event = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "invalid JSON")
    if not isinstance(event, dict):
        raise HTTPException(400, "invalid payload")
    try:
        verified = await pm.verify_paypal_webhook(request.headers, event)
    except pm.PaymentError as exc:
        raise HTTPException(502, f"could not verify with PayPal: {exc}")
    if not verified:
        raise HTTPException(401, "invalid PayPal signature")

    async with app.state.session_factory() as session:
        try:
            result = await pm.handle_paypal_webhook(session, event)
        except pm.PaymentError as exc:
            raise HTTPException(502, f"could not settle with PayPal: {exc}")
        if result.get("status") == "paid" and not result.get("already"):
            from uuid import UUID as _UUID

            await _apply_paid_outcome(session, _UUID(result["payment_id"]), note="webhook PayPal")
        if result.get("alert"):
            try:
                from src.services import telegram_sender

                await telegram_sender.send_owner_alert(
                    f"⚠️ PayPal {result['alert']} — payment {result['payment_id']}. راجع الاسترداد/الإلغاء يدوياً."
                )
            except Exception:  # noqa: BLE001
                pass
    return result


@app.get("/payment/success")
async def payment_success(request: Request, id: Optional[str] = None):
    return templates.TemplateResponse(request, "payment_status.html", {"result": "success", "payment_id": id})


@app.get("/payment/failure")
async def payment_failure(request: Request, id: Optional[str] = None):
    return templates.TemplateResponse(request, "payment_status.html", {"result": "failure", "payment_id": id})
