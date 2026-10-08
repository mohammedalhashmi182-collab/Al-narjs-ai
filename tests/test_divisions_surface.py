"""Divisions-first team framing and the live ops room.

The public landing page used to advertise a raw roster ("35 agents") as the
headline and render a JS-loaded grid of individual agent cards. The owner asked
for a smaller, more credible number. Shrinking it by editing a template would
have been a lie, so the honest version is implemented instead:

* the site leads with **divisions** (a department-level unit), derived at import
  time from ``catalog.EMPLOYEES`` so it can never drift from the real roster;
* the roster stays one click away inside each division card, so nothing is
  hidden from a visitor who wants the detail;
* a "live ops room" reads **aggregate counts only** from the database, and is
  allowed to show nothing at all rather than a number nobody can verify.

These tests lock all three properties, because the whole point of the change is
that the smaller number on the page is still a true number.
"""

from __future__ import annotations

import html
import re

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services import catalog

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
DIVISIONS_PARTIAL = REPO_ROOT / "src" / "web" / "templates" / "partials" / "_divisions.html"
PULSE_PARTIAL = REPO_ROOT / "src" / "web" / "templates" / "partials" / "_pulse.html"
LANDING = REPO_ROOT / "src" / "web" / "templates" / "landing.html"
LUXURY_CSS = REPO_ROOT / "src" / "web" / "static" / "css" / "narjis-luxury.css"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# --------------------------------------------------------------------------
# catalog: the division view is derived, never authored
# --------------------------------------------------------------------------


def test_divisions_are_derived_from_the_roster() -> None:
    assert catalog.DIVISIONS, "no divisions built"
    assert catalog.AGENT_COUNT == len(catalog.EMPLOYEES)


def test_every_agent_belongs_to_exactly_one_division() -> None:
    seen: list[str] = []
    for division in catalog.DIVISIONS:
        seen.extend(division["agents"])
    assert sorted(seen) == sorted(catalog.EMPLOYEES), "division coverage is not exact"
    assert len(seen) == len(set(seen)), "an agent is listed in two divisions"


def test_division_counts_match_their_rosters() -> None:
    for division in catalog.DIVISIONS:
        assert division["count"] == len(division["agents"])
        assert division["count"] > 0, f"empty division: {division['slug']}"


def test_division_count_is_smaller_than_the_roster() -> None:
    """The whole point: the headline number is structurally smaller."""
    assert catalog.DIVISION_COUNT < catalog.AGENT_COUNT


def test_every_division_has_both_languages_and_a_blurb() -> None:
    for division in catalog.DIVISIONS:
        assert division["name_ar"].strip()
        assert division["name_en"].strip()
        assert division["blurb_ar"].strip()
        assert division["blurb_en"].strip()
        assert not ARABIC.search(division["name_en"]), "English division name leaked Arabic"
        assert not ARABIC.search(division["blurb_en"]), "English blurb leaked Arabic"


ARABIC = re.compile(r"[\u0600-\u06ff]")


def test_division_lookups_resolve() -> None:
    first = catalog.DIVISIONS[0]
    assert catalog.get_division(first["slug"])["name_ar"] == first["name_ar"]
    assert catalog.get_division("not-a-division") is None
    member = first["agents"][0]
    assert catalog.divisions_for_agent(member)["slug"] == first["slug"]
    assert catalog.divisions_for_agent("not-an-agent") is None


# --------------------------------------------------------------------------
# templates: counts come from the context, not from a literal
# --------------------------------------------------------------------------


def test_divisions_partial_uses_no_hardcoded_numbers() -> None:
    markup = DIVISIONS_PARTIAL.read_text(encoding="utf-8")
    assert "{{ division_count }}" in markup
    assert "{{ agent_count }}" in markup
    # the retired roster headline must not sneak back in
    assert re.search(r"(?<![0-9])35(?![0-9])", markup) is None


def test_divisions_partial_renders_from_context_not_live_registry() -> None:
    markup = DIVISIONS_PARTIAL.read_text(encoding="utf-8")
    assert "{% for d in divisions %}" in markup
    assert "{{ d.name_ar }}" in markup and "{{ d.name_en }}" in markup
    assert "{{ d.count }}" in markup


def test_luxury_css_covers_the_new_components() -> None:
    css = LUXURY_CSS.read_text(encoding="utf-8")
    for selector in (".dv-grid", ".dv-card", ".dv-roster", ".pulse-live", ".pulse-item"):
        assert selector in css, f"missing style for {selector}"


def test_luxury_css_respects_reduced_motion() -> None:
    css = LUXURY_CSS.read_text(encoding="utf-8")
    assert "prefers-reduced-motion: reduce" in css


def test_pulse_partial_is_server_rendered_and_honest() -> None:
    markup = PULSE_PARTIAL.read_text(encoding="utf-8")
    assert 'id="pulse-live"' in markup
    assert 'data-pulse="leads_received"' in markup
    # metrics that need the database must not be pre-filled with a number
    assert 'data-pulse="leads_received">—<' in markup
    assert 'data-pulse="projects">—<' in markup
    assert "Capability" not in markup


# --------------------------------------------------------------------------
# the rendered page
# --------------------------------------------------------------------------


def test_home_renders_every_division(client: TestClient) -> None:
    r = client.get("/home")
    assert r.status_code == 200
    for division in catalog.DIVISIONS:
        assert f'data-division="{division["slug"]}"' in r.text
        assert division["name_ar"] in r.text
        # Jinja escapes the markup, so compare against the escaped form
        assert html.escape(division["name_en"]) in r.text


def test_home_renders_the_division_count_headline(client: TestClient) -> None:
    r = client.get("/home")
    assert r.text.count('class="dv-card"') == catalog.DIVISION_COUNT
    assert "أقسام متخصصة" in r.text


def test_home_shows_the_whole_roster_behind_the_divisions(client: TestClient) -> None:
    """A smaller headline must not hide the real team."""
    r = client.get("/home")
    assert r.text.count("/ai-agent/") >= catalog.AGENT_COUNT


def test_old_roster_grid_is_gone(client: TestClient) -> None:
    landing = LANDING.read_text(encoding="utf-8")
    assert 'id="agents-grid"' not in landing
    assert 'id="filters"' not in landing
    r = client.get("/home")
    assert 'id="agents-grid"' not in r.text


def test_dead_js_hooks_are_removed(client: TestClient) -> None:
    """The grid renderer used to null-deref once #agents changed shape."""
    landing = LANDING.read_text(encoding="utf-8")
    assert "renderAgents" not in landing
    assert "document.getElementById('filters')" not in landing
    r = client.get("/home")
    assert "renderAgents" not in r.text


def test_home_renders_the_ops_room(client: TestClient) -> None:
    r = client.get("/home")
    assert 'id="pulse-live"' in r.text
    for key in ("divisions", "agents", "plans", "leads_received", "projects"):
        assert f'data-pulse="{key}"' in r.text


def test_no_dead_ctas_in_the_new_partials() -> None:
    for path in (DIVISIONS_PARTIAL, PULSE_PARTIAL):
        markup = path.read_text(encoding="utf-8")
        assert 'href="#"' not in markup, f"dead CTA in {path.name}"


# --------------------------------------------------------------------------
# /api/pulse: aggregates only, degrades honestly
# --------------------------------------------------------------------------


def test_pulse_reports_catalog_truth(client: TestClient) -> None:
    r = client.get("/api/pulse")
    assert r.status_code == 200
    payload = r.json()
    assert payload["divisions"] == catalog.DIVISION_COUNT
    assert payload["agents"] == catalog.AGENT_COUNT
    assert payload["plans"] == len(catalog.PACKAGES)


def test_pulse_never_leaks_rows_or_identities(client: TestClient) -> None:
    payload = client.get("/api/pulse").json()
    assert set(payload) == {
        "divisions",
        "agents",
        "plans",
        "leads_received",
        "projects",
    }
    for value in payload.values():
        assert value is None or isinstance(value, int)


def test_pulse_metrics_are_null_when_the_database_is_unreachable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.db.session import get_session_factory

    class _Boom:
        async def __aenter__(self):
            raise RuntimeError("database is down")

        async def __aexit__(self, *exc):
            return False

    async def _factory():
        return _Boom

    monkeypatch.setattr("src.main.get_session_factory", _factory, raising=False)
    monkeypatch.setattr("src.db.session.get_session_factory", _factory)
    monkeypatch.setattr(app.state, "public_pulse_cache", None, raising=False)

    payload = client.get("/api/pulse").json()
    assert payload["leads_received"] is None
    assert payload["projects"] is None
    # capability numbers still answer, because they come from the catalogue
    assert payload["divisions"] == catalog.DIVISION_COUNT


def test_pulse_is_cached_briefly(client: TestClient) -> None:
    first = client.get("/api/pulse").json()
    second = client.get("/api/pulse").json()
    assert first == second