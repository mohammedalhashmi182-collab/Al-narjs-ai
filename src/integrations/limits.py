"""Rate limits for install, webhooks, and order lookups (stops order-number guessing)."""

from __future__ import annotations

from src.utils.rate_limit import SlidingWindowLimiter

installs = SlidingWindowLimiter(max_requests=20, window_seconds=600)
webhooks = SlidingWindowLimiter(max_requests=120, window_seconds=60)
order_lookups = SlidingWindowLimiter(max_requests=8, window_seconds=600)
product_lookups = SlidingWindowLimiter(max_requests=30, window_seconds=600)


def reset() -> None:
    for limiter in (installs, webhooks, order_lookups, product_lookups):
        limiter.reset()
