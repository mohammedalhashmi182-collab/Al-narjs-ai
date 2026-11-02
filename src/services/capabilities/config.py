"""Environment switches for the new capabilities.

Every value has a default. A missing variable does not stop the process:
the cron endpoint stays closed until ``CRON_SECRET`` is set, and model-backed
revision stays off until it is explicitly enabled.
"""

from __future__ import annotations

import os


def _raw(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return default
    return str(value).strip()


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int, lo: int, hi: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = int(str(raw).strip())
    except ValueError:
        return default
    return max(lo, min(hi, value))


def _float(name: str, default: float, lo: float, hi: float) -> float:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = float(str(raw).strip())
    except ValueError:
        return default
    return max(lo, min(hi, value))


def cron_secret() -> str:
    """Empty means the cron endpoint refuses every caller (503)."""
    return _raw("CRON_SECRET", "")


def cron_eval_limit() -> int:
    return _int("CAPABILITY_CRON_EVAL_LIMIT", 20, 1, 100)


def cron_revise_stored() -> bool:
    """Rewriting stored client deliverables from cron is off unless enabled."""
    return _flag("CAPABILITY_CRON_REVISE", False)


def style_enabled() -> bool:
    return _flag("CAPABILITY_STYLE_ENABLED", True)


def eval_runtime_enabled() -> bool:
    """Score agent output inside the shared runtime. Revision stays local."""
    return _flag("CAPABILITY_EVAL_RUNTIME", True)


def eval_use_model() -> bool:
    """Paid-model revision. Off by default so a public call cannot spend a key."""
    return _flag("CAPABILITY_EVAL_USE_MODEL", False)


def eval_max_rounds() -> int:
    return _int("CAPABILITY_EVAL_MAX_ROUNDS", 3, 1, 3)


def eval_min_score() -> float:
    return _float("CAPABILITY_EVAL_MIN_SCORE", 0.72, 0.0, 1.0)


def forecast_max_horizon() -> int:
    return _int("CAPABILITY_FORECAST_MAX_HORIZON", 36, 1, 60)


def forecast_default_vat() -> float:
    return _float("CAPABILITY_FORECAST_VAT", 0.15, 0.0, 1.0)


def ocr_max_bytes() -> int:
    return _int("CAPABILITY_OCR_MAX_BYTES", 8_000_000, 100_000, 20_000_000)


def ocr_vision_enabled() -> bool:
    return _flag("OCR_VISION_ENABLED", False)
