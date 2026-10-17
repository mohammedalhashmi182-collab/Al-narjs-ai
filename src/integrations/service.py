"""Tenant-facing store tools: order status, product lookup, and policy answers."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from src.integrations import limits
from src.integrations.config import enabled
from src.integrations.intent import classify
from src.integrations.phones import same_phone
from src.integrations.provider import OrderHit, ProductHit, StoreApiError
from src.integrations.tokens import apply_token_response, ensure_fresh, force_refresh, wipe
from src.models.store_integration import StoreConnection, StorePolicy, StoreWebhookEvent

log = logging.getLogger(__name__)

_GREET = "أهلًا بك 🌿\n"
_TAIL = "\n\nإذا عندك سؤال ثاني أنا حاضر."
_POLICY_LABELS = {"shipping": "الشحن والتوصيل", "returns": "الاسترجاع", "payment": "الدفع"}
# Same sentence for a missing order, a phone mismatch, and a masked marketplace
# phone, so a guess cannot tell whether the order exists.
_UNVERIFIED = _GREET + "لم أتمكن من مطابقة هذا الطلب مع رقمك. تأكد من رقم الطلب، أو اطلب موظفًا للمساعدة." + _TAIL


@dataclass
class StoreTurn:
    kind: str  # reply | handoff
    reason: Optional[str]
    body: str
    meta: dict


def _reply(body: str, tool: str, **extra) -> StoreTurn:
    meta = {"store_tool": tool, **extra}
    return StoreTurn("reply", None, body, meta)


def _handoff(reason: str, tool: str) -> StoreTurn:
    return StoreTurn("handoff", reason, "", {"store_tool": tool})


async def connections(session, project_id: UUID, *, active_only: bool = True) -> list[StoreConnection]:
    stmt = select(StoreConnection).where(StoreConnection.project_id == project_id)
    if active_only:
        stmt = stmt.where(StoreConnection.status == "active")
    return list((await session.execute(stmt)).scalars())


async def policy_row(session, project_id: UUID) -> Optional[StorePolicy]:
    return await session.get(StorePolicy, project_id)


def policy_public(row: Optional[StorePolicy]) -> dict:
    return {
        "shipping": (row.shipping if row else None) or "",
        "returns": (row.returns_text if row else None) or "",
        "payment": (row.payment if row else None) or "",
    }


def clean_policy_field(value: object) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("invalid")
    text = value.replace("\x00", "").strip()
    if len(text) > 1500:
        raise ValueError("too_long")
    return text or None


async def save_policy(session, project_id: UUID, fields: dict) -> dict:
    row = await policy_row(session, project_id)
    if row is None:
        row = StorePolicy(project_id=project_id)
        session.add(row)
    if "shipping" in fields:
        row.shipping = clean_policy_field(fields.get("shipping"))
    if "returns" in fields:
        row.returns_text = clean_policy_field(fields.get("returns"))
    if "payment" in fields:
        row.payment = clean_policy_field(fields.get("payment"))
    await session.commit()
    return policy_public(row)


async def disconnect(session, project_id: UUID, platform: str) -> bool:
    rows = [row for row in await connections(session, project_id, active_only=False) if row.platform == platform]
    if not rows:
        return False
    for row in rows:
        wipe(row)
    await session.commit()
    return True


def _client(platform: str, access: str, authorization: Optional[str]):
    if platform == "salla":
        from src.integrations.salla.client import SallaClient

        return SallaClient(access)
    from src.integrations.zid.client import ZidClient

    if not authorization:
        raise StoreApiError("missing_authorization", 401)
    return ZidClient(access, authorization)


async def _with_retry(session, row, call):
    access, authorization = await ensure_fresh(session, row)
    try:
        return await call(_client(row.platform, access, authorization))
    except StoreApiError as exc:
        if exc.status != 401:
            raise
        access, authorization = await force_refresh(session, row)
        return await call(_client(row.platform, access, authorization))


async def answer_store_question(session, project, contact: str, text: str) -> Optional[StoreTurn]:
    if not enabled() or project is None:
        return None
    kind = classify(text)
    if kind is None:
        return None
    tool, arg = kind
    if tool == "policy":
        return await _policy(session, project.id, arg)
    rows = await connections(session, project.id)
    if not rows:
        return None
    if tool == "order":
        return await _order(session, project.id, contact, rows, arg)
    return await _products(session, project.id, rows, arg)


async def _policy(session, project_id: UUID, topics: tuple[str, ...]) -> StoreTurn:
    row = await policy_row(session, project_id)
    parts: list[str] = []
    for topic in topics:
        value = ""
        if row is not None:
            value = (row.shipping if topic == "shipping" else row.returns_text if topic == "returns" else row.payment) or ""
        if not value.strip():
            return _handoff("no_policy", "store_policy")
        parts.append(f"{_POLICY_LABELS[topic]}:\n{value.strip()}")
    return _reply(_GREET + "\n\n".join(parts) + _TAIL, "store_policy", topics=list(topics))


async def _order(session, project_id, contact, rows, reference: Optional[str]) -> StoreTurn:
    if not reference:
        return _reply(
            _GREET + "أرسل رقم الطلب كما هو في رسالة التأكيد، وأتحقق من حالته على رقمك هذا." + _TAIL,
            "order_status", need_reference=True,
        )
    allowed, _ = limits.order_lookups.check(f"{project_id}:{contact}")
    if not allowed:
        log.info("store order lookup limited project=%s", project_id)
        return _handoff("rate_limited", "order_status")
    hits: list[OrderHit] = []
    failures = 0
    for row in rows:
        try:
            hit = await _with_retry(session, row, lambda client, ref=reference: client.fetch_order(ref))
        except StoreApiError as exc:
            failures += 1
            log.warning("store order lookup failed project=%s platform=%s status=%s", project_id, row.platform, exc.status)
            continue
        if hit is not None:
            hits.append(hit)
    for hit in hits:
        if hit.masked or not hit.status or not same_phone(hit.phone, contact):
            continue
        body = _GREET + f"طلب {hit.reference[:40]}: حالته «{hit.status[:80]}»." + _TAIL
        return _reply(body, "order_status", verified=True, platform=hit.platform)
    if hits:
        return _reply(_UNVERIFIED, "order_status", verified=False, outcome="order_unverified")
    if failures and failures == len(rows):
        return _reply(_UNVERIFIED, "order_status", verified=False, outcome="store_unavailable")
    return _reply(_UNVERIFIED, "order_status", verified=False, outcome="order_not_found")


async def _products(session, project_id, rows, query: str) -> Optional[StoreTurn]:
    allowed, _ = limits.product_lookups.check(f"product:{project_id}")
    if not allowed:
        return None
    found: list[ProductHit] = []
    for row in rows:
        try:
            found.extend(await _with_retry(session, row, lambda client, q=query: client.search_products(q)))
        except StoreApiError as exc:
            log.warning("store product lookup failed project=%s platform=%s status=%s", project_id, row.platform, exc.status)
    if not found:
        return None
    lines = []
    for item in found[:3]:
        stock = "متوفر" if item.available else "غير متوفر"
        price = f" — {item.price} ريال" if item.price else ""
        lines.append(f"• {item.name}{price} — {stock}")
    return _reply(_GREET + "\n".join(lines) + _TAIL, "product_lookup", count=len(found[:3]))


async def claim_event(session, platform: str, raw: bytes, payload: dict) -> bool:
    """Reserve the raw-body hash. False means this delivery was already handled."""
    name = ""
    merchant = None
    if platform == "salla":
        from src.integrations.salla.webhooks import event_name, merchant_ids

        name = event_name(payload)
        ids = merchant_ids(payload)
        merchant = next(iter(ids), None)
    else:
        from src.integrations.zid.webhooks import event_name, merchant_ids

        name = event_name(payload)
        ids = merchant_ids(payload)
        merchant = next(iter(ids), None)
    session.add(StoreWebhookEvent(
        platform=platform, dedupe_key=hashlib.sha256(raw).hexdigest(), event_name=name or "unknown", merchant_id=merchant,
    ))
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        return False
    return True


async def apply_webhook(session, platform: str, payload: dict) -> str:
    if platform == "salla":
        from src.integrations.salla.webhooks import apply
    else:
        from src.integrations.zid.webhooks import apply
    return await apply(session, payload)


async def linked_elsewhere(session, project_id: UUID, platform: str, merchant_id: str, store_ref: Optional[str]) -> bool:
    ids = [item for item in (merchant_id, store_ref) if item]
    if not ids:
        return False
    stmt = select(StoreConnection).where(
        StoreConnection.platform == platform,
        StoreConnection.status == "active",
        StoreConnection.project_id != project_id,
        or_(StoreConnection.merchant_id.in_(ids), StoreConnection.store_ref.in_(ids)),
    )
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def save_install(session, project_id: UUID, platform: str, token_body: dict, info) -> None:
    if await linked_elsewhere(session, project_id, platform, info.merchant_id, info.store_ref):
        raise StoreApiError("store_already_linked", 409)
    row = (await session.execute(select(StoreConnection).where(
        StoreConnection.project_id == project_id, StoreConnection.platform == platform,
    ))).scalar_one_or_none()
    if row is None:
        row = StoreConnection(project_id=project_id, platform=platform, status="active")
        session.add(row)
    row.merchant_id = info.merchant_id or None
    row.store_ref = info.store_ref
    row.store_name = (info.name or "")[:255] or None
    apply_token_response(row, token_body)
    await session.commit()
    log.info("store installed platform=%s project=%s merchant=%s", platform, project_id, row.merchant_id or "")
