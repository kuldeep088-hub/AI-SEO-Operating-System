"""A refused Google authorisation must land somewhere a human can read.

Google reports refusal by redirecting to our callback with `?error=<code>` and
**no** `code` parameter. Pressing Cancel on the consent screen is the ordinary
way to produce it, and on a public deployment it happens constantly.

Both callbacks originally declared `code` as a required query parameter, so
this path returned FastAPI's raw 422 validation JSON in the browser — a dead
end with no explanation and no way back. These tests pin the redirect.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from packages.core.config import settings

CALLBACKS = ["/v1/auth/google/callback", "/v1/google/callback"]


@pytest.fixture
def client() -> Iterator[TestClient]:
    # Used as a context manager so the app's lifespan runs — without it the
    # database pool is never initialised and every request dies in the handler
    # rather than exercising the behaviour under test.
    #
    # follow_redirects=False so the 307 itself is the assertion, rather than
    # whatever the web app happens to serve at the destination.
    with TestClient(app, follow_redirects=False) as c:
        yield c


@pytest.mark.parametrize("path", CALLBACKS)
def test_refusal_redirects_instead_of_422(client: TestClient, path: str) -> None:
    res = client.get(path, params={"error": "access_denied", "state": "whatever"})

    assert res.status_code != 422, "the raw validation blob is what this test exists to prevent"
    assert res.status_code in (302, 307)
    assert res.headers["location"].startswith(settings.web_url)


@pytest.mark.parametrize("path", CALLBACKS)
def test_error_code_is_forwarded_for_display(client: TestClient, path: str) -> None:
    """The web app turns the code into a sentence; it needs the code to do it."""
    res = client.get(path, params={"error": "admin_policy_enforced", "state": "x"})

    assert "oauth_error=admin_policy_enforced" in res.headers["location"]


@pytest.mark.parametrize("path", CALLBACKS)
def test_missing_code_without_an_error_is_also_handled(
    client: TestClient, path: str
) -> None:
    """A bare callback hit — a stale bookmark, a crawler — must not 422 either."""
    res = client.get(path)

    assert res.status_code in (302, 307)
    assert "oauth_error=missing_code" in res.headers["location"]


def test_signin_refusal_returns_to_login(client: TestClient) -> None:
    res = client.get(
        "/v1/auth/google/callback", params={"error": "access_denied", "state": "x"}
    )
    assert res.headers["location"].startswith(f"{settings.web_url}/login?")


def test_grant_refusal_returns_to_connect(client: TestClient) -> None:
    """The user is already signed in here, so /login would be a pointless bounce."""
    res = client.get(
        "/v1/google/callback", params={"error": "access_denied", "state": "x"}
    )
    assert res.headers["location"].startswith(f"{settings.web_url}/connect?")
