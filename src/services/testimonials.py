"""Real customer testimonials, and only real ones.

The public site renders a testimonials section only when this returns a
non-empty list. Entries come from ``content/testimonials.json`` and are added by
the owner after a customer has approved the quote. Never seed placeholders.

Each entry: {"name": str, "quote": str, "quote_ar"?: str, "company"?: str,
"approved": true}. Entries without ``approved: true`` or without a name and a
quote are ignored.
"""

from __future__ import annotations

import json
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "content" / "testimonials.json"


def load(path: Path | None = None) -> list[dict]:
    try:
        data = json.loads((path or _PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [
        t for t in data
        if isinstance(t, dict) and t.get("approved") is True
        and str(t.get("name") or "").strip() and str(t.get("quote") or "").strip()
    ]
