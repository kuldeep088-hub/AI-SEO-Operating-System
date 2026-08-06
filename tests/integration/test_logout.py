"""Signing out must land the user somewhere they can use.

The sign-out control in the app nav is a plain HTML form posting to
/v1/auth/logout, and a browser form POST *navigates* to whatever the endpoint
returns. Returning `{"ok": true}` revoked the session correctly and then left
the user looking at raw JSON on the API's origin, with no link back to the app.

The session revocation was never the bug — these tests pin the part that was:
who gets a redirect, who keeps the JSON, and that the cookie is cleared either
way.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from apps.api.deps import SESSION_COOKIE
from apps.api.main import app
from packages.core.config import settings

BROWSER = {"accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
SCRIPT = {"accept": "application/json"}


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app, follow_redirects=False) as c:
        yield c


def test_browser_navigation_is_redirected_to_login(client: TestClient) -> None:
    res = client.post("/v1/auth/logout", headers=BROWSER)

    assert res.status_code == 303, "303 turns the POST into a GET; 302 can re-POST"
    assert res.headers["location"] == f"{settings.web_url}/login"


def test_script_client_still_gets_json(client: TestClient) -> None:
    """The endpoint is documented API surface, not only a form target."""
    res = client.post("/v1/auth/logout", headers=SCRIPT)

    assert res.status_code == 200
    assert res.json() == {"ok": True}


@pytest.mark.parametrize("headers", [BROWSER, SCRIPT], ids=["browser", "script"])
def test_session_cookie_is_cleared_either_way(
    client: TestClient, headers: dict[str, str]
) -> None:
    res = client.post("/v1/auth/logout", headers=headers)

    cookie = res.headers.get("set-cookie", "")
    assert SESSION_COOKIE in cookie
    # An expiry in the past, or an empty value, is how a delete is expressed.
    assert 'Max-Age=0' in cookie or "expires=Thu, 01 Jan 1970" in cookie.lower()


@pytest.mark.parametrize("headers", [BROWSER, SCRIPT], ids=["browser", "script"])
def test_logout_without_a_session_is_not_an_error(
    client: TestClient, headers: dict[str, str]
) -> None:
    """Double-clicking sign out, or a stale tab, must not produce a 500."""
    res = client.post("/v1/auth/logout", headers=headers)
    assert res.status_code in (200, 303)
