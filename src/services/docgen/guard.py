"""Reject narrative numbers that were not computed (or quoted from the brief)."""

from __future__ import annotations

import re

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_LIST_MARKER = re.compile(r"^\s*\d{1,2}[.)\-]\s+")
_NUMBER = re.compile(r"(?<![\w])([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)")


def normalize_digits(text: str) -> str:
    return (text or "").translate(_AR_DIGITS).replace("٬", "").replace("٫", ".")


def strip_list_markers(text: str) -> str:
    return "\n".join(_LIST_MARKER.sub("", line) for line in normalize_digits(text).splitlines())


def extract_numbers(text: str) -> list[float]:
    """Western and Arabic-Indic numerals. List indexes (``1.``) are not figures."""
    found: list[float] = []
    for match in _NUMBER.finditer(strip_list_markers(text)):
        raw = match.group(1).replace(",", "")
        try:
            found.append(float(raw))
        except ValueError:
            continue
    return found


def number_allowed(number: float, allowed: list[float]) -> bool:
    """A figure matches a fact when it is the fact or a 2-decimal rounding of it.

    The tolerance is absolute (half a hundredth). A relative band would let a
    model round 97,183 down to 97,000 and still pass.
    """
    for fact in allowed:
        if abs(number - fact) <= 0.051:
            return True
    return False


def offending_numbers(text: str, allowed: list[float]) -> list[float]:
    bad: list[float] = []
    seen: set[str] = set()
    for number in extract_numbers(text):
        if number_allowed(number, allowed):
            continue
        key = f"{number:.4f}"
        if key in seen:
            continue
        seen.add(key)
        bad.append(number)
    return bad
