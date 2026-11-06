from pathlib import Path

from fastapi.testclient import TestClient


def test_public_whatsapp_contact():
    from src.main import app
    with TestClient(app) as client:
        for path in ("/ar/home", "/en/home", "/ar/contact", "/en/contact", "/ar/voice", "/en/voice"):
            response = client.get(path, follow_redirects=True)
            assert response.status_code == 200, path
            assert "https://wa.me/966552978753" in response.text, path
            assert "0540799266" not in response.text, path
            assert "+966540799266" not in response.text, path
