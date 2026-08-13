"""A per-caller budget for the two endpoints that cost real time.

`/generate` and `/preview` both take the single global build lock. That lock is
correct — the generator configures itself through module globals, so builds have
to be serialised — but it means throughput is one build at a time for the whole
service. One anonymous caller in a `for` loop is therefore enough to put every
other customer behind an arbitrarily long queue. Nothing else in the API is
worth limiting: reads are cheap and validation answers in 9 ms.

A token bucket rather than a fixed window, because a fixed window lets someone
spend a whole hour's budget in one second at the boundary and then do it again
immediately. The bucket refills continuously, so a burst is allowed once and
then paid for.

**In-process, and that is the honest scope.** The counters live in this
process's memory, so they reset on deploy and would not be shared between
replicas. The API is pinned to one replica anyway — see DEPLOY.md, and the build
lock is the reason — so a shared store would be precision this deployment cannot
use. If it ever runs multi-replica it needs a real queue first, and the limiter
should move to whatever backs that.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request

from api.config import get_settings


@dataclass
class _Bucket:
    tokens: float
    updated: float


class RateLimiter:
    """One named budget: `capacity` requests, refilled over `per_seconds`."""

    def __init__(self, capacity: int, per_seconds: float = 3600.0) -> None:
        self.capacity = float(capacity)
        self.rate = self.capacity / per_seconds
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def check(self, key: str, *, now: float | None = None) -> float:
        """Spend one token. Returns 0.0 if allowed, else seconds to wait."""
        now = time.monotonic() if now is None else now
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(tokens=self.capacity, updated=now)
                self._buckets[key] = bucket

            elapsed = max(0.0, now - bucket.updated)
            bucket.tokens = min(self.capacity, bucket.tokens + elapsed * self.rate)
            bucket.updated = now

            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return 0.0
            return (1.0 - bucket.tokens) / self.rate

    def prune(self, *, now: float | None = None) -> int:
        """Forget callers whose bucket has refilled completely.

        Without this the dict is an unbounded map of every IP ever seen — a slow
        leak with the same shape as the one the job index had.
        """
        now = time.monotonic() if now is None else now
        with self._lock:
            stale = [
                k
                for k, b in self._buckets.items()
                if b.tokens + (now - b.updated) * self.rate >= self.capacity
            ]
            for k in stale:
                del self._buckets[k]
            return len(stale)


def client_key(request: Request) -> str:
    """Who is calling.

    In the deployed topology the browser talks to the web service, which proxies
    server-side — so the API's socket peer is always the web container and
    limiting on it would throttle everyone as one caller. The proxy forwards
    `x-forwarded-for`, which the platform edge sets, and the left-most entry is
    the original client.

    Trusting that header is only safe because the API is not publicly reachable
    (DEPLOY.md gives it no public domain); a client that could hit it directly
    could put anything in there. If the API is ever exposed, this must become a
    trusted-proxy check rather than blind trust.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


_generate: RateLimiter | None = None
_preview: RateLimiter | None = None
_lock = threading.Lock()


def _limiters() -> tuple[RateLimiter, RateLimiter]:
    global _generate, _preview
    with _lock:
        if _generate is None or _preview is None:
            settings = get_settings()
            _generate = RateLimiter(settings.generate_per_hour)
            _preview = RateLimiter(settings.preview_per_hour)
        return _generate, _preview


def enforce(request: Request, which: str) -> None:
    """Raise 429 if this caller is over budget for `which` ("generate"/"preview")."""
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return
    generate, preview = _limiters()
    limiter = generate if which == "generate" else preview
    wait = limiter.check(client_key(request))
    if wait <= 0.0:
        return
    retry = max(1, int(wait + 0.5))
    raise HTTPException(
        status_code=429,
        detail=f"Too many {which} requests — try again in {retry}s.",
        headers={"Retry-After": str(retry)},
    )


def prune_all() -> int:
    """Drop fully-refilled buckets. Called by the retention sweep."""
    if _generate is None or _preview is None:
        return 0
    return _generate.prune() + _preview.prune()
