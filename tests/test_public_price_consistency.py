"""Public copy must not revive retired prices or the withdrawn launch discount."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ("marketing", "campaigns")
TEXT_SUFFIXES = {".md", ".html", ".txt", ".py", ".json"}

# Retired public prices (ردّ / بيع / تشغيل) and the withdrawn NARJIS50 offer.
OLD_PRICE = re.compile(r"(?<![\d,])(?:599|1,499|1499|3,499|3499)(?!\d)")
DISCOUNT = re.compile(r"NARJIS\s*50|خصم\s*50|50\s*%", re.IGNORECASE)


def _texts() -> list[tuple[Path, str]]:
    found = []
    for folder in SCAN_DIRS:
        base = ROOT / folder
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
                found.append((path, path.read_text(encoding="utf-8")))
    return found


def test_marketing_and_campaigns_have_no_retired_prices_or_launch_discount():
    hits = []
    for path, text in _texts():
        for pattern in (OLD_PRICE, DISCOUNT):
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                hits.append(f"{path.relative_to(ROOT)}:{line}: {match.group(0)}")
    assert hits == []
