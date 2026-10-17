"""Phone comparison for order verification. Last 9 digits, Arabic-Indic aware."""

from __future__ import annotations

import re

_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def digits(value: object) -> str:
    return re.sub(r"\D", "", str(value or "").translate(_AR))


def same_phone(left: object, right: object) -> bool:
    a, b = digits(left), digits(right)
    if len(a) < 8 or len(b) < 8:
        return False
    return a[-9:] == b[-9:]


def masked(value: object) -> bool:
    return "*" in str(value or "")
