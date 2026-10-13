"""Owner console for customer automation + the public Messenger webhook.

Owner API (cookie-authenticated, ``/api/owner/automation/*``):
  channels   GET / PUT {mode: off|review|auto}
  drafts     GET ?status=pending ; POST {id}/approve {text?} ; {id}/edit {text} ; {id}/reject {reason?}
  pipeline   GET ; POST {lead_id}/stage {stage} ; POST {lead_id}/payment-link {plan_key, billing_period}
  social     GET ; POST generate-week
  setup      GET (which credentials are present, webhook URLs to register; never values)
Page: GET /owner/automation
Public: GET/POST /webhooks/messenger
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select

from src.config.settings import get_settings
from src.core.owner_auth import check_owner, require_owner
from src.models import InboundMessage
from src.models.automation import CHANNEL_MODES, CHANNELS, PIPELINE_STAGES, LeadPipeline, SocialPostDraft
from src.services import lead_pipeline, messenger, smart_reply, social_agent

log = logging.getLogger(__name__)
router = APIRouter(tags=["automation"])
api = APIRouter(prefix="/api/owner/automation", dependencies=[Depends(require_owner)])


class ModeBody(BaseModel):
    mode: str


class TextBody(BaseModel):
    text: str | None = None
    reason: str | None = None


class StageBody(BaseModel):
    stage: str
    note: str | None = None


class PayLinkBody(BaseModel):
    plan_key: str
    billing_period: str = "monthly"
    addons: int = 0


def _base_url(request: Request) -> str:
    s = get_settings()
    return (s.public_base_url or str(request.base_url)).rstrip("/")


def _factory(request: Request):
    return request.app.state.session_factory


# --------------------------------------------------------------------------- channels

@api.get("/channels")
async def get_channels(request: Request):
    async with _factory(request)() as s:
        return {"modes": await smart_reply.all_modes(s), "allowed": list(CHANNEL_MODES)}


@api.put("/channels/{channel}")
async def put_channel(channel: str, body: ModeBody, request: Request):
    if channel not in CHANNELS or body.mode not in CHANNEL_MODES:
        raise HTTPException(400, "unknown channel or mode")
    async with _factory(request)() as s:
        await smart_reply.set_mode(s, channel, body.mode)
        await s.commit()
        return {"channel": channel, "mode": body.mode}


# --------------------------------------------------------------------------- drafts

@api.get("/drafts")
async def get_drafts(request: Request, status: str | None = "pending", limit: int = 100):
    async with _factory(request)() as s:
        rows = await smart_reply.list_drafts(s, status=status or None, limit=min(max(limit, 1), 500))
        return {"drafts": [smart_reply.draft_to_dict(d) for d in rows]}


async def _decide(request: Request, draft_id: str, fn, *args, **kwargs):
    try:
        did = UUID(draft_id)
    except ValueError:
        raise HTTPException(404, "draft not found")
    async with _factory(request)() as s:
        try:
            draft = await fn(s, did, *args, **kwargs)
        except LookupError:
            raise HTTPException(404, "draft not found")
        except ValueError as e:
            raise HTTPException(409, str(e))
        await s.commit()
        return smart_reply.draft_to_dict(draft)


@api.post("/drafts/{draft_id}/approve")
async def approve_draft(draft_id: str, request: Request, body: TextBody | None = None):
    return await _decide(request, draft_id, smart_reply.approve, text=(body.text if body else None),
                         base_url=_base_url(request))


@api.post("/drafts/{draft_id}/edit")
async def edit_draft(draft_id: str, body: TextBody, request: Request):
    return await _decide(request, draft_id, smart_reply.edit, body.text or "")


@api.post("/drafts/{draft_id}/reject")
async def reject_draft(draft_id: str, request: Request, body: TextBody | None = None):
    return await _decide(request, draft_id, smart_reply.reject, body.reason if body else None)


# --------------------------------------------------------------------------- pipeline

@api.get("/pipeline")
async def get_pipeline(request: Request):
    async with _factory(request)() as s:
        return await lead_pipeline.pipeline_board(s)


@api.post("/pipeline/{lead_id}/stage")
async def set_pipeline_stage(lead_id: UUID, body: StageBody, request: Request):
    if body.stage not in PIPELINE_STAGES:
        raise HTTPException(400, "unknown stage")
    async with _factory(request)() as s:
        pipe = await s.get(LeadPipeline, lead_id)
        if pipe is None:
            raise HTTPException(404, "lead not in pipeline")
        lead_pipeline.set_stage(pipe, body.stage, body.note or "owner")
        await s.commit()
        return {"lead_id": str(lead_id), "stage": pipe.stage}


@api.post("/pipeline/{lead_id}/payment-link")
async def pipeline_payment_link(lead_id: UUID, body: PayLinkBody, request: Request):
    async with _factory(request)() as s:
        try:
            draft = await lead_pipeline.request_payment_link(
                s, lead_id, body.plan_key, billing_period=body.billing_period, addons=body.addons,
                base_url=_base_url(request))
        except LookupError as e:
            raise HTTPException(404, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))
        await s.commit()
        return smart_reply.draft_to_dict(draft)


@api.post("/followups/run")
async def run_followups_now(request: Request):
    async with _factory(request)() as s:
        result = await lead_pipeline.run_followups(s)
        await s.commit()
        return result


# --------------------------------------------------------------------------- social

@api.get("/social")
async def get_social(request: Request):
    async with _factory(request)() as s:
        rows = (await s.execute(select(SocialPostDraft).order_by(SocialPostDraft.scheduled_for).limit(200))).scalars()
        return {"posts": [social_agent.post_to_dict(p) for p in rows]}


@api.post("/social/generate-week")
async def generate_social_week(request: Request):
    async with _factory(request)() as s:
        rows = await social_agent.generate_week(s)
        await s.commit()
        return {"posts": [social_agent.post_to_dict(p) for p in rows]}


# --------------------------------------------------------------------------- setup

def setup_status(base_url: str) -> dict:
    s = get_settings()
    have = lambda v: bool(v)  # noqa: E731 - presence only, never the value
    return {
        "whatsapp": {
            "env": {"WHATSAPP_TOKEN": have(s.whatsapp_token), "WHATSAPP_PHONE_ID": have(s.whatsapp_phone_number_id),
                    "WHATSAPP_APP_SECRET": have(s.whatsapp_app_secret),
                    "WHATSAPP_WEBHOOK_VERIFY_TOKEN": have(s.whatsapp_webhook_verify_token)},
            "webhook_url": f"{base_url}/webhooks/whatsapp",
        },
        "telegram": {
            "env": {"TELEGRAM_TOKEN": have(s.telegram_token), "TELEGRAM_WEBHOOK_SECRET": have(s.telegram_webhook_secret),
                    "TELEGRAM_OWNER_CHAT_ID": have(s.telegram_owner_chat_id)},
            "webhook_url": f"{base_url}/webhooks/telegram",
        },
        "messenger": {
            "env": {"META_PAGE_ACCESS_TOKEN": have(s.meta_page_access_token), "META_APP_SECRET": have(s.meta_app_secret),
                    "MESSENGER_VERIFY_TOKEN": have(s.messenger_verify_token)},
            "webhook_url": f"{base_url}/webhooks/messenger",
        },
        "payments": {"env": {"MOYASAR_API_SECRET": have(s.moyasar_api_secret),
                             "MOYASAR_WEBHOOK_SECRET": have(s.moyasar_webhook_secret),
                             "PUBLIC_BASE_URL": have(s.public_base_url)},
                     "webhook_url": f"{base_url}/webhooks/moyasar"},
        "llm": {"env": {k: have(getattr(s, k.lower())) for k in
                        ("GEMINI_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "GROQ_API_KEY", "ANTHROPIC_API_KEY")}},
    }


@api.get("/setup")
async def get_setup(request: Request):
    return setup_status(_base_url(request))


router.include_router(api)


# --------------------------------------------------------------------------- page

@router.get("/owner/automation", response_class=HTMLResponse)
async def automation_console(request: Request):
    if not check_owner(request):
        return RedirectResponse("/login")
    from src.main import templates

    return templates.TemplateResponse(request, "owner_automation.html", {"plans": __import__(
        "src.services.catalog", fromlist=["PACKAGES"]).PACKAGES})


# --------------------------------------------------------------------------- messenger webhook

@router.get("/webhooks/messenger")
async def messenger_verify(request: Request):
    q = request.query_params
    if messenger.verify_challenge(q.get("hub.mode"), q.get("hub.verify_token")):
        return PlainTextResponse(q.get("hub.challenge") or "")
    return PlainTextResponse("forbidden", status_code=403)


@router.post("/webhooks/messenger")
async def messenger_webhook(request: Request):
    raw = await request.body()
    if messenger.webhook_disabled_reason():
        return JSONResponse({"status": "disabled"}, status_code=200)
    if not messenger.verify_signature(request.headers.get("X-Hub-Signature-256"), raw):
        return JSONResponse({"status": "invalid_signature"}, status_code=403)
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return JSONResponse({"status": "bad_json"}, status_code=400)

    processed = duplicates = 0
    factory = _factory(request)
    for msg in messenger.extract_messages(payload):
        provider_id = f"fb:{msg.get('mid') or hashlib.sha256((msg['sender'] + msg['text']).encode()).hexdigest()[:40]}"[:255]
        async with factory() as s:
            exists = (await s.execute(select(InboundMessage.id).where(
                InboundMessage.provider_message_id == provider_id))).first()
            if exists is not None:
                duplicates += 1
                continue
            s.add(InboundMessage(
                id=uuid4(), lead_id=None, sender_number=msg["sender"][:32], provider_message_id=provider_id,
                occurred_at=datetime.now(UTC), message_type="text", text=msg["text"],
                payload_hash=hashlib.sha256(raw).hexdigest(), processing_status="received",
            ))
            await s.commit()
        processed += 1
        await smart_reply.safe_handle_inbound(
            factory, channel="messenger", recipient=msg["sender"], text=msg["text"],
            provider=getattr(request.app.state, "model_provider", None), base_url=_base_url(request))
    return {"status": "ok", "processed": processed, "duplicates": duplicates}
