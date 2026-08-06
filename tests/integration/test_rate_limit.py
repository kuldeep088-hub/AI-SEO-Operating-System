"""Rate limiting — docs/08-infrastructure.md §27 Layer 4.

§27's limits are all keyed per session or per org, which bounds nobody who has
not signed in. These tests pin the unauthenticated per-IP bucket that going
public requires, and the refill behaviour that keeps it from being a permanent
ban.
"""

from __future__ import annotations

import pytest

from packages.core.ratelimit import RateLimit, TokenBucketLimiter


@pytest.fixture
def limiter() -> TokenBucketLimiter:
    return TokenBucketLimiter()


def test_allows_up_to_the_limit_then_refuses(limiter: TokenBucketLimiter) -> None:
    rule = RateLimit(5, 60)
    assert all(limiter.allow("1.2.3.4", rule) for _ in range(5))
    assert not limiter.allow("1.2.3.4", rule)


def test_keys_are_independent(limiter: TokenBucketLimiter) -> None:
    rule = RateLimit(2, 60)
    assert limiter.allow("a", rule)
    assert limiter.allow("a", rule)
    assert not limiter.allow("a", rule)
    # A different caller is unaffected by the first one's exhaustion.
    assert limiter.allow("b", rule)


def test_scopes_are_independent(limiter: TokenBucketLimiter) -> None:
    """A session bucket and an IP bucket must not share state.

    hash_token() output and an IP string could otherwise collide in principle,
    and more practically the two have very different limits.
    """
    rule = RateLimit(1, 60)
    assert limiter.allow("same-key", rule, scope="session")
    assert not limiter.allow("same-key", rule, scope="session")
    assert limiter.allow("same-key", rule, scope="ip")


def test_tokens_refill_over_time(limiter: TokenBucketLimiter, monkeypatch) -> None:
    rule = RateLimit(60, 60)  # one per second
    clock = {"t": 1_000.0}
    monkeypatch.setattr("packages.core.ratelimit.time.monotonic", lambda: clock["t"])

    for _ in range(60):
        assert limiter.allow("ip", rule)
    assert not limiter.allow("ip", rule)

    clock["t"] += 1.0
    assert limiter.allow("ip", rule), "one second should buy exactly one token"
    assert not limiter.allow("ip", rule)

    clock["t"] += 3600.0
    assert limiter.allow("ip", rule)


def test_bucket_never_refills_past_its_limit(
    limiter: TokenBucketLimiter, monkeypatch
) -> None:
    """Otherwise a caller who idles for a day banks a day's worth of burst."""
    rule = RateLimit(5, 60)
    clock = {"t": 1_000.0}
    monkeypatch.setattr("packages.core.ratelimit.time.monotonic", lambda: clock["t"])

    assert limiter.allow("ip", rule)
    clock["t"] += 86_400.0

    assert sum(limiter.allow("ip", rule) for _ in range(50)) == 5


def test_retry_after_is_at_least_one_second(limiter: TokenBucketLimiter) -> None:
    rule = RateLimit(1, 3600)
    assert limiter.allow("ip", rule)
    assert not limiter.allow("ip", rule)
    assert limiter.retry_after("ip", rule) >= 1


def test_idle_buckets_are_evicted(limiter: TokenBucketLimiter, monkeypatch) -> None:
    """Memory must not be the failure mode when an attacker rotates addresses."""
    rule = RateLimit(1, 60)
    clock = {"t": 1_000.0}
    monkeypatch.setattr("packages.core.ratelimit.time.monotonic", lambda: clock["t"])

    for i in range(100):
        limiter.allow(f"ip-{i}", rule)
    assert len(limiter._buckets) == 100

    # Past the idle window, and past the sweep interval so a sweep actually runs.
    clock["t"] += 7_200.0
    limiter.allow("fresh", rule)
    assert len(limiter._buckets) == 1
