"""Internal test results shown on /home under «جرّبناها بأنفسنا».

Data comes from a real test run (content/internal_tests.json, produced by the
round2 test script against the local server). These are tests by the
Al-Narjis team, never customer testimonials. Missing/invalid file -> None, so
the section is simply not rendered.
"""
from __future__ import annotations

import json
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "content" / "internal_tests.json"


def load(path: Path | None = None) -> dict | None:
    try:
        data = json.loads((path or _PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not data.get("test_date") or not data.get("transcripts"):
        return None
    return data
