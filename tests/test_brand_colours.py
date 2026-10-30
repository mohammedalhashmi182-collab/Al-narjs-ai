"""Public surfaces use black, white, grey, and #FF5A36. No beige, gold, or green."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "web"
FORBIDDEN = re.compile(
    r"f4eee2|e9e1d3|bdb4a5|c9a27a|244,\s*238,\s*226|n-green|btn-green|#4f7942|#3d5f33|#5ea552|#3f7d3a",
    re.I,
)


def test_src_web_has_no_beige_gold_or_green_tokens():
    hits = []
    for path in ROOT.rglob("*"):
        if path.suffix.lower() not in {".css", ".html"}:
            continue
        text = path.read_text(encoding="utf-8")
        for n, line in enumerate(text.splitlines(), 1):
            if FORBIDDEN.search(line):
                hits.append(f"{path.relative_to(ROOT)}:{n}")
    assert not hits, hits
