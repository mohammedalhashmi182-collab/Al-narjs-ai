"""The bundled sample workbook. The bytes are also stored under tests/fixtures.

The sheet is an illustrative shop series for the public demo. It is not a claim
about a real client's revenue.
"""

from __future__ import annotations

import io
from pathlib import Path

from openpyxl import Workbook

SAMPLE_PATH = Path(__file__).resolve().parent / "samples" / "sales.xlsx"
FIXTURE_PATH = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "sales.xlsx"

_MONTHS = [f"2026-{month:02d}" for month in range(1, 7)]
_SERIES = (
    ("عسل سدر", (80, 92, 101, 110, 124, 133), (90, 90, 95, 95, 95, 98)),
    ("تمر خلاص", (200, 210, 225, 240, 250, 268), (25, 25, 26, 26, 28, 28)),
)


def build_sample_bytes() -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "المبيعات"
    worksheet.sheet_view.rightToLeft = True
    worksheet.append(["الشهر", "المنتج", "الكمية", "سعر الوحدة", "المبيعات"])
    for product, units, prices in _SERIES:
        for month, unit, price in zip(_MONTHS, units, prices, strict=True):
            worksheet.append([month, product, unit, price, unit * price])
    for cell in worksheet["A"][1:]:
        cell.number_format = "@"
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def load_sample_bytes() -> bytes:
    if SAMPLE_PATH.is_file():
        return SAMPLE_PATH.read_bytes()
    if FIXTURE_PATH.is_file():
        return FIXTURE_PATH.read_bytes()
    return build_sample_bytes()
