"""The live voice page may open a socket to xAI. No other page may."""

from src.main import (
    CONTENT_SECURITY_POLICY,
    VOICE_LIVE_CSP,
    VOICE_LIVE_PATHS,
)


def test_voice_live_csp_adds_only_the_xai_socket():
    assert "wss://api.x.ai" in VOICE_LIVE_CSP
    assert "https://api.x.ai" in VOICE_LIVE_CSP
    assert "elevenlabs" not in VOICE_LIVE_CSP
    assert "script-src 'self' 'unsafe-inline' blob:" not in VOICE_LIVE_CSP
    assert "worker-src" not in VOICE_LIVE_CSP


def test_site_wide_csp_is_unchanged():
    assert "elevenlabs" not in CONTENT_SECURITY_POLICY
    assert "api.x.ai" not in CONTENT_SECURITY_POLICY
    assert "blob:" not in CONTENT_SECURITY_POLICY.split("img-src")[0]
    assert "worker-src" not in CONTENT_SECURITY_POLICY
    assert VOICE_LIVE_PATHS == {
        "/static/voice-live.html",
        "/voice",
        "/ar/voice",
        "/en/voice",
    }
