"""Error classification.

The worker's retry logic branches on these (docs/08-infrastructure.md §25):
retrying a revoked OAuth token three times only delays telling the user
something they must fix by hand.
"""

from __future__ import annotations


class SeoOsError(Exception):
    """Base for every application error."""


class TransientError(SeoOsError):
    """Retry with backoff — timeout, 503, connection reset."""


class QuotaError(SeoOsError):
    """Upstream quota exhausted. Requeue at retry_after; does NOT consume an attempt."""

    def __init__(self, message: str, retry_after: int = 3600) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class PermanentError(SeoOsError):
    """Do not retry — dead-letter and notify. Invalid config, revoked token, 404."""


class SSRFBlockedError(PermanentError):
    """A fetch was blocked because the URL resolved to a private address.

    See docs/09-security-ops.md §29. This is a security control, never a
    transient failure — do not retry it.
    """


class AuthError(SeoOsError):
    """Authentication or authorisation failure."""


class TenantMismatchError(AuthError):
    """A principal attempted to reach another tenant's data.

    Should be impossible — RLS is the backstop. If this is ever raised, it means
    the application layer caught something before the database had to, which is
    worth investigating rather than swallowing.
    """
