"""First-class capabilities: forecast, Arabic OCR, style memory, evaluation."""

from src.services.capabilities.config import (  # noqa: F401
    cron_secret,
    eval_max_rounds,
    eval_min_score,
    eval_runtime_enabled,
    eval_use_model,
    forecast_max_horizon,
    ocr_max_bytes,
    style_enabled,
)
