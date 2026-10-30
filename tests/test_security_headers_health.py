"""Proxy https redirect, owner-only deep health, and Permissions-Policy."""
from fastapi.testclient import TestClient

from src.core.owner_auth import make_session_token
from src.main import SECURITY_HEADERS, app


def test_http_via_proxy_redirects_get_but_not_health_or_plain_requests():
    with TestClient(app, follow_redirects=False) as client:
        redirected = client.get("/ar/home", headers={"X-Forwarded-Proto": "http"})
        assert redirected.status_code == 301
        assert redirected.headers["location"].startswith("https://")
        assert redirected.headers["location"].endswith("/ar/home")

        plain = client.get("/ar/home")
        assert plain.status_code == 200

        probe = client.get("/health", headers={"X-Forwarded-Proto": "http"})
        assert probe.status_code == 200
        assert probe.json()["status"] == "healthy"


def test_deep_health_hides_integrations_from_everyone_but_the_owner():
    with TestClient(app) as client:
        public = client.get("/health/deep")
        assert public.status_code == 200
        assert public.json() == {"status": "healthy"}
        via_query = client.get("/health", params={"deep": "1"})
        assert via_query.json() == {"status": "healthy"}
        assert "db" not in via_query.json()

        client.cookies.set("narjis_owner", make_session_token())
        owned = client.get("/health/deep")
        body = owned.json()
        assert body["status"] == "healthy"
        assert "db" in body


def test_permissions_policy_is_set_and_the_voice_page_keeps_its_microphone():
    assert SECURITY_HEADERS["Permissions-Policy"] == (
        "camera=(), microphone=(), geolocation=(), payment=(self)"
    )
    with TestClient(app) as client:
        home = client.get("/ar/home")
        assert home.headers["permissions-policy"] == SECURITY_HEADERS["Permissions-Policy"]
        voice = client.get("/static/voice-live.html")
        assert voice.headers["permissions-policy"] == "microphone=(self)"
