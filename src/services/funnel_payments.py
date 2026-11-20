"""Link a payment to a lead only with an authenticated identifier.

Anonymous ``lead_id`` values and email/phone guesses are ignored. A link is
written for a signed lead token or for an owner session, and only when the
payment is not already linked to a different lead. Amount, currency and status
are left untouched. Existing payment rows are not rewritten by this module
unless the caller passes a valid token or an owner flag for that same request.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from src.core.portal_auth import make_lead_token, read_lead_token
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PaymentLinkError(ValueError):
    pass


async def link_payment(
    session,
    payment,
    *,
    token: str | None = None,
    owner: bool = False,
    owner_lead_id: UUID | None = None,
) -> dict:
    """Attach ``payment.lead_id`` when the proof is a token or an owner session."""
    from src.models import AcquisitionLead
    from src.models.funnel import FunnelEvent, PaymentLeadLink

    existing = (
        await session.execute(select(PaymentLeadLink).where(PaymentLeadLink.payment_id == payment.id))
    ).scalar_one_or_none()
    if existing is not None:
        return {
            "linked": True,
            "deduplicated": True,
            "lead_id": str(existing.lead_id),
            "method": existing.method,
        }

    method = None
    lead_id = None
    evidence = None
    if token:
        claims = read_lead_token(token)
        if not claims or not claims.get("lead"):
            return {"linked": False, "reason": "token_rejected"}
        try:
            lead_id = UUID(str(claims["lead"]))
        except ValueError:
            return {"linked": False, "reason": "token_rejected"}
        method = "signed_token"
        evidence = str(claims.get("jti") or "token")[:255]
    elif owner and owner_lead_id is not None:
        lead_id = owner_lead_id
        method = "owner_session"
        evidence = "owner_session"

    if lead_id is None or method is None:
        return {"linked": False, "reason": "no_authenticated_identifier"}

    lead = await session.get(AcquisitionLead, lead_id)
    if lead is None:
        return {"linked": False, "reason": "unknown_lead"}
    if payment.lead_id and payment.lead_id != lead_id:
        return {"linked": False, "reason": "already_linked"}

    payment.lead_id = lead_id
    session.add(PaymentLeadLink(
        payment_id=payment.id,
        lead_id=lead_id,
        method=method,
        evidence_ref=evidence or method,
    ))
    session.add(FunnelEvent(
        lead_id=lead_id,
        event_type="payment_linked",
        idempotency_key=f"payment-link:{payment.id}",
        evidence_ref=str(payment.id),
        actor="funnel",
        channel="payment",
        payload={"method": method},
    ))
    await session.flush()
    logger.info("Linked payment %s to lead %s method=%s", payment.id, lead_id, method)
    return {"linked": True, "deduplicated": False, "lead_id": str(lead_id), "method": method}


async def open_sandbox_payment(session_factory, lead_id: UUID, *, package: str = "bidaya") -> dict:
    """Create a local paid row for tests. Refuses production. Does not call Moyasar."""
    from src.config.settings import settings
    from src.services.payments import create_payment

    if (settings.environment or "").lower() == "production":
        raise PaymentLinkError("sandbox payments are refused in production")
    token = make_lead_token(lead_id)
    async with session_factory() as session:
        payment = await create_payment(
            session,
            package,
            founding=False,
            lead_id=None,
        )
        linked = await link_payment(session, payment, token=token)
        if not linked.get("linked"):
            raise PaymentLinkError(linked.get("reason") or "link_failed")
        payment.status = "paid"
        payment.gateway = "sandbox"
        await session.commit()
        payment_id = payment.id
        amount = payment.amount
    return {
        "payment_id": str(payment_id),
        "lead_id": str(lead_id),
        "status": "paid",
        "gateway": "sandbox",
        "amount": amount,
        "linked": True,
    }
