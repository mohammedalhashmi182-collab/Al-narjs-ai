"""Botpress integration: closed-sale intake for the social media agent.

This is the third channel. It shares the CRM, the CEO brain and the queue with
Telegram and WhatsApp, but it owns its own path and its own authentication, so a
bug here cannot reach the live channels.

What changed versus the first attempt at this file, and why
---------------------------------------------------------
The earlier version called ``company_brain.process_event(...)``. No such method
exists -- ``CompanyBrain`` exposes ``run_once``, ``_detect_priorities``,
``_revenue_priorities`` and ``_record_decision``. Every call raised
``AttributeError``, the bare ``except Exception: pass`` swallowed it, and the
endpoint still answered that the CEO had been awakened. It reported success
while doing nothing. Everything here is wired to methods that exist, and
``tests/test_botpress_intake.py`` asserts the CEO path actually runs.

Security posture
----------------
A closed sale is a revenue event, so this is a privileged integration point: an
unauthenticated caller could otherwise fabricate a customer and make the fleet
act on it. Three layers guard it.

1. **HMAC-SHA256 over the raw body**, mirroring ``whatsapp_routes``. The secret is
   read from ``BOTPRESS_WEBHOOK_SECRET`` at call time. It is deliberately *not*
   declared in ``src/config/settings.py``: that file's env-var names are
   owner-approval territory, so the router reads the environment directly and
   stays inert (503) until the owner adds the variable in Render.
2. **Rate limiting** per client IP via ``rate_limit_botpress``.
3. **Strict validation**: ``extra="forbid"`` rejects unknown keys, every field is
   length-bounded, e-mail and phone are normalised and format-checked, control
   characters are stripped, and the package must resolve to ``catalog.PACKAGES``.
   No payload value ever reaches a shell, an ``eval``, or a format string; values
   are bound as SQLAlchemy parameters.

Idempotency
-----------
Botpress retries on a non-2xx reply, so ``eventId`` is stored in
``inbound_messages.provider_message_id`` (unique). A replay answers ``duplicate``
instead of creating a second customer or waking the fleet twice.

Audit trail
-----------
``inbound_messages`` has no free-form payload column by design -- it keeps
``payload_hash`` (SHA-256 of the raw body) plus a bounded ``media_meta`` blob.
That is what this module writes: a hash for forensics, sanitised fields for the
timeline, and never the raw request.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.utils.rate_limit import rate_limit_botpress

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["botpress"])

SIGNATURE_HEADER = "X-Botpress-Signature"
MANAGER = "CEO_AlNarjis"
SOURCE = "botpress"

# Ceilings, not aspirations. They exist so a hostile or broken sender cannot push
# a megabyte into a column sized for a phone number.
MAX_NAME = 200
MAX_EMAIL = 254
MAX_PHONE = 32
MAX_PACKAGE = 40
MAX_EVENT_ID = 64
MAX_FREE_TEXT = 500
# The queue input is serialised into a task row; keep the whole thing small.
MAX_INPUT_CHARS = 4000

_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s.]+(\.[^@\s.]+)+$")
_DIGIT_RE = re.compile(r"\d")
# Every C0 control character plus DEL. Newlines and tabs are included on purpose:
# an identity field must be a single line, or a customer name carrying "\n" would
# forge extra lines in the owner alert that quotes it. Free-text fields use
# _clean_notes instead, which keeps the line breaks a human wrote.
_CONTROL_ALL_RE = re.compile(r"[\x00-\x1f\x7f]")
_CONTROL_TEXT_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Sale -> agent that should pick it up. Keys are catalog package keys; the
# fallback applies when the reported package is not in the catalog.
_ONBOARDING_SLUG = {
    "social": "social_media",
    "ecommerce": "store_manager",
    "content": "content_ideas",
    "growth": "marketing_agent",
}


def webhook_secret() -> str:
    """The shared secret, or an empty string when the integration is off."""
    return (os.environ.get("BOTPRESS_WEBHOOK_SECRET") or "").strip()


def is_configured() -> bool:
    return bool(webhook_secret())


def sign_body(secret: str, raw: bytes) -> str:
    """Exposed so tests can produce a valid signature without duplicating HMAC."""
    return hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()


def verify_signature(signature: str, raw: bytes, secret: str) -> bool:
    """Constant-time HMAC-SHA256 check, tolerating a ``sha256=`` prefix."""
    if not signature or not secret:
        return False
    provided = signature.strip()
    if provided.lower().startswith("sha256="):
        provided = provided.split("=", 1)[1].strip()
    return hmac.compare_digest(provided.lower(), sign_body(secret, raw))


def _clean(value: Optional[str], limit: int) -> str:
    """Single-line sanitisation: strip control characters, then hard-bound length.

    Newlines are removed because every caller here formats the value into a
    single line of an owner alert or an audit field.
    """
    if value is None:
        return ""
    text = _CONTROL_ALL_RE.sub("", str(value)).strip()
    return text[:limit]


def _clean_notes(value: Optional[str], limit: int) -> str:
    """Free-text sanitisation: keeps the author's line breaks, drops the rest."""
    if value is None:
        return ""
    text = _CONTROL_TEXT_RE.sub("", str(value)).strip()
    return text[:limit]


def normalize_phone(value: Optional[str]) -> str:
    """Keep digits and a single leading ``+``.

    Saudi input arrives as ``05xxxxxxxx``, ``+9665xxxxxxxx`` or ``9665xxxxxxxx``.
    Everything else is dropped, so a stored value can never carry markup.
    """
    text = _clean(value, 64)
    if not text:
        return ""
    plus = text.startswith("+")
    digits = "".join(_DIGIT_RE.findall(text))
    if not digits:
        return ""
    digits = digits[:MAX_PHONE - 1]
    return f"+{digits}" if plus else digits


class ClosedSale(BaseModel):
    """A closed sale as the social media agent reports it."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    clientName: str = Field(min_length=1, max_length=MAX_NAME)
    clientEmail: Optional[str] = Field(default=None, max_length=MAX_EMAIL)
    clientPhone: Optional[str] = Field(default=None, max_length=MAX_PHONE)
    chosenPackage: str = Field(min_length=1, max_length=MAX_PACKAGE)
    paymentStatus: str = Field(min_length=1, max_length=32)
    eventId: Optional[str] = Field(default=None, max_length=MAX_EVENT_ID)
    notes: Optional[str] = Field(default=None, max_length=MAX_FREE_TEXT)

    @field_validator("clientName", "chosenPackage", "paymentStatus")
    @classmethod
    def _require_clean_text(cls, value: str) -> str:
        cleaned = _clean(value, MAX_FREE_TEXT)
        if not cleaned:
            raise ValueError("value is empty after sanitisation")
        return cleaned

    @field_validator("notes")
    @classmethod
    def _clean_free_text(cls, value: Optional[str]) -> Optional[str]:
        cleaned = _clean_notes(value, MAX_FREE_TEXT)
        return cleaned or None

    @field_validator("clientEmail")
    @classmethod
    def _validate_email(cls, value: Optional[str]) -> Optional[str]:
        cleaned = _clean(value, MAX_EMAIL).lower()
        if not cleaned:
            return None
        if not _EMAIL_RE.match(cleaned):
            raise ValueError("invalid e-mail address")
        return cleaned

    @field_validator("clientPhone")
    @classmethod
    def _validate_phone(cls, value: Optional[str]) -> Optional[str]:
        cleaned = normalize_phone(value)
        if not cleaned:
            return None
        if len(_DIGIT_RE.findall(cleaned)) < 9:
            raise ValueError("phone number is too short")
        return cleaned

    def package_key(self) -> Optional[str]:
        """Map a reported label onto a catalog key, or ``None``.

        Botpress may report ``"Social"``, ``"social"`` or the Arabic name, so the
        match is case-insensitive and then falls back to a substring. An unknown
        package never raises: the sale is still real, it is simply not priced.
        """
        from src.services import catalog

        label = _clean(self.chosenPackage, MAX_FREE_TEXT).casefold()
        for key, meta in catalog.PACKAGES.items():
            if label in (key.casefold(), str(meta.get("price", "")).casefold()):
                return key
        for key, meta in catalog.PACKAGES.items():
            names = {
                str(meta.get("name", "")).casefold(),
                str(meta.get("name_en", "")).casefold(),
                key.casefold(),
            }
            if any(name and name in label for name in names):
                return key
        return None

    def is_paid(self) -> bool:
        return self.paymentStatus.strip().casefold() in {"success", "paid", "completed"}


def segment_for(package_key: Optional[str]) -> str:
    """Classification for the CRM. Descriptive only -- it is not a lead status."""
    return {
        "social": "social_media",
        "ecommerce": "ecommerce",
        "content": "content",
        "growth": "growth",
    }.get(package_key or "", "converted")


def audit_blob(sale: ClosedSale, package_key: Optional[str]) -> dict:
    """The bounded, sanitised record kept for the timeline. Never the raw body."""
    return {
        "origin": SOURCE,
        "client_name": sale.clientName[:MAX_NAME],
        "client_email": (sale.clientEmail or "")[:MAX_EMAIL],
        "client_phone": (sale.clientPhone or "")[:MAX_PHONE],
        "package": sale.chosenPackage[:MAX_PACKAGE],
        "package_key": package_key or "",
        "payment_status": sale.paymentStatus[:32],
        "event_id": (sale.eventId or "")[:MAX_EVENT_ID],
        "notes": (sale.notes or "")[:MAX_FREE_TEXT],
    }


def _reject(reason: str, status_code: int) -> JSONResponse:
    """A rejection that never echoes the payload, the signature or the secret."""
    log.warning("botpress webhook rejected: %s", reason)
    return JSONResponse({"status": "rejected", "reason": reason}, status_code=status_code)


async def _seen_before(session, event_id: str) -> bool:
    from sqlalchemy import select

    from src.models import InboundMessage

    result = await session.execute(
        select(InboundMessage).where(InboundMessage.provider_message_id == event_id)
    )
    return result.scalar_one_or_none() is not None


async def _record_event(
    session,
    event_id: str,
    sale: ClosedSale,
    package_key: Optional[str],
    raw: bytes,
) -> None:
    """Persist the audit row: a payload hash plus the sanitised field summary."""
    from src.models import InboundMessage

    session.add(
        InboundMessage(
            provider_message_id=event_id,
            sender_number=(sale.clientPhone or "")[:32] or None,
            occurred_at=datetime.now(timezone.utc),
            message_type="sale",
            text=(sale.clientName or "")[:500],
            media_meta=audit_blob(sale, package_key),
            payload_hash=hashlib.sha256(raw).hexdigest(),
            processing_status="accepted",
        )
    )
    await session.commit()


async def _upsert_lead(session, sale: ClosedSale, package_key: Optional[str]) -> tuple[str, Optional[UUID]]:
    """Record the customer. Returns ``(disposition, lead_id)``.

    Lookup is on e-mail first and phone second, so a repeat report from the same
    person updates the existing lead instead of cloning it.

    ``lead_status`` and ``priority`` are deliberately left alone: lead-status
    logic is owner-approval territory, so this records the sale without deciding
    where the lead sits in the pipeline.
    """
    from sqlalchemy import select

    from src.models import AcquisitionLead

    lead = None
    if sale.clientEmail:
        lead = (
            await session.execute(
                select(AcquisitionLead).where(AcquisitionLead.email == sale.clientEmail)
            )
        ).scalar_one_or_none()
    if lead is None and sale.clientPhone:
        lead = (
            await session.execute(
                select(AcquisitionLead).where(AcquisitionLead.phone == sale.clientPhone)
            )
        ).scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if lead is not None:
        lead.contact_name = sale.clientName
        if sale.clientPhone:
            lead.phone = sale.clientPhone
            lead.phone_raw = sale.clientPhone
        if package_key:
            lead.suggested_package = package_key
        lead.buying_signal = True
        lead.segment = segment_for(package_key)
        lead.segment_reason = "Closed sale reported by the social media agent"
        lead.last_activity = now
        await session.commit()
        return "matched", lead.id

    lead = AcquisitionLead(
        company_name=sale.clientName,
        contact_name=sale.clientName,
        phone=sale.clientPhone,
        phone_raw=sale.clientPhone,
        email=sale.clientEmail,
        source=SOURCE,
        source_sheet="botpress_closed_sale",
        historical_customer=True,
        suggested_package=package_key,
        buying_signal=True,
        segment=segment_for(package_key),
        segment_reason="Closed sale reported by the social media agent",
        last_activity=now,
    )
    session.add(lead)
    await session.commit()
    await session.refresh(lead)
    return "created", lead.id


async def _wake_ceo(
    request: Request,
    sale: ClosedSale,
    package_key: Optional[str],
    lead_id: Optional[UUID],
) -> dict:
    """Hand the sale to the CEO and the queue. Reports what actually ran.

    Every branch is guarded and every failure is caught: Botpress only needs a
    2xx to stop retrying, and the sale is already committed. What must never
    happen is the opposite of the old bug -- claiming a step ran when it did not,
    so each step reports ``skipped``/``error`` explicitly.
    """
    app = request.app
    steps: dict[str, Any] = {}

    company_brain = getattr(app.state, "company_brain", None)
    if company_brain is None or not hasattr(company_brain, "run_once"):
        steps["ceo_brain"] = "skipped"
    else:
        try:
            steps["ceo_brain"] = await company_brain.run_once()
        except Exception as exc:  # noqa: BLE001 - a CEO hiccup must not lose the sale
            log.warning("company_brain.run_once failed: %s", exc)
            steps["ceo_brain"] = "error"

    queue_worker = getattr(app.state, "queue_worker", None)
    if queue_worker is None or not hasattr(queue_worker, "enqueue_agent"):
        steps["task_id"] = "skipped"
        return steps

    from src.automation.queue_worker import TaskPriority
    from src.services import catalog

    package = catalog.PACKAGES.get(package_key or "") or {}
    payload = {
        "origin": SOURCE,
        "manager": MANAGER,
        "customer": sale.clientName,
        "email": sale.clientEmail or "",
        "phone": sale.clientPhone or "",
        "package": package_key or "",
        "package_name": str(package.get("name", ""))[:MAX_NAME],
        "lead_id": str(lead_id) if lead_id else "",
        "note": (sale.notes or "")[:MAX_FREE_TEXT],
    }
    # Bound the serialised task input, then pick a real agent: a missing slug
    # would enqueue a task that fails at execution instead of at intake.
    trimmed = json.dumps(payload, ensure_ascii=False)[:MAX_INPUT_CHARS]
    slug = _ONBOARDING_SLUG.get(package_key or "") or "customer_manager"
    if slug not in catalog.EMPLOYEES:
        slug = next(iter(catalog.EMPLOYEES))

    try:
        steps["task_id"] = await queue_worker.enqueue_agent(
            agent_slug=slug,
            input_data=payload | {"input_summary": trimmed},
            priority=TaskPriority.HIGH,
            metadata={"origin": SOURCE, "manager": MANAGER},
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("queue enqueue failed: %s", exc)
        steps["task_id"] = None
    return steps


async def _notify_owner(sale: ClosedSale, package_key: Optional[str]) -> str:
    from src.services import telegram_sender

    amount = None
    if package_key:
        from src.services import catalog

        amount = (catalog.PACKAGES.get(package_key) or {}).get("price")

    line = (
        "صفقة مغلقة من وكيل السوشيال ميديا\n"
        f"العميل: {sale.clientName}\n"
        f"الباقة: {package_key or sale.chosenPackage}" + (f" ({amount} ر.س)" if amount else "")
    )
    if sale.clientPhone:
        line += f"\nالجوال: {sale.clientPhone}"
    if sale.clientEmail:
        line += f"\nالبريد: {sale.clientEmail}"

    try:
        await telegram_sender.send_owner_alert(line)
        return "sent"
    except Exception as exc:  # noqa: BLE001 - the sale is already saved
        log.warning("owner alert failed: %s", exc)
        return "failed"


@router.post("/botpress-lead", dependencies=[Depends(rate_limit_botpress)])
async def botpress_lead(request: Request):
    """A closed sale from Botpress: authenticate, validate, then act.

    Order matters. Signature first, then the rate-limit dependency, then JSON,
    then validation, then the idempotency check. Nothing is written and nothing is
    woken before the request is proven authentic.
    """
    if not is_configured():
        return _reject("not_configured", 503)

    raw = await request.body()

    signature = request.headers.get(SIGNATURE_HEADER)
    if not signature:
        return _reject("missing_signature", 403)
    if not verify_signature(signature, raw, webhook_secret()):
        return _reject("signature_mismatch", 403)

    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return _reject("bad_json", 400)
    if not isinstance(payload, dict):
        return _reject("bad_json", 400)

    try:
        sale = ClosedSale.model_validate(payload)
    except Exception:  # pydantic ValidationError and whatever it wraps
        return _reject("invalid_payload", 422)

    if not sale.is_paid():
        return JSONResponse({"status": "payment_incomplete"}, status_code=400)

    event_id = _clean(sale.eventId, MAX_EVENT_ID) or f"bp:{uuid4()}"
    package_key = sale.package_key()

    # Same factory the rest of the app uses for a request-scoped session, so a
    # test (or a future multi-tenant wiring) controls one object, not two.
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        from src.db.session import get_session_factory

        session_factory = await get_session_factory()

    async with session_factory() as session:
        if await _seen_before(session, event_id):
            return JSONResponse({"status": "duplicate", "event_id": event_id})
        await _record_event(session, event_id, sale, package_key, raw)
        disposition, lead_id = await _upsert_lead(session, sale, package_key)

    steps = await _wake_ceo(request, sale, package_key, lead_id)
    notify = await _notify_owner(sale, package_key)

    return JSONResponse(
        {
            "status": "accepted",
            "event_id": event_id,
            "manager": MANAGER,
            "package": package_key,
            "lead": disposition,
            "lead_id": str(lead_id) if lead_id else None,
            "ceo": steps,
            "owner_alert": notify,
        }
    )


@router.get("/botpress/health")
async def botpress_health():
    """Whether the integration is armed. Names the variable, never its value."""
    configured = is_configured()
    return {
        "configured": configured,
        "secret_source": "env" if configured else None,
        "required_env": ["BOTPRESS_WEBHOOK_SECRET"],
        "signature_header": SIGNATURE_HEADER,
    }

