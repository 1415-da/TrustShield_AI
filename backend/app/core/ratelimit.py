"""Small in-process sliding-window rate limiter (per key), shared by sign-in, signup and the public playground."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import Request


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self.hits: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str, limit: int, window: float) -> bool:
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def exceeded(self, key: str, limit: int, window: float) -> bool:
        """True when `key` already has `limit` hits inside the window (does not record a hit)."""
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > window:
                q.popleft()
            return len(q) >= limit

    def hit(self, key: str) -> None:
        with self.lock:
            self.hits[key].append(time.monotonic())

    def reset(self) -> None:
        with self.lock:
            self.hits.clear()


limiter = SlidingWindowLimiter()


def client_key(request: Request) -> str:
    # Behind the web app's /api proxy every request comes from the proxy, so prefer the forwarded client address.
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")
