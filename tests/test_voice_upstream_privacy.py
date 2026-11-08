"""Regression guard: do not expose untrusted voice-provider errors to visitors."""
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "src/web/static/js/voice-live-app.js").read_text(encoding="utf-8")


def test_upstream_error_details_not_logged_or_rendered():
    assert 'console.warn("voice session error"' not in SOURCE
    assert 'String(detail).slice' not in SOURCE
    assert 'add(T.down, "sys")' in SOURCE


def test_websocket_close_reason_not_shown_to_visitor():
    assert 'event.reason' not in SOURCE
    assert 'return T.dropped + (code ? " (" + code + ")" : "");' in SOURCE
