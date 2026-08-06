"""In-process token-bucket rate limiting.

docs/08-infrastructure.md §27 Layer 4 specifies these limits, and states the
threat model plainly: *"This is a local tool with a handful of users. Nobody is
DDoSing it… the threat model is accident rather than abuse."* Every limit it
lists is therefore keyed per **session** or per **org**.

That premise stops holding the moment the app is reachable from the internet.
An unauthenticated caller has no session and no org, so none of the §27 limits
bind them at all — and `/v1/auth/google/start` performs a database INSERT into
`oauth_states` before any authentication happens. This module adds the per-IP
bucket that case needs, and implements the §27 per-session limits alongside it.

**No new dependency** (CLAUDE.md rule 11) — a token bucket is twenty lines and
`slowapi`/`limits` would pull in a Redis-shaped abstraction this does not need.

**Known limitation, deliberate.** State lives in the process. `deploy/systemd/
seoos-api.service` runs `--workers 2`, so a limit of N is effectively N×2 across
the pool, and a restart forgets every bucket. For accident-shaped load and
casual abuse that is fine. It is *not* a defence against a distributed attacker
— that belongs at the edge, in Caddy or a CDN, and is called out as such in
deploy/README.md.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from fastapi import HTTPException, Request

__all__ = ["RateLimit", "TokenBucketLimiter", "client_ip", "limiter"]

# Buckets are evicted once idle for this long, so a caller rotating source
# addresses cannot grow the table without bound.
_IDLE_EVICTION_S = 3600.0

# Hard ceiling on tracked keys. Reaching it means something abnormal is
# happening; the sweep below drops the least recently used half rather than
# letting memory become the failure mode.
_MAX_KEYS = 50_000


@dataclass(frozen=True, slots=True)
class RateLimit:
    """`limit` events per `window_s` seconds, refilled continuously."""

    limit: int
    window_s: float

    @property
    def refill_per_second(self) -> float:
        return self.limit / self.window_s


# docs/08-infrastructure.md §27 Layer 4.
READ = RateLimit(300, 60)
MUTATION = RateLimit(60, 60)
ENQUEUE = RateLimit(20, 60)

# Not in §27, because §27 assumed nobody unauthenticated could reach this.
# Starting a sign-in writes a row to oauth_states with no credential required.
#
# 60/hour, not 10: this is keyed by source address, and a whole office behind
# one NAT address shares it. The limit exists to bound how fast an anonymous
# caller can make us write rows, not to police individual humans — and
# sweep_expired() in the scheduler collects whatever does get written.
OAUTH_START_PER_IP = RateLimit(60, 3600)


@dataclass
class _Bucket:
    tokens: float
    last_refill: float
    last_seen: float = field(default=0.0)


class TokenBucketLimiter:
    """Continuous-refill token buckets keyed by an arbitrary string."""

    def __init__(self) -> None:
        self._buckets: dict[tuple[str, str], _Bucket] = {}
        self._last_sweep = time.monotonic()

    def allow(self, key: str, rule: RateLimit, *, scope: str = "default") -> bool:
        """Consume one token. False means the caller is over its limit."""
        now = time.monotonic()
        self._maybe_sweep(now)

        bucket = self._buckets.get((scope, key))
        if bucket is None:
            # A new caller starts with a full bucket minus this request.
            self._buckets[(scope, key)] = _Bucket(
                tokens=rule.limit - 1.0, last_refill=now, last_seen=now
            )
            return True

        elapsed = now - bucket.last_refill
        bucket.tokens = min(rule.limit, bucket.tokens + elapsed * rule.refill_per_second)
        bucket.last_refill = now
        bucket.last_seen = now

        if bucket.tokens < 1.0:
            return False

        bucket.tokens -= 1.0
        return True

    def retry_after(self, key: str, rule: RateLimit, *, scope: str = "default") -> int:
        """Whole seconds until one token is available. At least 1."""
        bucket = self._buckets.get((scope, key))
        if bucket is None or bucket.tokens >= 1.0:
            return 1
        deficit = 1.0 - bucket.tokens
        return max(1, int(deficit / rule.refill_per_second) + 1)

    def _maybe_sweep(self, now: float) -> None:
        if now - self._last_sweep < 60.0 and len(self._buckets) < _MAX_KEYS:
            return
        self._last_sweep = now

        cutoff = now - _IDLE_EVICTION_S
        self._buckets = {k: b for k, b in self._buckets.items() if b.last_seen > cutoff}

        if len(self._buckets) >= _MAX_KEYS:
            keep = sorted(self._buckets.items(), key=lambda kv: kv[1].last_seen)
            self._buckets = dict(keep[len(keep) // 2 :])

    def reset(self) -> None:
        """Drop all state. For tests."""
        self._buckets.clear()
        self._last_sweep = time.monotonic()


limiter = TokenBucketLimiter()


def client_ip(request: Request) -> str:
    """The caller's address.

    `deploy/systemd/seoos-api.service` runs uvicorn with `--proxy-headers
    --forwarded-allow-ips 127.0.0.1`, so behind Caddy `request.client.host` is
    already the real client rather than the loopback. Trusting the raw
    X-Forwarded-For header here instead would let anyone spoof their way past
    the limit by setting it themselves.
    """
    return request.client.host if request.client else "unknown"


def enforce(request: Request, key: str, rule: RateLimit, *, scope: str) -> None:
    """Raise 429 with Retry-After if `key` is over `rule`."""
    if limiter.allow(key, rule, scope=scope):
        return
    retry = limiter.retry_after(key, rule, scope=scope)
    raise HTTPException(
        429,
        detail="Too many requests. Slow down and try again.",
        headers={"Retry-After": str(retry)},
    )
