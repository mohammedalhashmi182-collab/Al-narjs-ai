"""The live voice page gets the ElevenLabs/blob CSP sources; no other page does."""

from src.main import (
    CONTENT_SECURITY_POLICY,
    VOICE_LIVE_CSP,
    VOICE_LIVE_PATHS,
)


def test_voice_live_csp_adds_only_needed_sources():
    assert "wss://api.elevenlabs.io" in VOICE_LIVE_CSP
    assert "https://api.elevenlabs.io" in VOICE_LIVE_CSP
    assert "script-src 'self' 'unsafe-inline' blob:" in VOICE_LIVE_CSP
    assert "worker-src 'self' blob:" in VOICE_LIVE_CSP
    assert "media-src 'self' blob: mediastream:" in VOICE_LIVE_CSP
    assert "frame-ancestors 'none'" in VOICE_LIVE_CSP
    assert "object-src 'none'" in VOICE_LIVE_CSP


def test_site_wide_csp_is_unchanged():
    assert "elevenlabs" not in CONTENT_SECURITY_POLICY
    assert "blob:" not in CONTENT_SECURITY_POLICY.split("img-src")[0]
    assert "worker-src" not in CONTENT_SECURITY_POLICY
    assert VOICE_LIVE_PATHS == {"/static/voice-live.html"}
