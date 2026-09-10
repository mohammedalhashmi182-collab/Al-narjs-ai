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