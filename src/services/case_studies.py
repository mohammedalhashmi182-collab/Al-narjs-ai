"""Real customer case studies, and only real ones.

The public site renders a case-studies section only when this returns a
non-empty list. Entries come from ``content/case_studies.json`` and are added
by the owner after a customer has approved the write-up. Never seed
placeholders, names, logos, or numbers.

Each entry:

* ``title`` and ``summary`` (English), plus optional ``title_ar`` / ``summary_ar``
* ``approved`` must be true
* optional ``url`` (the customer's own site) and ``sector``

A logo field is intentionally absent. Do not add one until the owner has a
file the customer approved.
"""

from __future__ import annotations

import json
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "content" / "case_studies.json"


def load(path: Path | None = None) -> list[dict]:
    try:
        data = json.loads((path or _PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    ready: list[dict] = []
    for item in data:
        if not isinstance(item, dict) or item.get("approved") is not True:
            continue
        title = str(item.get("title") or "").strip()
        summary = str(item.get("summary") or "").strip()
        if not title or not summary:
            continue
        ready.append(item)
    return ready
