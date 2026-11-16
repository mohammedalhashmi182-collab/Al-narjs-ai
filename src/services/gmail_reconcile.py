"""Reconcile mail that was sent from the business mailbox outside this app.

Least privilege: the only acceptable OAuth scope is ``gmail.readonly``.
Send, modify, compose and full mail access are refused. This module does not
open a socket. ``fetch_headers`` raises until the owner enables a read-only
run outside production. Tests and the fixture script call ``ingest_snapshot``.

A Message-ID is the idempotency key. Outbound mail from our mailbox is
``sent`` because the mailbox itself is the proof, not an API response.
Inbound mail is a reply only when ``In-Reply-To`` matches a message we stored.
Unknown recipients are counted and not turned into new leads.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime

from src.services.funnel_identity import canonical_email, find_by_any
from src.services.funnel_record import record_message, record_reply
from src.services.funnel_messages import PROOF_MAILBOX
from src.utils.logger import get_logger

logger = get_logger(__name__)

READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
FORBIDDEN_SCOPES = frozenset({
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://mail.google.com/",
})
PUBLIC_MAILBOX = "alnarjisai@gmail.com"


class LeastPrivilegeError(PermissionError):
    pass


class ReconcileDisabled(RuntimeError):
    pass


@dataclass(frozen=True)
class MailSnapshot:
    message_id: str
    from_addr: str
    to_addrs: tuple[str, ...] = ()
    in_reply_to: str | None = None
    occurred_at: datetime | None = None
    text: str = ""
    labels: tuple[str, ...] = field(default_factory=tuple)


def assert_least_privilege(scopes: list[str] | tuple[str, ...]) -> None:
    """Accept readonly alone. Anything that can send or change mail is refused."""
    cleaned = [str(item).strip() for item in scopes if str(item).strip()]
    if cleaned != [READONLY_SCOPE]:
        raise LeastPrivilegeError("Gmail reconciliation allows only gmail.readonly")
    if any(item in FORBIDDEN_SCOPES or item.rsplit("/", 1)[-1] in {"send", "modify", "compose"} for item in cleaned):
        raise LeastPrivilegeError("Gmail reconciliation allows only gmail.readonly")


def mailbox_addresses() -> set[str]:
    found = {PUBLIC_MAILBOX}
    try:
        from src.config.settings import settings

        for value in (settings.smtp_from, settings.smtp_username, getattr(settings, "mail_reply_to", None)):
            text = canonical_email(str(value or ""))
            if text:
                found.add(text)
    except Exception:  # noqa: BLE001 - settings must not block a fixture ingest
        pass
    return found


def fetch_headers() -> list[MailSnapshot]:
    """Network entry point. Disabled. Do not point this at production."""
    if os.environ.get("ENVIRONMENT", "").lower() == "production":
        raise ReconcileDisabled("refusing to read Gmail from production")
    if os.environ.get("GMAIL_RECONCILE_ENABLED", "").strip().lower() not in {"1", "true", "yes"}:
        raise ReconcileDisabled(
            "Gmail reconciliation is disabled. It never sends mail. "
            "Enable GMAIL_RECONCILE_ENABLED only with gmail.readonly, outside production."
        )
    scopes = [part.strip() for part in os.environ.get("GMAIL_RECONCILE_SCOPES", READONLY_SCOPE).split(",") if part.strip()]
    assert_least_privilege(scopes)
    raise ReconcileDisabled(
        "No Gmail client is bundled. Pass a local fixture to ingest_snapshot. This process does not contact Google."
    )


def refuse_reason(environment: str | None, argv: list[str]) -> str | None:
    """Why the operator script must exit before touching a database."""
    if (environment or "").lower() == "production":
        return "refusing: production"
    if "--fixture" not in argv or argv.index("--fixture") == len(argv) - 1:
        return "refusing: pass --fixture with a local file. This script does not contact Gmail."
    return None


def _others(message: MailSnapshot, ours: set[str]) -> list[str]:
    sender = canonical_email(message.from_addr)
    recipients = [canonical_email(item) for item in message.to_addrs]
    recipients = [item for item in recipients if item]
    if sender in ours:
        return [item for item in recipients if item not in ours]
    if sender and sender not in ours:
        return [sender]
    return []


async def ingest_snapshot(session, messages: list[MailSnapshot]) -> dict:
    """Idempotent ingest. Writes rows. Does not send and does not call Gmail."""
    ours = mailbox_addresses()
    messages = sorted(
        messages,
        key=lambda item: 0 if canonical_email(item.from_addr) in ours else 1,
    )
    report = {
        "seen": len(messages),
        "ingested": 0,
        "deduplicated": 0,
        "linked": 0,
        "unmatched": 0,
        "replies": 0,
        "opt_outs": 0,
    }
    for message in messages:
        sender = canonical_email(message.from_addr)
        outbound = sender in ours
        others = _others(message, ours)
        lead = None
        for addr in others:
            lead = await find_by_any(session, email=addr)
            if lead is not None:
                break
        lead_id = lead.id if lead is not None else None
        if outbound:
            result = await record_message(
                session,
                lead_id=lead_id,
                channel="email",
                direction="outbound",
                requested="sent",
                proof_kind=PROOF_MAILBOX,
                proof_ref=message.message_id,
                in_reply_to=message.in_reply_to,
                occurred_at=message.occurred_at,
                enforce_consent=False,
            )
        else:
            result = await record_reply(
                session,
                evidence_ref=message.message_id,
                text=message.text,
                lead_id=lead_id,
                in_reply_to=message.in_reply_to,
                occurred_at=message.occurred_at,
            )
            report["replies"] += 0 if result.get("deduplicated") else 1
            if result.get("classification") == "opt_out" and not result.get("deduplicated"):
                report["opt_outs"] += 1
        if result.get("deduplicated"):
            report["deduplicated"] += 1
        else:
            report["ingested"] += 1
        if lead_id is None:
            report["unmatched"] += 0 if result.get("deduplicated") else 1
        elif not result.get("deduplicated"):
            report["linked"] += 1
    logger.info(
        "Gmail snapshot ingested seen=%s ingested=%s deduplicated=%s linked=%s unmatched=%s",
        report["seen"], report["ingested"], report["deduplicated"], report["linked"], report["unmatched"],
    )
    return report
