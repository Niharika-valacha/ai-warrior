"""Per-client rate limits for endpoints that spend money: model calls and web searches."""
# No `from __future__ import annotations` here: FastAPI must see the real `Request` type on __call__.
import math
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request


class RateLimit:
    """Sliding window: at most `limit` requests per `window_s` seconds per client.

    Usable as a FastAPI dependency (`Depends(limit)`) or called directly with a key.
    """

    # ponytail: in-memory, so it only works with one API instance. Move the counters to Redis
    # when the API runs on more than one instance (roadmap Phase 5).

    def __init__(self, limit: int, window_s: int):
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window_s:
                hits.popleft()
            if len(hits) >= self.limit:
                retry = math.ceil(self.window_s - (now - hits[0]))
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many requests. Try again in {retry}s.",
                    headers={"Retry-After": str(retry)},
                )
            hits.append(now)

    def __call__(self, request: Request) -> None:
        self.check(request.client.host if request.client else "unknown")
