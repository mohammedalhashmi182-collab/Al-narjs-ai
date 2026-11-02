"""Public workspaces and JSON APIs for the four new capabilities.

Pages are Arabic and English. The cron endpoint stays closed until
``CRON_SECRET`` is set. Card numbers and national IDs never reach storage.
"""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from src.services.capabilities.config import cron_secret, eval_max_rounds, eval_use_model, forecast_default_vat
from src.services.capabilities.cron_jobs import run_daily
from src.services.capabilities.eval_loop import run_eval_loop
from src.services.capabilities.forecast import ForecastError, PlanInput, build_forecast
from src.services.capabilities.ocr import OcrError, read_document
from src.services.capabilities.style_memory import StyleProfile, learn_from_edit, render_block

router = APIRouter(tags=["capabilities"])

WORKSPACES = (
    ("/capabilities/forecast", "financial_forecast"),
    ("/capabilities/ocr", "arabic_ocr"),
    ("/capabilities/style", "style_memory"),
    ("/capabilities/eval", "evaluation_loop"),
)


class PlanBody(BaseModel):
    name: str = "Plan"
    price_sar: float = Field(ge=0)
    customers: float = Field(gt=0)


class ForecastBody(BaseModel):
    plans: list[PlanBody] = Field(min_length=1)
    monthly_growth: float = 0
    monthly_churn: float = 0
    fixed_costs_sar: float = Field(default=0, ge=0)
    variable_cost_per_customer_sar: float = Field(default=0, ge=0)
    vat_rate: float | None = None
    horizon_months: int = 12


class StyleBody(BaseModel):
    client_key: str = ""
    brand_ar: str = ""
    brand_en: str = ""
    voice: str = "msa"
    tone: str = ""
    banned_words: list[str] = Field(default_factory=list)
    colours: str = ""
    fonts: str = ""
    signature: str = ""
    original: str = ""
    approved: str = ""


class EvalBody(BaseModel):
    text: str
    locale: str = "ar"
    dialect: str = ""
    brand_ar: str = ""
    brand_en: str = ""
    banned_words: list[str] = Field(default_factory=list)
    agent_slug: str = ""


def _page(request: Request, slug: str, extra: dict | None = None):
    from src.main import _page_lang, templates
    from src.services import catalog

    lang = _page_lang(request)
    employee = catalog.get_employee(slug) or {}
    ctx = {
        "ar": lang == "ar",
        "slug": slug,
        "employee": employee,
        "result": None,
        "error": "",
    }
    if extra:
        ctx.update(extra)
    return templates.TemplateResponse(request, "capability_workspace.html", ctx)


def _plans_from_form(name: str, price: str, customers: str) -> list[PlanInput]:
    return [PlanInput(name=name or "Plan", price_sar=float(price), customers=float(customers))]


def _percent(raw: str, default: float) -> float:
    text = (raw or "").strip().replace("%", "").replace(",", ".")
    if not text:
        return default
    value = float(text)
    if value > 1:
        value = value / 100
    return value


def _forecast_view(payload: dict, ar: bool) -> dict:
    """Drop the workbook bytes from the HTML payload; the script reads the API."""
    scenarios = []
    for item in payload["scenarios"].values():
        scenarios.append(
            {
                "label": item["label_ar"] if ar else item["label_en"],
                "break_even_month": item["break_even_month"],
                "ending_customers": item["ending_customers"],
                "total_revenue_ex_vat_sar": item["total_revenue_ex_vat_sar"],
                "total_profit_ex_vat_sar": item["total_profit_ex_vat_sar"],
                "estimate": True,
            }
        )
    return {
        "note": payload["note_ar"] if ar else payload["note_en"],
        "scenarios": scenarios,
        "estimate": True,
    }


@router.get("/capabilities/forecast", response_class=HTMLResponse)
async def forecast_page(request: Request):
    return _page(request, "financial_forecast")


@router.post("/capabilities/forecast", response_class=HTMLResponse)
async def forecast_page_submit(
    request: Request,
    plan_name: str = Form("Plan"),
    price_sar: str = Form(...),
    customers: str = Form(...),
    growth_percent: str = Form("0"),
    churn_percent: str = Form("0"),
    fixed_costs_sar: str = Form("0"),
    variable_cost_sar: str = Form("0"),
    vat_percent: str = Form("15"),
    horizon_months: str = Form("12"),
):
    from src.main import _page_lang

    ar = _page_lang(request) == "ar"
    try:
        payload = build_forecast(
            _plans_from_form(plan_name, price_sar, customers),
            monthly_growth=_percent(growth_percent, 0),
            monthly_churn=_percent(churn_percent, 0),
            fixed_costs_sar=float(fixed_costs_sar or 0),
            variable_cost_per_customer_sar=float(variable_cost_sar or 0),
            vat_rate=_percent(vat_percent, forecast_default_vat()),
            horizon_months=int(horizon_months or 12),
        )
    except (ForecastError, ValueError) as exc:
        return _page(request, "financial_forecast", {"error": str(exc)})
    return _page(
        request,
        "financial_forecast",
        {"result": _forecast_view(payload, ar), "xlsx_base64": payload["xlsx_base64"]},
    )


@router.post("/api/capabilities/forecast")
async def forecast_api(body: ForecastBody):
    try:
        return build_forecast(
            [PlanInput(name=p.name, price_sar=p.price_sar, customers=p.customers) for p in body.plans],
            monthly_growth=body.monthly_growth,
            monthly_churn=body.monthly_churn,
            fixed_costs_sar=body.fixed_costs_sar,
            variable_cost_per_customer_sar=body.variable_cost_per_customer_sar,
            vat_rate=body.vat_rate,
            horizon_months=body.horizon_months,
        )
    except ForecastError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/capabilities/ocr", response_class=HTMLResponse)
async def ocr_page(request: Request):
    return _page(request, "arabic_ocr")


@router.post("/capabilities/ocr", response_class=HTMLResponse)
async def ocr_page_submit(request: Request, file: UploadFile = File(...)):
    data = await file.read()
    try:
        result = await read_document(data, file.content_type or "")
    except OcrError as exc:
        return _page(request, "arabic_ocr", {"error": str(exc)})
    view = {k: v for k, v in result.items() if k != "xlsx_base64"}
    return _page(request, "arabic_ocr", {"result": view, "xlsx_base64": result["xlsx_base64"]})


@router.post("/api/capabilities/ocr")
async def ocr_api(file: UploadFile = File(...)):
    data = await file.read()
    try:
        return await read_document(data, file.content_type or "")
    except OcrError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/capabilities/style", response_class=HTMLResponse)
async def style_page(request: Request):
    return _page(request, "style_memory")


def _profile_from_body(body: StyleBody, *, persist: bool) -> StyleProfile:
    profile = StyleProfile(
        client_key=body.client_key or "preview",
        brand_ar=body.brand_ar,
        brand_en=body.brand_en,
        register=body.voice,
        tone=body.tone,
        banned_words=list(body.banned_words),
        colours=body.colours,
        fonts=body.fonts,
        signature=body.signature,
    )
    if body.original.strip() and body.approved.strip():
        return learn_from_edit(profile, body.original, body.approved, persist=persist)
    return profile.cleaned()


@router.post("/capabilities/style", response_class=HTMLResponse)
async def style_page_submit(
    request: Request,
    brand_ar: str = Form(""),
    brand_en: str = Form(""),
    voice: str = Form("msa"),
    tone: str = Form(""),
    banned_words: str = Form(""),
    colours: str = Form(""),
    fonts: str = Form(""),
    signature: str = Form(""),
    original: str = Form(""),
    approved: str = Form(""),
):
    body = StyleBody(
        client_key="preview",
        brand_ar=brand_ar,
        brand_en=brand_en,
        voice=voice,
        tone=tone,
        banned_words=[w.strip() for w in banned_words.split(",") if w.strip()],
        colours=colours,
        fonts=fonts,
        signature=signature,
        original=original,
        approved=approved,
    )
    profile = _profile_from_body(body, persist=False)
    return _page(
        request,
        "style_memory",
        {"result": {"prompt": render_block(profile), "register": profile.register, "banned_words": profile.banned_words}},
    )


@router.post("/api/capabilities/style/preview")
async def style_preview(body: StyleBody):
    profile = _profile_from_body(body, persist=False)
    return {
        "stored": False,
        "register": profile.register,
        "banned_words": profile.banned_words,
        "learned": profile.learned,
        "prompt": render_block(profile),
    }


@router.put("/api/capabilities/style/{client_key}")
async def style_save(client_key: str, body: StyleBody, request: Request):
    from src.core.portal_auth import require_portal_project
    from src.db.session import get_session_factory
    from src.services.capabilities.style_memory import save_profile

    factory = await get_session_factory()
    async with factory() as session:
        await require_portal_project(session, request, client_key)
        body.client_key = client_key
        profile = _profile_from_body(body, persist=True)
        saved = await save_profile(session, profile)
    return {"stored": True, "client_key": saved.client_key, "register": saved.register}


@router.get("/capabilities/eval", response_class=HTMLResponse)
async def eval_page(request: Request):
    return _page(request, "evaluation_loop")


async def _maybe_model_revise(text: str, issues: list[str]) -> str:
    from src.services.capabilities.eval_loop import placeholder_revise

    if not eval_use_model():
        return placeholder_revise(text, issues)
    try:
        from src.core.model_provider import ModelRequest
        from src.main import app

        provider = app.state.model_provider
        prompt = (
            "Revise the deliverable. Keep every fact that was already supported. "
            "Do not invent numbers, names, or sources. Remove placeholders. "
            "Defects:\n- " + "\n- ".join(issues) + "\n\nDELIVERABLE:\n" + text
        )
        response = await provider.complete_with_fallback(
            "gemini",
            ModelRequest(prompt=prompt, system_prompt="You are the Al-Narjis evaluation reviser.", temperature=0.2, max_tokens=1800),
        )
        revised = (getattr(response, "content", "") or "").strip()
        return revised or placeholder_revise(text, issues)
    except Exception:  # noqa: BLE001
        return placeholder_revise(text, issues)


def _eval_sync(body: EvalBody) -> dict[str, Any]:
    """Synchronous gate. Model revision is applied by the async wrapper."""
    outcome = run_eval_loop(
        body.text,
        locale=body.locale,
        register=body.dialect,
        brand_ar=body.brand_ar,
        brand_en=body.brand_en,
        banned_words=body.banned_words,
        max_rounds=eval_max_rounds(),
        agent_slug=body.agent_slug or "evaluation_loop",
        source="api",
    )
    return outcome.as_dict()


@router.post("/capabilities/eval", response_class=HTMLResponse)
async def eval_page_submit(request: Request, text: str = Form(...), locale: str = Form("ar")):
    body = EvalBody(text=text, locale=locale or "ar")
    if eval_use_model():
        outcome = await _eval_with_model(body)
    else:
        outcome = _eval_sync(body)
    view = {
        "passed": outcome["passed"],
        "rounds": outcome["rounds"],
        "revisions": outcome["revisions"],
        "overall": (outcome.get("final") or {}).get("overall"),
        "issues": (outcome.get("final") or {}).get("issues") or [],
        "text": outcome["text"],
    }
    return _page(request, "evaluation_loop", {"result": view})


async def _eval_with_model(body: EvalBody) -> dict:
    from src.services.capabilities import eval_loop as loop

    def revise(text: str, issues: list[str]) -> str:
        # The async model call is resolved by the placeholder path here; the
        # async route below performs the model rounds when the switch is on.
        return loop.placeholder_revise(text, issues)

    outcome = run_eval_loop(
        body.text,
        locale=body.locale,
        register=body.dialect,
        brand_ar=body.brand_ar,
        brand_en=body.brand_en,
        banned_words=body.banned_words,
        revise=revise,
        max_rounds=eval_max_rounds(),
        agent_slug=body.agent_slug or "evaluation_loop",
        source="api",
    )
    if eval_use_model() and not outcome.passed:
        card_issues = (outcome.scores[-1].get("issues") if outcome.scores else []) or []
        revised = await _maybe_model_revise(outcome.text, card_issues)
        outcome = run_eval_loop(
            revised,
            locale=body.locale,
            register=body.dialect,
            brand_ar=body.brand_ar,
            brand_en=body.brand_en,
            banned_words=body.banned_words,
            max_rounds=eval_max_rounds(),
            agent_slug=body.agent_slug or "evaluation_loop",
            source="api-model",
        )
    return outcome.as_dict()


@router.post("/api/capabilities/eval")
async def eval_api(body: EvalBody):
    if not body.text.strip():
        raise HTTPException(422, "text is required")
    if eval_use_model():
        return await _eval_with_model(body)
    return _eval_sync(body)


async def _cron_daily(request: Request):
    secret = cron_secret()
    if not secret:
        raise HTTPException(status_code=503, detail="cron_disabled")
    provided = request.headers.get("x-cron-secret") or ""
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        provided = provided or auth.split(" ", 1)[1].strip()
    if not provided or not hmac.compare_digest(provided, secret):
        raise HTTPException(status_code=401, detail="unauthorized")
    return await run_daily()


@router.get("/webhooks/cron/daily")
async def cron_daily_get(request: Request):
    return await _cron_daily(request)


@router.post("/webhooks/cron/daily")
async def cron_daily_post(request: Request):
    return await _cron_daily(request)
