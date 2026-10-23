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
PUBLIC_PAGES = [str(p.relative_to(TEMPLATES)) for p in TEMPLATES.rglob("*.html")]


def _read(name: str) -> str:
    body = (TEMPLATES / name).read_text(encoding="utf-8")
    # the pricing section is shared with /pricing as a partial
    return body.replace('{% include "partials/_pricing_section.html" %}', (TEMPLATES / "partials" / "_pricing_section.html").read_text(encoding="utf-8"))


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
    # tiers are looped from the catalog-built ``plans`` context, never typed in
    assert "{% for plan in plans %}" in body
    assert "plan.price" in body and "plan.total_halalas" in body
    for pkg in catalog.PACKAGES.values():
        assert f"{int(pkg['price']):,}" not in body, "a price was hard-coded in the template"


def test_plan_order_ctas_point_to_the_payment_portal() -> None:
    """Every tier CTA opens the existing checkout (portal) with that tier preselected."""
    body = _read("landing.html")
    assert 'href="/portal?pkg={{ plan.key }}"' in body
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
        assert team[0] == catalog.CEO_SLUG, f"plan {key} must be led by the CEO"
        assert len(team) == catalog.plan_agent_count(key) + 1, f"plan {key} team != its allowance"
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
    # v2 renders one language server-side; if a hide rule ever returns it
    # must still be scoped to descendants of body.
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


def test_public_contact_identity_is_consistent() -> None:
    for path in TEMPLATES.rglob('*.html'):
        body = path.read_text(encoding='utf-8')
        assert 'Al-Narjs AI' not in body, path
        assert 'aimerchantvault.77@gmail.com' not in body, path
        for address in re.findall(r'mailto:([^"\s?]+)', body):
            assert address == 'AlNarjisai@gmail.com', path


def test_single_how_section_and_explicit_sample_disclosure() -> None:
    body = _read('landing.html')
    assert body.count('id="how"') == 1
    assert body.index('id="how"') < body.index('id="pricing"')
    for name in ['landing.html', 'consult.html', 'portal.html']:
        assert 'يُدار بواسطة أحمد عبدالله الزهراني' in _read(name)
        assert 'وثيقة عمل حر رقم FL-272182297' in _read(name)
        assert 'Operated by أحمد عبدالله الزهراني' in _read(name)
