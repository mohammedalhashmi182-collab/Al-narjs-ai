"""Regression coverage for owner-session expiry and timestamp validation."""

import base64
import json

from src.core import owner_auth


def _signed_owner_token(timestamp):
    payload = {"t": timestamp, "r": "owner"}
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    return f"{raw}.{owner_auth._sign(raw)}"


def test_owner_token_rejects_future_issue_time(monkeypatch):
    monkeypatch.setattr(owner_auth.time, "time", lambda: 1_000_000)
    assert owner_auth.verify_session_token(_signed_owner_token(1_000_001)) is False


def test_owner_token_expiration_edges(monkeypatch):
    monkeypatch.setattr(owner_auth.time, "time", lambda: 1_000_000)
    assert owner_auth.verify_session_token(_signed_owner_token(1_000_000)) is True
    assert owner_auth.verify_session_token(_signed_owner_token(1_000_000 - 12 * 3600)) is True
    assert owner_auth.verify_session_token(_signed_owner_token(1_000_000 - 12 * 3600 - 1)) is False


def test_owner_token_rejects_malformed_timestamps(monkeypatch):
    monkeypatch.setattr(owner_auth.time, "time", lambda: 1_000_000)
    for timestamp in (None, "1000000", True, 1.5):
        assert owner_auth.verify_session_token(_signed_owner_token(timestamp)) is False
