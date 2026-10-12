"""The owner console is owner-only, and the public agent list stays public-safe.

Both halves matter: the console leaks leads, payments and model routing, while
`GET /api/agents` is deliberately public because the landing page counts the
live registry. That endpoint used to hand the public the internal fields too.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services import catalog

INTERNAL_FIELDS = ("default_model", "is_system", "employee_no", "questions")

# Everything the owner console reads. None of it may answer an anonymous call.
OWNER_ONLY_API = [
    ("GET", "/api/agents/orchestrator"),
    ("GET", "/api/executions"),
    ("GET", "/api/leads"),
    ("GET", "/api/owner/overview"),
    ("GET", "/api/owner/payments/readiness"),
    ("GET", "/api/owner/agents/status"),
    ("GET", "/api/queue/stats"),
    ("GET", "/api/schedules"),
    ("GET", "/api/workflows"),
]

OWNER_ONLY_PAGES = ["/", "/owner", "/agents"]


@pytest.fixture(scope="module")
def anon():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def owner():
    with TestClient(app) as c:
        c.post("/login", json={"password": "test-owner-password-not-for-production"})
        yield c


@pytest.mark.parametrize("method,path", OWNER_ONLY_API)
def test_owner_api_is_closed_to_anonymous_callers(anon: TestClient, method, path) -> None:
    r = anon.request(method, path)
    assert r.status_code == 401, f"{method} {path} answered {r.status_code} to the public"


@pytest.mark.parametrize("path", OWNER_ONLY_PAGES)
def test_owner_pages_redirect_anonymous_visitors_away(anon: TestClient, path) -> None:
    r = anon.get(path, follow_redirects=False)
    assert r.status_code in (302, 303, 307), f"{path} answered {r.status_code}"
    assert r.headers.get("location") in ("/home", "/login"), path


def test_public_agent_list_never_exposes_internal_fields(anon: TestClient) -> None:
    r = anon.get("/api/agents")
    assert r.status_code == 200
    agents = r.json()["agents"]
    assert agents, "the landing page counts this list, it must not be empty"
    for agent in agents:
        for field in INTERNAL_FIELDS:
            assert field not in agent, f"{agent['slug']} leaked {field}"


def test_public_agent_list_still_carries_what_the_public_pages_render(anon: TestClient) -> None:
    agents = anon.get("/api/agents").json()["agents"]
    for field in ("slug", "name", "title_ar", "title_en", "dept", "intro_ar", "category"):
        assert field in agents[0], f"{field} disappeared and a public page may need it"


def test_owner_still_gets_the_internal_fields(owner: TestClient) -> None:
    r = owner.get("/api/agents")
    assert r.status_code == 200
    agents = r.json()["agents"]
    for field in INTERNAL_FIELDS:
        assert field in agents[0], f"the console needs {field}"


def test_owner_agent_status_reports_a_rollup(owner: TestClient) -> None:
    r = owner.get("/api/owner/agents/status")
    assert r.status_code == 200
    body = r.json()

    summary = body["summary"]
    assert summary["total"] == len(catalog.EMPLOYEES)
    assert summary["total"] == summary["healthy"] + summary["failing"] + summary["idle"]
    assert len(body["agents"]) == summary["total"]

    for agent in body["agents"]:
        assert agent["state"] in ("healthy", "failing", "idle")
        # An idle agent has never run, so it must not claim a status or a date.
        if agent["state"] == "idle":
            assert agent["runs"] == 0
            assert agent["last_status"] is None
            assert agent["last_at"] is None
        assert isinstance(agent["provider_reachable"], bool)


def test_agent_status_never_leaks_a_key_in_a_provider_error(owner: TestClient) -> None:
    for probe in owner.get("/api/owner/agents/status").json()["providers"]:
        assert set(probe["detail"]) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_")


def test_pulse_stays_public_for_the_landing_page(anon: TestClient) -> None:
    assert anon.get("/api/pulse").status_code == 200
    assert anon.get("/api/payments/capabilities").status_code == 200