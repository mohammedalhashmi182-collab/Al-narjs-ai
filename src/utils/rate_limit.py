from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class SlidingWindowLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > self.window_seconds:
                q.popleft()
            if len(q) >= self.max_requests:
                retry_after = max(1, int(self.window_seconds - (now - q[0])))
                return False, retry_after
            q.append(now)
            return True, 0

    def reset(self) -> None:
        """Drop all recorded hits.

        The limiters are process-wide by design, so a test suite that drives one
        endpoint repeatedly exhausts the window and every later test sees a 429
        that has nothing to do with what it is asserting.
        """
        with self._lock:
            self._hits.clear()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


consult_limiter = SlidingWindowLimiter(max_requests=30, window_seconds=60)


def rate_limit_consult(request: Request) -> None:
    ok, retry_after = consult_limiter.check(f"{client_ip(request)}:/api/consult")
    if not ok:
        raise HTTPException(
            status_code=429,
            detail={"error": "Too many requests", "retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        )


login_limiter = SlidingWindowLimiter(max_requests=10, window_seconds=300)


def rate_limit_login(request: Request) -> None:
    ok, retry_after = login_limiter.check(f"{client_ip(request)}:login")
    if not ok:
        raise HTTPException(
            status_code=429,
            detail={"error": "Too many attempts", "retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        )


# A buyer clicks "I sent the transfer" once. This endpoint pushes an alert to the
# owner's Telegram, so it must not be callable in a loop by a bored script.
transfer_limiter = SlidingWindowLimiter(max_requests=20, window_seconds=600)


def rate_limit_transfer_report(request: Request) -> None:
    ok, retry_after = transfer_limiter.check(f"{client_ip(request)}:/api/payments/transfer-reported")
    if not ok:
        raise HTTPException(
            status_code=429,
            detail={"error": "Too many requests", "retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        )


# The Botpress closed-sale endpoint creates a customer, wakes the CEO and pushes
# an owner alert in one call, so it is the most expensive endpoint in the app.
# The signature already proves the caller is Botpress; this limits a misconfigured
# or replaying sender. Deliberately tight: real closed sales are rare.
botpress_limiter = SlidingWindowLimiter(max_requests=30, window_seconds=300)


def rate_limit_botpress(request: Request) -> None:
    ok, retry_after = botpress_limiter.check(f"{client_ip(request)}:/api/v1/botpress-lead")
    if not ok:
        raise HTTPException(
            status_code=429,
            detail={"error": "Too many requests", "retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        )


# Karmish drives the model provider, so every call costs money and tokens. It is
# owner-only, and this is the second lock: a stolen session cookie must not be
# able to run up a bill.
karmish_limiter = SlidingWindowLimiter(max_requests=20, window_seconds=300)


def rate_limit_karmish(request: Request) -> None:
    ok, retry_after = karmish_limiter.check(f"{client_ip(request)}:/api/v1/karmish/talk")
    if not ok:
        raise HTTPException(
            status_code=429,
            detail={"error": "Too many requests", "retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        )