"""Deterministic follow-up & next-action engine.

Pure functions only: no database, no network, no sending. Given an
``AcquisitionLead`` (ORM row or plain dict) it answers the five operator
questions:

  1. what happened        -> ``reason``
  2. what happens next    -> ``next_action``
  3. when                 -> ``due`` / ``due_at`` / ``due_label``
  4. what to say          -> :func:`prepare_follow_up` (reuses ``generate_message``)
  5. what is missing      -> ``missing``

The engine never invents dates or intent. When a follow-up cannot be
determined from an existing timestamp it returns ``UNSCHEDULED``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from src.services.lead_normalize import is_valid_email, is_valid_phone
from src.services.lead_outreach import generate_message

# --- Next-action vocabulary -------------------------------------------------
CONTACT_LEAD = "CONTACT_LEAD"
FOLLOW_UP = "FOLLOW_UP"
FOLLOW_UP_PROPOSAL = "FOLLOW_UP_PROPOSAL"
REVIEW_RESPONSE = "REVIEW_RESPONSE"
QUALIFY_LEAD = "QUALIFY_LEAD"
PREPARE_DEMO = "PREPARE_DEMO"
CUSTOMER_ONBOARDING = "CUSTOMER_ONBOARDING"
FIND_CONTACT_INFO = "FIND_CONTACT_INFO"
NO_ACTION = "NO_ACTION"

# --- Due states -------------------------------------------------------------
DUE = "DUE"
SCHEDULED = "SCHEDULED"
UNSCHEDULED = "UNSCHEDULED"
NOT_APPLICABLE = "NOT_APPLICABLE"

# Mirrors the operator's existing default in the lead workbench.
DEFAULT_FOLLOWUP_DAYS = 3

# Existing lifecycle meaning, preserved exactly (see src/models/crm.py).
_STATUS_NEXT_ACTION: dict[str, str] = {
    "NEW": CONTACT_LEAD,
    "READY": CONTACT_LEAD,
    "CONTACTED": FOLLOW_UP,
    "FOLLOW_UP": FOLLOW_UP,
    "REPLIED": REVIEW_RESPONSE,
    "INTERESTED": QUALIFY_LEAD,
    "DEMO": PREPARE_DEMO,
    "PROPOSAL": FOLLOW_UP_PROPOSAL,
    "WON": CUSTOMER_ONBOARDING,
    "LOST": NO_ACTION,
    "DO_NOT_CONTACT": NO_ACTION,
}

# Statuses that need a reachable channel before the next action makes sense.
_REQUIRES_REACHABILITY = {
    "NEW", "READY", "CONTACTED", "FOLLOW_UP",
    "REPLIED", "INTERESTED", "DEMO", "PROPOSAL",
}

# Statuses for which a missing next_followup_at means "follow-up not scheduled".
_NEEDS_SCHEDULED_FOLLOWUP = {"CONTACTED", "FOLLOW_UP", "PROPOSAL"}

_REASONS: dict[str, str] = {
    "NEW": "Imported lead, not yet prepared for outreach",
    "READY": "Prepared for first outreach; no contact recorded yet",
    "CONTACTED": "Initial outreach recorded with no response",
    "FOLLOW_UP": "A follow-up is scheduled; waiting on the operator",
    "REPLIED": "The lead replied; the response needs review",
    "INTERESTED": "The lead is interested; needs qualification",
    "DEMO": "At the demo stage; prepare the demo",
    "PROPOSAL": "Proposal sent; follow up on the proposal",
    "WON": "Deal won; start customer onboarding",
    "LOST": "Lead was lost; no further action",
    "DO_NOT_CONTACT": "Opted out; do not contact",
}

_RELEVANT_EVENT_TYPES = {"message_generated", "status_change", "followup_scheduled", "note"}


def _get(lead: Any, key: str, default: Any = None) -> Any:
    if isinstance(lead, dict):
        return lead.get(key, default)
    return getattr(lead, key, default)


def _as_dt(value: Any) -> Optional[datetime]:
    """Parse a timestamp defensively; naive values are treated as UTC."""
    dt: Optional[datetime]
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _due_label(due_state: str, due_at: Optional[datetime], now: datetime) -> Optional[str]:
    if due_state == DUE and due_at is not None:
        overdue = (now.date() - due_at.date()).days
        return "Due today" if overdue <= 0 else f"Overdue by {overdue} day(s)"
    if due_state == SCHEDULED and due_at is not None:
        ahead = (due_at.date() - now.date()).days
        if ahead <= 0:
            return "Due today"
        if ahead == 1:
            return "Due tomorrow"
        return f"Due in {ahead} days"
    if due_state == UNSCHEDULED:
        return "Follow-up not scheduled"
    return None


def compute_next_action(lead: Any, *, now: Optional[datetime] = None) -> dict:
    """Return the deterministic next action for a lead. Reads only, never writes."""
    now = now or datetime.now(timezone.utc)
    status = (_get(lead, "lead_status") or "NEW").strip() or "NEW"

    phone = _get(lead, "phone")
    email = _get(lead, "email")
    has_phone = is_valid_phone(phone)
    has_email = is_valid_email(email)
    reachable = has_phone or has_email

    missing = [name for name, ok in (("phone", has_phone), ("email", has_email)) if not ok]

    next_action = _STATUS_NEXT_ACTION.get(status, NO_ACTION)
    if status in _REQUIRES_REACHABILITY and not reachable:
        next_action = FIND_CONTACT_INFO

    followup_at = _as_dt(_get(lead, "next_followup_at"))
    if followup_at is not None:
        due_state = DUE if followup_at <= now else SCHEDULED
    elif status in _NEEDS_SCHEDULED_FOLLOWUP:
        due_state = UNSCHEDULED
    else:
        due_state = NOT_APPLICABLE

    if next_action == FIND_CONTACT_INFO:
        reason = "No reachable phone or email on file"
    else:
        reason = _REASONS.get(status, "Unrecognised lead status")

    return {
        "status": status,
        "next_action": next_action,
        "reason": reason,
        "due": due_state,
        "due_at": followup_at.isoformat() if followup_at else None,
        "due_label": _due_label(due_state, followup_at, now),
        "missing": missing,
        "is_follow_up": next_action in (FOLLOW_UP, FOLLOW_UP_PROPOSAL),
        "reachable": reachable,
    }


def _previous_relevant_event(events: Iterable[Any]) -> Optional[dict]:
    best: Optional[Any] = None
    best_at: Optional[datetime] = None
    for event in events or ():
        if (_get(event, "event_type") or "") not in _RELEVANT_EVENT_TYPES:
            continue
        created = _as_dt(_get(event, "created_at"))
        if created is None:
            # No timestamp: keep it only as a last-resort fallback.
            if best is None:
                best = event
            continue
        if best_at is None or created > best_at:
            best, best_at = event, created
    if best is None:
        return None
    created = _as_dt(_get(best, "created_at"))
    return {
        "event_type": _get(best, "event_type"),
        "created_at": created.isoformat() if created else None,
        "status_after": _get(best, "status_after"),
        "message": _get(best, "message"),
        "note": _get(best, "note"),
    }


def prepare_follow_up(
    lead: Any,
    events: Iterable[Any] = (),
    *,
    now: Optional[datetime] = None,
) -> dict:
    """Prepare (never send) the next operator action, reusing the existing draft generator."""
    base = compute_next_action(lead, now=now)

    prepared: dict = {"next_action": base}
    if base["next_action"] != NO_ACTION:
        prepared["draft"] = generate_message(lead)
    prepared["previous_event"] = _previous_relevant_event(events)
    prepared["suggested_timing"] = base["due_at"] if base["due"] in (DUE, SCHEDULED) else None
    prepared["suggested_days"] = DEFAULT_FOLLOWUP_DAYS if base["due"] == UNSCHEDULED else None
    return prepared
