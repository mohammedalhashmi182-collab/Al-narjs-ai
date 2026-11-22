"""Leftover hosts (karmaai.online and *.onrender.com) 301 to https://alnarjisai.com."""
from fastapi.testclient import TestClient

from src.config.settings import settings
from src.main import app
from src.services.public_status import status_host_home


def test_old_domain_redirects_with_path_and_query(monkeypatch):
    monkeypatch.setattr(settings, "domain", "alnarjisai.com")
    with TestClient(app, follow_redirects=False) as client:
        for host in ("karmaai.online", "www.karmaai.online", "n9.karmaai.online", "KarmaAI.online:443"):
            r = client.get("/ar/pricing?plan=team&src=ad", headers={"Host": host})
            assert r.status_code == 301, host
            assert r.headers["location"] == "https://alnarjisai.com/ar/pricing?plan=team&src=ad"

        head = client.head("/", headers={"Host": "karmaai.online"})
        assert head.status_code == 301
        assert head.headers["location"] == "https://alnarjisai.com/"

        encoded = client.get("/ar/%D9%85%D8%AF", headers={"Host": "www.karmaai.online"})
        assert encoded.headers["location"] == "https://alnarjisai.com/ar/%D9%85%D8%AF"

        # Plain http on the old host goes straight to the new https origin.
        hop = client.get("/ar/home", headers={"Host": "karmaai.online", "X-Forwarded-Proto": "http"})
        assert hop.headers["location"] == "https://alnarjisai.com/ar/home"


def test_old_domain_keeps_health_webhooks_and_posts(monkeypatch):
    monkeypatch.setattr(settings, "domain", "alnarjisai.com")
    with TestClient(app, follow_redirects=False) as client:
        assert client.get("/health", headers={"Host": "karmaai.online"}).status_code == 200
        hook = client.get("/webhooks/stores/salla/callback", headers={"Host": "karmaai.online"})
        assert hook.status_code != 301
        post = client.post("/api/consult", json={}, headers={"Host": "karmaai.online"})
        assert post.status_code != 301




def test_render_fallback_host_redirects_with_path_and_query(monkeypatch):
    monkeypatch.setattr(settings, "domain", "alnarjisai.com")
    with TestClient(app, follow_redirects=False) as client:
        for host in (
            "al-narjs-ai-1.onrender.com",
            "al-narjs-ai-1-pr-12.onrender.com",
            "al-narjs-ai-1.onrender.com:443",
        ):
            r = client.get("/ar/pricing?plan=team&src=ad", headers={"Host": host})
            assert r.status_code == 301, host
            assert r.headers["location"] == "https://alnarjisai.com/ar/pricing?plan=team&src=ad"

        head = client.head("/", headers={"Host": "al-narjs-ai-1.onrender.com"})
        assert head.status_code == 301
        assert head.headers["location"] == "https://alnarjisai.com/"

        encoded = client.get("/ar/%D9%85%D8%AF", headers={"Host": "al-narjs-ai-1.onrender.com"})
        assert encoded.headers["location"] == "https://alnarjisai.com/ar/%D9%85%D8%AF"

        hop = client.get(
            "/ar/home",
            headers={"Host": "al-narjs-ai-1.onrender.com", "X-Forwarded-Proto": "http"},
        )
        assert hop.headers["location"] == "https://alnarjisai.com/ar/home"


def test_render_fallback_host_keeps_health_webhooks_and_posts(monkeypatch):
    monkeypatch.setattr(settings, "domain", "alnarjisai.com")
    with TestClient(app, follow_redirects=False) as client:
        host = {"Host": "al-narjs-ai-1.onrender.com"}
        assert client.get("/health", headers=host).status_code == 200
        hook = client.get("/webhooks/stores/salla/callback", headers=host)
        assert hook.status_code != 301
        telegram = client.post("/webhooks/telegram", json={}, headers=host)
        assert telegram.status_code != 301
        moyasar = client.post("/webhooks/moyasar", json={}, headers=host)
        assert moyasar.status_code != 301
        post = client.post("/api/consult", json={}, headers=host)
        assert post.status_code != 301


def test_new_domain_and_other_hosts_are_not_redirected(monkeypatch):
    monkeypatch.setattr(settings, "domain", "alnarjisai.com")
    with TestClient(app, follow_redirects=False) as client:
        for host in ("alnarjisai.com", "notkarmaai.online", "karmaai.online.evil.example", "al-narjs-ai-1.onrender.com.evil.example", "notonrender.com"):
            r = client.get("/ar/home", headers={"Host": host})
            assert r.status_code == 200, host


def test_redirect_waits_until_domain_setting_moves(monkeypatch):
    monkeypatch.setattr(settings, "domain", "karmaai.online")
    with TestClient(app, follow_redirects=False) as client:
        r = client.get("/ar/home", headers={"Host": "karmaai.online"})
        assert r.status_code == 200
        # The Render hostname still 301s; it is not the previous custom domain.
        render = client.get("/ar/home", headers={"Host": "al-narjs-ai-1.onrender.com"})
        assert render.status_code == 301
        assert render.headers["location"] == "https://alnarjisai.com/ar/home"


def test_both_status_hosts_open_the_status_page():
    assert status_host_home("status.alnarjisai.com", "/") == "/ar/status"
    assert status_host_home("status.karmaai.online", "/en") == "/en/status"
