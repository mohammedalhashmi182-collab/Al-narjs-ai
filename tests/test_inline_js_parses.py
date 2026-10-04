"""Every inline script must parse.

This exists because a stray ``}`` after an edit landed in ``portal.html`` and
took the whole page script down with it. Nothing in the test suite noticed: the
response was 200, the DOM was complete, the templates contained the expected
strings, and every element the script was supposed to build stayed empty. A
visitor saw a package grid with nothing in it. Only a real browser reported the
failure, as ``pageerror: missing ) after argument list``.

A syntax error is the cheapest defect in the codebase to catch and the most
expensive to ship, because it is invisible to every content assertion while
disabling the page. So the parse is asserted directly.

``node --check`` is the real parser, not a bracket counter, so a missing brace
in a template literal or an unclosed arrow function is caught too. Jinja is
stubbed before parsing: ``{{ x }}`` becomes a value and ``{% ... %}`` is dropped,
which keeps a template-only construct from being reported as broken JavaScript.

Skipped when node is not installed rather than failed, so a machine without
node does not report a false defect.
"""

from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / "src" / "web" / "templates"

INLINE_SCRIPT_RE = re.compile(
    r'<script(?![^>]*\bsrc\s*=)(?![^>]*\btype\s*=\s*["\']?(?!module\b)[^"\'>\s]+)[^>]*>'
    r"(?P<body>.*?)</script>",
    re.S | re.I,
)
JINJA_STATEMENT_RE = re.compile(r"\{%.*?%\}", re.S)
JINJA_EXPRESSION_RE = re.compile(r"\{\{.*?\}\}", re.S)
JINJA_COMMENT_RE = re.compile(r"\{#.*?#\}", re.S)

NODE = shutil.which("node")
requires_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


def _scripts() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in sorted(TEMPLATES_DIR.rglob("*.html")):
        for index, match in enumerate(INLINE_SCRIPT_RE.finditer(path.read_text(encoding="utf-8"))):
            found.append((f"{path.relative_to(ROOT)}#script{index}", match.group("body")))
    return found


def _as_javascript(body: str) -> str:
    """Strip Jinja so the parse tests the JavaScript, not the templating."""
    stubbed = JINJA_COMMENT_RE.sub("", body)
    stubbed = JINJA_STATEMENT_RE.sub("", stubbed)
    return JINJA_EXPRESSION_RE.sub("null", stubbed)


def test_the_templates_actually_contain_inline_scripts():
    assert len(_scripts()) >= 20, "the extraction pattern stopped matching"


@requires_node
@pytest.mark.parametrize(("name", "body"), _scripts(), ids=[n for n, _ in _scripts()])
def test_inline_script_parses(tmp_path: Path, name: str, body: str):
    if not body.strip():
        pytest.skip("empty script tag")

    source = _as_javascript(body)
    script = tmp_path / "inline.js"
    script.write_text(source, encoding="utf-8")
    result = subprocess.run(  # noqa: S603
        [NODE, "--check", str(script)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        line = next(
            (
                entry
                for entry in result.stderr.splitlines()
                if "SyntaxError" in entry
            ),
            result.stderr.strip(),
        )
        pytest.fail(f"{name}: {line}")