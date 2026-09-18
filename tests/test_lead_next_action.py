"""Tests for the deterministic follow-up & next-action engine.

Pure behaviour: no database, no network, no sending. Campaign #1 preservation
is asserted by proving the engine is read-only over lead data.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest

from src.services import lead_next_action as engine
from src.services.lead_next_action import compute_next_action, prepare_follow_up

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)


def lead(**overrides) -> dict:
    base = {
        "company_name": "شركة الاختبار",
        "phone": "0553078789",
        "email": None,
        "lead_status": "READY",
        "next_followup_at": None,
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("NEW", engine.CONTACT_LEAD),
        ("READY", engine.CONTACT_LEAD),
        ("CONTACTED", engine.FOLLOW_UP),
        ("FOLLOW_UP", engine.FOLLOW_UP),
        ("REPLIED", engine.REVIEW_RESPONSE),
        ("INTERESTED", engine.QUALIFY_LEAD),
        ("DEMO", engine.PREPARE_DEMO),
        ("PROPOSAL", engine.FOLLOW_UP_PROPOSAL),
        ("WON", engine.CUSTOMER_ONBOARDING),
        ("LOST", engine.NO_ACTION),
        ("DO_NOT_CONTACT", engine.NO_ACTION),
    ],
)
def test_status_maps_to_next_action(status, expected):
    assert compute_next_action(lead(lead_status=status), now=NOW)["next_action"] == expected


def test_contacted_without_schedule_is_unscheduled():
    result = compute_next_action(lead(lead_status="CONTACTED"), now=NOW)
    assert result["next_action"] == engine.FOLLOW_UP
    assert result["due"] == engine.UNSCHEDULED
    assert result["due_at"] is None
    assert result["due_label"] == "Follow-up not scheduled"


def test_followup_due_now_is_marked_due_today():
    result = compute_next_action(
        lead(lead_status="CONTACTED", next_followup_at=NOW - timedelta(hours=1)), now=NOW
    )
    assert result["due"] == engine.DUE
    assert result["due_label"] == "Due today"


def test_followup_in_past_labels_overdue():
    result = compute_next_action(
        lead(lead_status="CONTACTED", next_followup_at=NOW - timedelta(days=3)), now=NOW
    )
    assert result["due"] == engine.DUE
    assert result["due_label"] == "Overdue by 3 day(s)"


def test_future_followup_is_scheduled():
    result = compute_next_action(
        lead(lead_status="FOLLOW_UP", next_followup_at=NOW + timedelta(days=2)), now=NOW
    )
    assert result["due"] == engine.SCHEDULED
    assert result["due_label"] == "Due in 2 days"
    assert result["due_at"] is not None


def test_scheduled_without_timestamp_never_guesses():
    # Unknown/absent data must not invent a due date.
    result = compute_next_action(lead(lead_status="PROPOSAL", next_followup_at=None), now=NOW)
    assert result["due"] == engine.UNSCHEDULED
    assert result["due_at"] is None


def test_non_followup_status_has_no_due():
    result = compute_next_action(lead(lead_status="NEW"), now=NOW)
    assert result["due"] == engine.NOT_APPLICABLE
    assert result["due_label"] is None


def test_missing_contact_info_is_reported_and_blocks_outreach():
    result = compute_next_action(lead(lead_status="READY", phone=None, email=None), now=NOW)
    assert result["next_action"] == engine.FIND_CONTACT_INFO
    assert result["missing"] == ["phone", "email"]
    assert result["reachable"] is False


def test_valid_email_counts_as_reachable():
    result = compute_next_action(lead(phone=None, email="sales@example.com"), now=NOW)
    assert result["reachable"] is True
    assert result["missing"] == ["phone"]


def test_status_transition_updates_next_action():
    data = lead(lead_status="CONTACTED", next_followup_at=None)
    assert compute_next_action(data, now=NOW)["next_action"] == engine.FOLLOW_UP
    data["lead_status"] = "REPLIED"
    assert compute_next_action(data, now=NOW)["next_action"] == engine.REVIEW_RESPONSE


def test_prepare_follow_up_builds_draft_and_preserves_wa_link():
    data = lead(lead_status="CONTACTED", next_followup_at=NOW - timedelta(hours=2))
    prepared = prepare_follow_up(data, events=[], now=NOW)
    draft = prepared["draft"]
    assert draft["message"]
    assert draft["wa_link"] is not None
    assert "wa.me/966553078789" in draft["wa_link"]
    assert prepared["next_action"]["due"] == engine.DUE
    assert prepared["suggested_timing"] is not None


def test_prepare_follow_up_suggests_default_days_when_unscheduled():
    prepared = prepare_follow_up(lead(lead_status="PROPOSAL"), events=[], now=NOW)
    assert prepared["suggested_timing"] is None
    assert prepared["suggested_days"] == engine.DEFAULT_FOLLOWUP_DAYS


def test_prepare_follow_up_returns_previous_event():
    events = [
        {"event_type": "note", "created_at": NOW - timedelta(days=5), "note": "old"},
        {"event_type": "message_generated", "created_at": NOW - timedelta(days=1), "message": "hi"},
    ]
    prepared = prepare_follow_up(lead(lead_status="CONTACTED"), events=events, now=NOW)
    assert prepared["previous_event"]["event_type"] == "message_generated"


def test_no_action_has_no_draft():
    prepared = prepare_follow_up(lead(lead_status="LOST"), events=[], now=NOW)
    assert prepared["next_action"]["next_action"] == engine.NO_ACTION
    assert "draft" not in prepared


def test_engine_is_read_only_over_lead_data():
    data = lead(lead_status="CONTACTED", next_followup_at=NOW)
    before = dict(data)
    compute_next_action(data, now=NOW)
    prepare_follow_up(data, events=[], now=NOW)
    assert data == before


def test_engine_has_no_external_send_capability():
    source = inspect.getsource(engine)
    for forbidden in ("requests", "httpx", "smtplib", "urlopen", "send_message", "/send"):
        assert forbidden not in source
