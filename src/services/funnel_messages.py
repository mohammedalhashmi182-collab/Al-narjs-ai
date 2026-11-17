"""Message states for the revenue funnel.

An API success is ``accepted``. It is not a send and it is not delivery.
``sent`` requires a mailbox Message-ID. ``delivered`` requires a delivery
receipt on a message that was already sent. Draft and queued never count.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

SENT_STATES = frozenset({"sent", "delivered", "replied"})
OPEN_STATES = frozenset({"draft", "queued", "accepted", "failed"})

PROOF_API = "api_accept"
PROOF_MAILBOX = "mailbox_message_id"
PROOF_DELIVERY = "delivery_receipt"
PROOF_REPLY = "inbound_reply"
PROOF_NONE = "none"


class ProofError(ValueError):
    """The caller asked for a state the proof does not support."""


def resolve_state(
    *,
    requested: str,
    proof_kind: str,
    proof_ref: str | None,
    prior_was_sent: bool = False,
) -> str:
    """Return the state that this proof is allowed to record."""
    proof_kind = proof_kind or PROOF_NONE
    if requested in {"draft", "queued"}:
        if proof_kind not in {PROOF_NONE, ""}:
            raise ProofError("a draft or queued message is not a send")
        return requested
    if requested == "failed":
        return "failed"
    if proof_kind == PROOF_API:
        # A caller may ask for sent or delivered. The API response cannot grant either.
        return "accepted"
    if proof_kind == PROOF_MAILBOX:
        if not (proof_ref or "").strip():
            raise ProofError("sent requires a Message-ID")
        if requested == "delivered":
            raise ProofError("a Message-ID is not a delivery receipt")
        return "sent"
    if proof_kind == PROOF_DELIVERY:
        if not (proof_ref or "").strip():
            raise ProofError("delivery requires a receipt id")
        if not prior_was_sent:
            raise ProofError("delivery is not inferred before an independent send proof")
        return "delivered"
    if proof_kind == PROOF_REPLY:
        if not (proof_ref or "").strip():
            raise ProofError("a reply requires the inbound Message-ID")
        return "replied"
    raise ProofError("unknown proof")


def is_actually_sent(state: str, send_proof_ref: str | None) -> bool:
    """True only when a mailbox Message-ID (or a later state built on it) exists."""
    return bool(send_proof_ref) and state in SENT_STATES


def is_delivered(state: str, delivery_proof_ref: str | None) -> bool:
    return bool(delivery_proof_ref) and state in {"delivered", "replied"}


def legacy_api_ack_state(outbound_status: str | None) -> str:
    """How a pre-existing ``outbound_messages.status`` is read.

    Provider acknowledgement used to be stored as ``sent``. The funnel does
    not promote that to delivery. Queued and draft stay unsent.
    """
    status = (outbound_status or "").strip().lower()
    if status in {"draft", "queued", "awaiting_credential"}:
        return "queued" if status != "draft" else "draft"
    if status in {"failed", "error"}:
        return "failed"
    if status in {"sent", "acknowledged"}:
        return "accepted"
    return "queued"


def evidence_hash(text: str) -> str:
    return hashlib.sha256((text or "").strip().encode("utf-8")).hexdigest()


def utcnow() -> datetime:
    return datetime.now(UTC)
