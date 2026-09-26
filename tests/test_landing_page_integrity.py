"""Guards for the public landing page.

Rules enforced (Issue #1):
- no dead ``href="#'"`` CTAs on public pages,
- agent counts are rendered from the catalog (never hard-coded marketing numbers),
- server-side values exist so the page is meaningful without JavaScript,
- no fake social proof.
"""

from pathlib import Path

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
    assert 'id="agents-grid">' in body
    # first agents must be pre-rendered, not only a spinner
    grid_start = body.index('id="agents-grid"')
    grid_slice = body[grid_start:grid_start + 4000]
    assert "ag-card" in grid_slice
    assert "fa-spinner" not in grid_slice


def test_agents_count_matches_catalog() -> None:
    assert len(catalog.EMPLOYEES) >= 30
    for key, pkg in catalog.PACKAGES.items():
        assert pkg["price"], key
        assert pkg["amount"] > 0, key
    for key, team in catalog.PACKAGE_TEAMS.items():
        assert len(team) == 5, f"plan {key} must open exactly 5 agents"
        for slug in team:
            assert slug in catalog.EMPLOYEES, slug
