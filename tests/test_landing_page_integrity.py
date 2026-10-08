"""Guards for the public landing page.

Rules enforced (Issue #1):
- no dead ``href="#'"`` CTAs on public pages,
- agent counts are rendered from the catalog (never hard-coded marketing numbers),
- server-side values exist so the page is meaningful without JavaScript,
- no fake social proof.
"""

from pathlib import Path
import re

import pytest

from src.services import catalog

TEMPLATES = Path(__file__).resolve().parents[1] / "src" / "web" / "templates"
LANDING = TEMPLATES / "landing.html"
PUBLIC_PAGES = ["landing.html", "sales_lead.html"]


def _read(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", PUBLIC_PAGES)
def test_no_dead_hash_ctas(name: str) -> None:
    body = _read(name)
    dead = [
        line.strip()
        for line in body.splitlines()
        if 'href="#"' in line
    ]
    assert not dead, f"{name} still contains dead links: {dead}"


def test_landing_agent_counts_come_from_context() -> None:
    body = _read("landing.html")
    assert "{{ agent_count }}" in body
    # hard-coded marketing number would drift from the real catalog again
    assert ">30<" not in body
    assert "30 agent" not in body.lower()


def test_landing_prices_come_from_catalog() -> None:
    body = _read("landing.html")
    for key in catalog.PACKAGES:
        assert f"{{{{ packages['{key}']" in body, f"plan {key} not rendered from catalog"


def test_plan_ctas_point_to_portal() -> None:
    body = _read("landing.html")
    for key in catalog.PACKAGES:
        assert f'href="/portal?pkg={key}"' in body, f"plan {key} has no working CTA"
    assert "js-order" not in body


def test_landing_has_about_and_no_fake_testimonials() -> None:
    body = _read("landing.html")
    assert 'id="about"' in body
    assert 'id="testimonials"' not in body
    for banned in ["أفضل متجر", "عميل سعيد", "تقييمات العملاء", "★★★★★"]:
        assert banned not in body


def test_landing_renders_values_without_javascript() -> None:
    body = _read("landing.html")
    assert 'id="rotor"></span>' not in body, "rotor must have server-rendered text"
    # The whole team section lives in an included partial and is rendered
    # server-side as divisions, so nothing on it depends on JavaScript:
    # no grid to hydrate, no spinner to wait for.
    divisions = _read("partials/_divisions.html")
    assert "dv-grid" in divisions
    assert "{% for d in divisions %}" in divisions
    assert "ag-card" not in divisions
    pulse = _read("partials/_pulse.html")
    assert 'id="pulse-live"' in pulse
    assert "fa-spinner" not in body and "fa-spinner" not in divisions


def test_agents_count_matches_catalog() -> None:
    assert len(catalog.EMPLOYEES) >= 30
    for key, pkg in catalog.PACKAGES.items():
        assert pkg["price"], key
        assert pkg["amount"] > 0, key
    for key, team in catalog.PACKAGE_TEAMS.items():
        assert len(team) == 5, f"plan {key} must open exactly 5 agents"
        for slug in team:
            assert slug in catalog.EMPLOYEES, slug


# ---------------------------------------------------------------------------
# The language switch must never hide the page itself
# ---------------------------------------------------------------------------

# Every template ships a rule that hides the inactive language. Written as a
# bare `[data-lang]` it also matches <body data-lang="ar">, and since the body
# is not a descendant of itself the usual `body[data-lang=...]` reset cannot
# bring it back. The result is a 200 response with a completely blank page.
# It shipped once and 404 tests did not catch it, because the HTML and the
# status code were both perfectly correct.
UNSCOPED_LANG_HIDE = re.compile(
    r"(?m)^\s*\[data-lang\]\s*(,[^{]*)?\{\s*display\s*:\s*none",
)


@pytest.mark.parametrize(
    "name",
    sorted(
        p.name
        for p in TEMPLATES.glob("*.html")
        if UNSCOPED_LANG_HIDE.search(p.read_text(encoding="utf-8"))
    ),
)
def test_no_unscoped_data_lang_display_none(name: str) -> None:
    """Fail loudly on any template that can hide <body> itself."""
    pytest.fail(
        f"{name} hides [data-lang] without a `body ` ancestor prefix, so it also "
        "matches <body data-lang=...> and renders a blank page. Scope it as "
        "`body [data-lang] { display: none }`."
    )


def test_landing_language_hide_rule_is_scoped() -> None:
    body = _read("landing.html")
    assert "body [data-lang]" in body, (
        "landing.html must scope the language hide rule to a descendant"
    )
    assert not UNSCOPED_LANG_HIDE.search(body), (
        "landing.html must scope the language hide rule to a descendant, "
        "otherwise <body data-lang=...> is hidden and the page renders blank"
    )


def test_body_tag_carries_data_lang_and_must_survive_it() -> None:
    """The body is the element that carries data-lang, so it is the at-risk one."""
    body = _read("landing.html")
    assert re.search(r"<body[^>]*\bdata-lang=", body), (
        "the landing body carries data-lang; the language hide rule must "
        "therefore be descendant-scoped or the whole page disappears"
    )
