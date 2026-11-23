"""Regression checks: WhatsApp must not call a retired Meta Graph API version."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_whatsapp_sender_uses_supported_version():
    code = (ROOT / "src/services/whatsapp_sender.py").read_text(encoding="utf-8")
    assert 'API_URL = "https://graph.facebook.com/v26.0"' in code
    assert "graph.facebook.com/v20.0" not in code


def test_readonly_credentials_validator_avoids_expired_versions():
    code = (ROOT / "scripts/verify_whatsapp_credentials.py").read_text(encoding="utf-8")
    assert 'DEFAULT_VERSION = "v26.0"' in code
    assert 'VERSION_FALLBACKS = ("v25.0", "v24.0", "v23.0")' in code
    assert '"v20.0"' not in code
    assert '"v19.0"' not in code


def test_tenant_reply_uses_shared_meta_sender_endpoint():
    code = (ROOT / "src/services/tenant_reply.py").read_text(encoding="utf-8")
    assert "from .whatsapp_sender import API_URL" in code
