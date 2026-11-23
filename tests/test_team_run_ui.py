"""Team run panel on the homepage: the visitor watches the AI CEO's team work.

File-content guards for the visitor-facing panel. The stream itself is covered
by tests/test_ceo_live.py. Here we check the markup, the script's event contract,
the safety rules (no markup-string writes of server text), accessibility, and the
motion and focus rules in the stylesheet.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "src" / "web" / "templates" / "landing.html"
JS = ROOT / "src" / "web" / "static" / "js" / "narjis-team-run.js"
CSS = ROOT / "src" / "web" / "static" / "css" / "narjis-team-run.css"

EVENT_TYPES = ("team", "agent_start", "agent_done", "final", "unavailable", "no_agents", "error")
PANEL_IDS = (
    "teamRun",
    "teamRunForm",
    "teamRunProblem",
    "teamRunSubmit",
    "teamRunCount",
    "teamRunStatus",
    "teamRunCards",
)
NODE = shutil.which("node")


def _template() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _js() -> str:
    return JS.read_text(encoding="utf-8")


def _css() -> str:
    return CSS.read_text(encoding="utf-8")


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def test_homepage_hosts_the_panel_hidden_until_the_script_runs() -> None:
    body = _template()
    assert 'id="teamRun"' in body
    section = re.search(r'<section[^>]*id="teamRun"[^>]*>', body)
    assert section, "the team run panel must be a <section id=\"teamRun\">"
    assert " hidden" in section.group(0), "the panel must start hidden so it needs JavaScript"
    assert 'aria-labelledby="teamRunH"' in body and 'id="teamRunH"' in body


@pytest.mark.parametrize("element_id", PANEL_IDS)
def test_every_id_the_script_reads_exists_in_the_template(element_id: str) -> None:
    assert f'id="{element_id}"' in _template()
    assert f"'{element_id}'" in _js(), f"the script must look up #{element_id}"


def test_input_is_labelled_capped_and_the_status_is_polite() -> None:
    body = _template()
    assert re.search(r'<label[^>]*for="teamRunProblem"', body), "the textarea needs a label"
    field = re.search(r'<textarea[^>]*id="teamRunProblem"[^>]*>', body)
    assert field and 'maxlength="600"' in field.group(0)
    status = re.search(r'<p[^>]*id="teamRunStatus"[^>]*>', body)
    assert status and 'aria-live="polite"' in status.group(0)
    assert 'role="status"' in status.group(0)


def test_submit_button_carries_the_bilingual_copy() -> None:
    body = _template()
    assert "شغّل الفريق" in body
    assert "Run the team" in body
    assert 'type="submit"' in re.search(r'<button[^>]*id="teamRunSubmit"[^>]*>', body).group(0)


def test_panel_sits_under_the_hero_copy_and_loads_its_assets() -> None:
    body = _template()
    hero_copy = body.index('<div class="copy">')
    panel = body.index('id="teamRun"')
    concierge = body.index('id="ngConcierge"')
    assert hero_copy < panel, "the panel belongs inside the hero copy column"
    assert panel < concierge, "the panel sits beside the CEO concierge column"
    assert '/static/css/narjis-team-run.css"' in body
    assert re.search(r'<script src="/static/js/narjis-team-run\.js" defer></script>', body)


def test_script_speaks_the_stream_contract() -> None:
    js = _js()
    for event_type in EVENT_TYPES:
        assert f"'{event_type}'" in js, f"the script must handle the {event_type!r} event"
    assert "/api/ceo/team-run" in js
    assert "'POST'" in js
    assert "documentElement.lang" in js
    assert "response.status === 429" in js, "HTTP 429 must show the limit and render no cards"
    assert "getReader" in js and "TextDecoder" in js, "the stream is read with fetch and a reader"


def test_script_never_writes_server_text_as_markup() -> None:
    js = _js()
    assert "innerHTML" not in js
    assert "insertAdjacentHTML" not in js
    assert "document.write" not in js
    assert "EventSource" not in js, "the endpoint takes POST, so EventSource cannot be used"
    assert "eval(" not in js
    assert "textContent" in js


def test_script_disables_the_button_during_a_run_and_restores_it() -> None:
    js = _js()
    assert "submit.disabled = on" in js
    assert "setBusy(false)" in js
    assert "busy = on" in js or "if (busy) return" in js


def test_script_keeps_the_daily_limit_away_from_the_cards() -> None:
    js = _js()
    limit_branch = js[js.index("response.status === 429") :]
    limit_branch = limit_branch[: limit_branch.index("return null;")]
    assert "finish(T.limit)" in limit_branch
    assert "addCard" not in limit_branch and "onTeam" not in limit_branch


@pytest.mark.parametrize("state", ["queued", "working", "done", "ended", "final"])
def test_card_states_have_css(state: str) -> None:
    css = _css()
    assert f".ntr-card.is-{state}" in css or f".is-{state}" in css, f"no style for is-{state}"


def test_script_only_toggles_classes_the_stylesheet_defines() -> None:
    css = _compact(_css())
    for cls in set(re.findall(r"'(ntr-[a-z-]+)'", _js())):
        assert f".{cls}" in css or f".{cls}:" in css or f".{cls}," in css, f"{cls} is not styled"


def test_stylesheet_honours_reduced_motion_and_the_identity() -> None:
    css = _css()
    lowered = css.lower()
    assert "prefers-reduced-motion: reduce" in css
    assert "#ff5a36" in lowered
    assert "outline: 3px solid #ff5a36" in lowered, "focus rings must be a 3px #FF5A36 outline"
    compact = _compact(css)
    assert "rgba(255,255,255,.78)" in compact
    assert "rgba(18,16,13,.12)" in compact
    assert "backdrop-filter:blur(24px)" in compact
    assert "border-radius:20px" in compact
    for banned in ("#f4c430", "#4f7942", "#7c3aed", "#8b5cf6", "#a855f7", "#6d28d9"):
        assert banned not in lowered, f"{banned} is not part of this panel's palette"


def test_pulse_is_removed_for_reduced_motion() -> None:
    css = _css()
    reduced = re.search(r"@media \(prefers-reduced-motion: reduce\)\s*\{(.*?)\n\}", css, re.S)
    assert reduced, "reduced-motion block is missing"
    assert "animation: none" in reduced.group(1)
    assert "ntr-pulse" in css and "ntr-pulse" not in reduced.group(1)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_script_parses() -> None:
    result = subprocess.run([NODE, "--check", str(JS)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
