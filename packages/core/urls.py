"""URL handling for values that came from a request.

Both OAuth callbacks build their Location header by concatenating
``settings.web_url`` with a ``redirect_to`` the caller supplied:

    RedirectResponse(f"{settings.web_url}{redirect_to}")

``web_url`` is a bare origin with no trailing slash, so that concatenation only
stays on our origin when ``redirect_to`` begins with a single ``/``. Anything
else walks off it — ``.evil.com`` yields ``https://our.site.evil.com`` and
``@evil.com`` yields ``https://our.site@evil.com``, where everything before the
``@`` is userinfo and the real host is the attacker's. Both are ordinary
open redirects, and an open redirect on the end of a *real* Google login is a
convincing phishing primitive: the victim sees our domain, signs in for real,
and lands on the attacker's page.

See docs/06-api-auth.md §16.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

__all__ = ["safe_redirect_path"]

# CR/LF would split the Location header; NUL and friends are never legitimate
# in a path we generated ourselves.
_FORBIDDEN = frozenset("\r\n\t\x00\x0b\x0c")


def safe_redirect_path(value: str | None, default: str = "/") -> str:
    """Return ``value`` if it is a same-origin relative path, else ``default``.

    Accepts a path, optionally with query and fragment (``/connect?partial=1``).
    Rejects anything that could change the origin once concatenated onto
    ``web_url``:

    >>> safe_redirect_path("/connect")
    '/connect'
    >>> safe_redirect_path(".evil.com")
    '/'
    >>> safe_redirect_path("//evil.com")
    '/'
    >>> safe_redirect_path("https://evil.com")
    '/'
    >>> safe_redirect_path("/\\\\evil.com")
    '/'
    """
    if not value:
        return default

    if any(ch in _FORBIDDEN for ch in value):
        return default

    # Browsers normalise a backslash to a forward slash in the authority
    # position, so "/\evil.com" becomes "//evil.com" — protocol-relative, and
    # therefore off-origin — despite starting with a single slash.
    if "\\" in value:
        return default

    parts = urlsplit(value)

    # A scheme or an authority means it is not a relative path at all.
    if parts.scheme or parts.netloc:
        return default

    # urlsplit(".evil.com") parses as a *relative* path with no leading slash.
    # Concatenated onto the origin it becomes a different host.
    if not parts.path.startswith("/"):
        return default

    # "//evil.com" is protocol-relative. urlsplit already caught the common
    # form via netloc; this covers the rest.
    if parts.path.startswith("//"):
        return default

    return urlunsplit(("", "", parts.path, parts.query, parts.fragment))
