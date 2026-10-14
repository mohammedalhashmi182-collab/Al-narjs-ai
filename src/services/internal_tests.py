"""Internal test results shown on /home under «جرّبناها بأنفسنا».

Data comes from a real test run (content/internal_tests.json, produced by the
round2 test script against the local server). These are tests by the
Al-Narjis team, never customer testimonials. Missing/invalid file -> None, so
the section is simply not rendered.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "content" / "internal_tests.json"


def enabled() -> bool:
    """Section is OFF unless INTERNAL_TESTS_ENABLED is truthy.

    The 2026-10-14 run (5/12 correct, 7 handoffs) is too weak to publish and no
    model key was available to re-run with the LLM reply agent, so the owner must
    opt in explicitly after a strong, real re-run.
    """
    return os.getenv("INTERNAL_TESTS_ENABLED", "").strip().lower() in ("1", "true", "yes", "on")


def load(path: Path | None = None, *, force: bool = False) -> dict | None:
    if not (force or enabled()):
        return None
    try:
        data = json.loads((path or _PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not data.get("test_date") or not data.get("transcripts"):
        return None
    return data
