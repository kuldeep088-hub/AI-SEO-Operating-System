"""The session cookie's Secure flag — a setting that fails silently when wrong.

A Secure cookie sent over plain http is dropped by the browser without an
error anywhere: no exception, no log line, no failed request. The user just
lands back on the login screen forever. Since this system's "production" mode
is still localhost over http, the flag must follow the URL scheme rather than
the ENV name.
"""

from __future__ import annotations

from packages.core.config import Settings


def _settings(**over: str) -> Settings:
    base = {
        "DATABASE_URL": "postgresql://x/y",
        "TOKEN_ENCRYPTION_KEY": "k",
        "SESSION_SECRET": "s",
    }
    return Settings(**{**base, **over})  # type: ignore[arg-type]


def test_plain_http_localhost_never_sets_secure() -> None:
    s = _settings(API_URL="http://localhost:8000", ENV="dev")
    assert s.cookie_secure is False


def test_prod_mode_on_http_still_does_not_set_secure() -> None:
    """The regression this exists for: ./run.sh --prod must not break login."""
    s = _settings(API_URL="http://localhost:8000", ENV="prod-local")
    assert s.is_prod is True
    assert s.cookie_secure is False


def test_https_sets_secure_regardless_of_env() -> None:
    """Put TLS in front and the flag turns itself on, with no ENV change."""
    for env in ("dev", "prod-local"):
        s = _settings(API_URL="https://seo.growleadsagency.com", ENV=env)
        assert s.cookie_secure is True
