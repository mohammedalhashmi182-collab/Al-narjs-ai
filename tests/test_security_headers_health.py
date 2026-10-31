"""Proxy https redirect, owner-only deep health, and Permissions-Policy."""
from fastapi.testclient import TestClient

from src.config.settings import settings
from src.core.owner_auth import make_session_token
from src.main import SECURITY_HEADERS, _https_redirect_origin, app


def _host_scope(host: str) -> dict:
    return {
        "type": "http",
        "method": "GET",
        "path": "/ar/home",
        "query_string": b"",
        "headers": [(b"host", host.encode("latin-1")), (b"x-forwarded-proto", b"http")],
    }


def test_http_via_proxy_redirects_get_but_not_health_or_plain_requests(monkeypatch):
    monkeypatch.setattr(settings, "public_base_url", None)
    with TestClient(app, follow_redirects=False) as client:
        redirected = client.get("/ar/home", headers={"X-Forwarded-Proto": "http"})
        assert redirected.status_code == 301
        # The test client's Host is not our site, so the redirect stays on the canonical origin.
        assert redirected.headers["location"] == "https://karmaai.online/ar/home"

        plain = client.get("/ar/home")
        assert plain.status_code == 200

        probe = client.get("/health", headers={"X-Forwarded-Proto": "http"})
        assert probe.status_code == 200
        assert probe.json()["status"] == "healthy"


def test_spoofed_host_never_redirects_to_an_outside_domain(monkeypatch):
    monkeypatch.setattr(settings, "public_base_url", None)
    spoofed = (
        "evil.example",
        "karmaai.online.evil.example",
        "notkarmaai.online",
        "evil.example:443",
        "karmaai.online@evil.example",
        "https://evil.example",
    )
    for host in spoofed:
        origin = _https_redirect_origin(_host_scope(host))
        assert origin == "https://karmaai.online", host
        assert "evil" not in origin

    with TestClient(app, follow_redirects=False) as client:
        response = client.get(
            "/ar/home",
            headers={"X-Forwarded-Proto": "http", "Host": "evil.example"},
        )
        assert response.status_code == 301
        assert response.headers["location"] == "https://karmaai.online/ar/home"
        assert "evil.example" not in response.headers["location"]


def test_public_base_url_builds_the_redirect_and_ignores_host(monkeypatch):
    monkeypatch.setattr(settings, "public_base_url", "http://karmaai.online/ignored")
    with TestClient(app, follow_redirects=False) as client:
        response = client.get(
            "/ar/pricing",
            params={"plan": "team"},
            headers={"X-Forwarded-Proto": "http", "Host": "evil.example"},
        )
        assert response.status_code == 301
        assert response.headers["location"] == "https://karmaai.online/ar/pricing?plan=team"
        assert "evil.example" not in response.headers["location"]


def test_allowlisted_host_is_used_only_when_public_base_url_is_unset(monkeypatch):
    monkeypatch.setattr(settings, "public_base_url", None)
    assert _https_redirect_origin(_host_scope("www.karmaai.online")) == "https://www.karmaai.online"
    assert _https_redirect_origin(_host_scope("KarmaAI.online:443")) == "https://karmaai.online"
    with TestClient(app, follow_redirects=False) as client:
        response = client.get(
            "/ar/home",
            headers={"X-Forwarded-Proto": "http", "Host": "www.karmaai.online"},
        )
        assert response.status_code == 301
        assert response.headers["location"] == "https://www.karmaai.online/ar/home"


def test_proxy_header_rules_still_apply(monkeypatch):
    monkeypatch.setattr(settings, "public_base_url", None)
    with TestClient(app, follow_redirects=False) as client:
        first_value = client.get(
            "/ar/home",
            headers={"X-Forwarded-Proto": "http, https", "Host": "karmaai.online"},
        )
        assert first_value.status_code == 301
        assert first_value.headers["location"] == "https://karmaai.online/ar/home"

        already_https = client.get(
            "/ar/home",
            headers={"X-Forwarded-Proto": "https", "Host": "evil.example"},
        )
        assert already_https.status_code == 200

        missing = client.get("/ar/home", headers={"Host": "evil.example"})
        assert missing.status_code == 200

        head = client.head(
            "/ar/home",
            headers={"X-Forwarded-Proto": "http", "Host": "evil.example"},
        )
        assert head.status_code == 301
        assert head.headers["location"] == "https://karmaai.online/ar/home"

        posted = client.post(
            "/ar/home",
            headers={"X-Forwarded-Proto": "http", "Host": "evil.example"},
        )
        assert posted.status_code != 301
        assert posted.headers.get("location") is None

        probe = client.get(
            "/health",
            headers={"X-Forwarded-Proto": "http", "Host": "evil.example"},
        )
        assert probe.status_code == 200


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
