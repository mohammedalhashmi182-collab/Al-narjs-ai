"""Guards for the conversion sections added to the landing page.

Covers ``#proof`` (trust without invented claims), ``#needs`` (the deterministic
"what does your business need" picker), ``#why`` (the honest comparison) and the
one-primary-CTA rule.

Rules enforced:
- the picker is deterministic: fixed bilingual data, no network call,
- every plan and every agent it names really exists in ``src/services/catalog.py``,
- the page copy cannot drift from the catalogue job titles,
- Arabic is first, never glued to its English twin, and carries no Latin leakage,
- the comparison stays neutral: no named competitor, no invented proof,
- the individual CV service is de-emphasised in the UI but never removed,
- each stage keeps exactly one gold primary action.
"""

from pathlib import Path
import re

import pytest

from src.services import catalog

TEMPLATES = Path(__file__).resolve().parents[1] / "src" / "web" / "templates"
LANDING = TEMPLATES / "landing.html"

ARABIC = re.compile(r"[\u0600-\u06FF]")
LATIN = re.compile(r"[A-Za-z]")

ALLOWED_LATIN_IN_AR = {
    "AI", "AG", "JavaScript", "Telegram", "SEO", "A", "B", "EN", "Narjis", "Al",
}
# Words that would make the comparison an attack rather than a comparison.
BANNED_IN_WHY = {
    "chatgpt", "claude", "gemini", "copilot", "midjourney", "openai", "anthropic",
    "google", "upwork", "mostaql", "خمسات", "مستقل", "مستقلين",
}

# The CV agent is intentionally demoted from the visible Growth team, so the
# page says nothing about hiring. It must still exist in the catalogue.
DEMOTED_SLUG = "cv_writer"


def _body() -> str:
    return LANDING.read_text(encoding="utf-8")


def _section(anchor: str, end: str) -> str:
    body = _body()
    return body[body.index(anchor):body.index(end, body.index(anchor))]


def _stage(section_id: str) -> str:
    """Markup of exactly one section, up to the next section comment."""
    body = _body()
    start = body.index(section_id)
    nxt = body.index("<!-- ====================", start)
    return body[start:nxt]


def _proof() -> str:
    return _section('id="proof"', "<!-- ==================== DEMO")


def _needs_markup() -> str:
    return _section('id="needs"', "<!-- ==================== WHY AL-NARJIS")


def _why() -> str:
    return _section('id="why"', "<!-- ==================== FEATURES")


def _needs_js() -> str:
    body = _body()
    return body[body.index("var NEEDS ="):body.index("var allAgents")]


def _pricing_markup() -> str:
    body = _body()
    return body[body.index('id="pricing"'):body.index("<!-- ==================== FIRST WEEK")]


# --------------------------------------------------------------------------
# the picker stays deterministic and offline
# --------------------------------------------------------------------------

def test_picker_has_no_network_call() -> None:
    js = _needs_js()
    for banned in ("fetch(", "XMLHttpRequest", "axios", "await ", "navigator.sendBeacon"):
        assert banned not in js, f"the picker must stay deterministic, found {banned!r}"


def test_picker_offers_six_problems() -> None:
    js = _needs_js()
    keys = re.findall(r"^\s{20}(\w+): \{$", js, re.M)
    assert len(keys) == 6, f"expected exactly 6 business problems, got {keys}"


def test_every_problem_maps_to_a_real_plan() -> None:
    js = _needs_js()
    plans = re.findall(r"plan: '(\w+)'", js)
    assert plans, "no problem maps to a plan"
    for plan in plans:
        assert plan in catalog.PACKAGES, f"{plan!r} is not a catalogue package"


def test_every_problem_is_bilingual() -> None:
    js = _needs_js()
    blocks = re.findall(r"label: \{ ar: '([^']+)', en: '([^']+)' \}", js)
    assert len(blocks) == 6, "each of the 6 problems needs an Arabic and English label"
    for ar, en in blocks:
        assert ARABIC.search(ar), f"Arabic label missing Arabic script: {ar!r}"
        assert LATIN.search(en), f"English label missing Latin script: {en!r}"
        assert ar == ar.strip() and en == en.strip()


def test_picker_never_invents_an_agent() -> None:
    js = _needs_js()
    slugs = set(re.findall(r"agents: \[([^\]]*)\]", js)[0].replace("'", "").replace(" ", "").split(","))
    slugs |= set(re.findall(r"agents: \[([^\]]*)\]", "".join(re.findall(r"agents: \[([^\]]*)\]", js))))
    for slug in slugs:
        if not slug:
            continue
        assert slug in catalog.EMPLOYEES, f"{slug!r} is not a catalogue agent"


# --------------------------------------------------------------------------
# the page cannot drift from the catalogue
# --------------------------------------------------------------------------

def test_picker_titles_match_the_catalogue() -> None:
    js = _needs_js()
    rows = re.findall(r"(\w+): \{ ar: '([^']+)', en: '([^']+)' \},", js[js.index("var AGENT_TITLE"):])
    assert rows, "AGENT_TITLE map not found"
    for slug, ar, en in rows:
        assert slug in catalog.EMPLOYEES, f"{slug!r} is not a catalogue agent"
        emp = catalog.EMPLOYEES[slug]
        assert ar == emp["title_ar"], f"{slug}: page says {ar!r}, catalogue says {emp['title_ar']!r}"
        assert en == emp["title_en"], f"{slug}: page says {en!r}, catalogue says {emp['title_en']!r}"


def test_picker_rosters_match_the_catalogue_teams() -> None:
    js = _needs_js()
    block = js[js.index("var PLAN_TEAM"):js.index("}", js.index("var PLAN_TEAM"))]
    rosters = dict(re.findall(r"(\w+): \[([^\]]*)\]", block))
    assert set(rosters) == set(catalog.PACKAGE_TEAMS), "picker rosters must cover every plan"
    for plan, raw in rosters.items():
        shown = [s.strip().strip("'") for s in raw.split(",") if s.strip()]
        real = catalog.PACKAGE_TEAMS[plan]
        omitted = set(real) - set(shown)
        assert not set(shown) - set(real), f"{plan}: the page shows agents the plan does not have"
        # the demoted agent is the only one allowed to be missing
        assert omitted <= {DEMOTED_SLUG}, f"{plan}: unexpected missing agents {omitted}"


# --------------------------------------------------------------------------
# Arabic first, no glued translation, no Latin leakage
# --------------------------------------------------------------------------

AR_SPAN = re.compile(r'<span data-lang="ar"[^>]*>((?:(?!</span>).)*)</span>')
EN_TAIL = re.compile(r'\s*<span (?:data-lang="en" data-inline|class="en-nm")>')


def _ar_spans(markup: str) -> list[tuple[int, str]]:
    lines = markup.splitlines()
    out: list[tuple[int, str]] = []
    for i, line in enumerate(lines, 1):
        for m in AR_SPAN.finditer(line):
            if not EN_TAIL.match(line, m.end()):
                out.append((i, m.group(0)))
    return out


def test_new_sections_are_fully_bilingual() -> None:
    for name, markup in (("proof", _proof()), ("needs", _needs_markup()), ("why", _why())):
        unpaired = [x for x in _ar_spans(markup) if "<b>" not in x[1] and "<br" not in x[1]]
        assert not unpaired, f"#{name} has Arabic copy with no English counterpart: {unpaired}"


def test_new_sections_have_no_latin_in_arabic_copy() -> None:
    for name, markup in (("proof", _proof()), ("needs", _needs_markup()), ("why", _why())):
        for lineno, line in enumerate(markup.splitlines(), 1):
            for m in re.finditer(r'data-lang="ar"[^>]*>([^<]*)<', line):
                value = m.group(1)
                if not ARABIC.search(value):
                    continue
                for token in re.findall(r"[A-Za-z][A-Za-z0-9/&-]*", value):
                    assert token in ALLOWED_LATIN_IN_AR, (
                        f"#{name} line {lineno}: Latin {token!r} leaked into Arabic copy: {value!r}"
                    )


def test_new_sections_have_no_foreign_script() -> None:
    for name, markup in (("proof", _proof()), ("needs", _needs_markup()), ("why", _why())):
        for ch in markup:
            if not ch.isalpha():
                continue
            code = ord(ch)
            if 0x0600 <= code <= 0x06FF or ch.isascii():
                continue
            raise AssertionError(f"#{name}: non-Arabic, non-Latin letter {ch!r} U+{code:04X}")


# --------------------------------------------------------------------------
# the trust section never invents proof
# --------------------------------------------------------------------------

def test_proof_never_invents_social_proof() -> None:
    proof = _proof()
    for banned in ("عميل سعيد", "testimonial", "شركاء", "شريك نجاح", "رائع!", "آراء العملاء"):
        assert banned not in proof, f"#proof must not show invented proof: {banned!r}"
    # the honest disclaimer has to stay: no logos, no ratings, no numbers we cannot back
    assert ("لا نعرض" in proof) or ("لا ننشر" in proof), (
        "#proof must keep the disclaimer that unverified proof is not shown"
    )
    # and it must not assert a business status we cannot verify
    for banned in ("لم نبدأ", "لم نبدأ العمل", "not started working", "no clients yet"):
        assert banned not in proof, (
            f"#proof must not assert an unverified business status: {banned!r}"
        )


def test_proof_points_at_real_pages() -> None:
    body = _body()
    for anchor in ('href="#demo"', 'href="#how"'):
        assert anchor in _proof(), f"#proof must link to {anchor}"
        assert anchor in body


def test_no_roi_or_revenue_claims() -> None:
    for name, markup in (("proof", _proof()), ("needs", _needs_markup()), ("why", _why())):
        for banned in ("ROI", "عائد", "تضاعف", "مضمون", "ضمان", "نضمن"):
            assert banned not in markup, f"#{name} must not promise a financial outcome: {banned!r}"


# --------------------------------------------------------------------------
# the comparison stays neutral
# --------------------------------------------------------------------------

def test_why_compares_the_four_expected_options() -> None:
    why = _why()
    for col in ("أداة AI عامة", "مستقل", "فريق موظفين", "النرجس"):
        assert col in why, f"#why is missing the {col!r} column"


def test_why_covers_every_criterion_the_owner_asked_for() -> None:
    why = _why()
    for row in ("طريقة العمل", "التخصص", "التكرار", "العربية أولاً", "مخرجات جاهزة", "فريق مركزي"):
        assert row in why, f"#why is missing the {row!r} row"


def test_why_names_no_competitor() -> None:
    why = _why().lower()
    for banned in BANNED_IN_WHY:
        if banned == "مستقل":
            continue  # "مستقل" is a category column, allowed as a header only
        assert banned not in why, f"#why must not attack a named competitor: {banned!r}"


def test_why_keeps_its_honest_caveat() -> None:
    assert "تكفيك" in _why(), "#why must admit when a general tool is enough"


# --------------------------------------------------------------------------
# positioning: the CV service is demoted, not deleted
# --------------------------------------------------------------------------

def test_cv_is_demoted_from_the_visible_growth_team() -> None:
    pricing = _pricing_markup()
    assert DEMOTED_SLUG in catalog.PACKAGE_TEAMS["growth"], "catalogue precondition"
    # the CV agent must not be one of the visible team chips
    assert "كاتب سيرة ذاتية" not in pricing, "the CV agent is still a visible team chip"
    assert "CV Writer" not in pricing, "the CV agent is still a visible team chip"
    # but it is disclosed honestly, and still ships in the plan
    assert DEMOTED_SLUG in catalog.PACKAGE_TEAMS["growth"]
    assert "السيرة الذاتية" in pricing, "the Growth plan must still disclose the CV agent"


def test_growth_card_shows_every_other_team_member() -> None:
    pricing = _pricing_markup()
    for slug in catalog.PACKAGE_TEAMS["growth"]:
        if slug == DEMOTED_SLUG:
            continue
        assert catalog.EMPLOYEES[slug]["title_ar"] in pricing, (
            f"the Growth card hides {slug!r} without saying so"
        )


# --------------------------------------------------------------------------
# one gold primary action per stage
# --------------------------------------------------------------------------

def _blocks(markup: str, block_class: str) -> list[str]:
    """Every ``div`` whose class list contains ``block_class``, balanced to its own close."""
    out: list[str] = []
    opener = re.compile(r'<div class="([^"]*)">')
    divs = re.compile(r"<div\b[^>]*>|</div>")
    for m in opener.finditer(markup):
        # exact class token only, so `why-cta` never matches `why-cta-row`
        if block_class not in m.group(1).split():
            continue
        depth = 1
        for tag in divs.finditer(markup, m.end()):
            depth += 1 if tag.group(0).startswith("<div") else -1
            if depth == 0:
                out.append(markup[m.end():tag.start()])
                break
    return out


@pytest.mark.parametrize("block_class", ["next-step", "why-cta", "pcmp-close"])
def test_each_conversion_block_has_exactly_one_gold_cta(block_class: str) -> None:
    blocks = _blocks(_body(), block_class)
    assert blocks, f"the {block_class!r} block disappeared"
    for block in blocks:
        gold = re.findall(r'class="btn btn-gold"', block)
        assert len(gold) == 1, f"{block_class} has {len(gold)} gold CTAs, expected exactly one"


def test_the_demo_panel_keeps_the_run_control_as_its_only_gold() -> None:
    demo = _stage('id="demo"')
    panel = demo[:demo.index("next-step")]
    gold = re.findall(r'class="btn btn-gold[^"]*"', panel)
    assert len(gold) == 1, f"the demo panel has {len(gold)} gold buttons, expected only the run control"
    assert "demo-run" in gold[0], f"the demo panel's gold button is not the run control: {gold[0]}"


def test_the_trust_section_pushes_the_funnel_forward_without_buying() -> None:
    proof = _stage('id="proof"')
    assert "btn-gold" not in proof, "#proof is a trust section and must not contain a gold CTA"
    assert proof.count('href="#demo"') >= 1, "#proof must push the visitor into the demo"


def test_the_needs_picker_ends_in_one_gold_cta() -> None:
    js = _needs_js()
    tail = js[js.index("function ndRender()"):]
    assert tail.count("btn-gold") == 1, (
        f"the picker must end in one gold CTA, found {tail.count('btn-gold')}"
    )
    # the gold action must be the one that carries the chosen plan
    gold_line = next(ln for ln in tail.splitlines() if "btn-gold" in ln)
    assert "/portal?pkg=" in gold_line, f"the gold CTA ignores the chosen plan: {gold_line.strip()}"
    assert "d.plan" in gold_line, f"the gold CTA does not use the selected plan key: {gold_line.strip()}"
    assert "/consult" in tail, "the picker must keep the free consult next to the gold CTA"


def test_the_picker_never_rebuilds_its_own_buttons() -> None:
    """Re-rendering on click detaches the buttons, so only the first pick ever registers."""
    js = _needs_js()
    handler = js[js.index("ndPick.addEventListener"):js.index("ndRenderPick();")]
    assert "ndRenderPick()" not in handler, (
        "the click handler must not re-render the picker; it would detach the buttons"
    )
    assert "ndMarkPicked()" in handler, "the click handler must mark the picked button in place"
    assert "function ndMarkPicked" in js, "ndMarkPicked is missing"


# --------------------------------------------------------------------------
# responsive: a grid track may never blow the page out
# --------------------------------------------------------------------------

def test_hero_tracks_cannot_blow_out_the_viewport() -> None:
    """``1fr`` has an automatic min-content minimum: the console panel used to
    push the whole page 58px wider than a 320px phone. ``minmax(0, ...)`` is the fix."""
    body = _body()
    rule = re.search(r"\.hero \.inner\{[^}]*\}", body)
    assert rule, ".hero .inner rule not found"
    tracks = re.findall(r"grid-template-columns:([^;]+)", rule.group(0))
    assert tracks, ".hero .inner declares no grid-template-columns"
    for value in tracks:
        for track in value.split():
            if track.endswith("fr") or track.endswith("fr)"):
                assert track.startswith("minmax(0,"), (
                    f".hero .inner track {track!r} can overflow a narrow phone; use minmax(0, ...)"
                )


def test_multi_column_grids_use_minmax_zero_tracks() -> None:
    """Same class of bug: any responsive grid must clamp its automatic minimum."""
    body = _body()
    bad = []
    for m in re.finditer(r"([.\w-]+)\{[^}]*grid-template-columns:([^;}]+)", body):
        sel, value = m.group(1), m.group(2)
        if "minmax(0" in value or "auto-fit" in value or "auto-fill" in value:
            continue
        for track in value.split():
            bare = track.strip("()")
            if re.fullmatch(r"[\d.]+fr", bare) and bare != "1fr":
                bad.append(f"{sel} -> {track}")
            elif re.fullmatch(r"1fr", bare) and "repeat" in value:
                bad.append(f"{sel} -> {track}")
    assert not bad, f"grids that can overflow a narrow phone: {bad}"


@pytest.mark.parametrize("section_id", ['id="needs"', 'id="why"', 'id="pricing"'])
def test_new_stages_all_reach_purchase_or_consult(section_id: str) -> None:
    chunk = _stage(section_id)
    if section_id == 'id="needs"':
        js = _needs_js()
        assert '/portal?pkg=' in js, "#needs offers no way to buy"
        assert "/consult" in js, "#needs offers no way to ask"
    else:
        assert "/portal" in chunk, f"{section_id} offers no way to buy"
        assert "/consult" in chunk, f"{section_id} offers no way to ask"
