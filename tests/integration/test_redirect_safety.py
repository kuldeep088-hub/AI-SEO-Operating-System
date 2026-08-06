"""The OAuth callbacks concatenate a caller-supplied path onto web_url.

`settings.web_url` is a bare origin with no trailing slash, so
`f"{web_url}{redirect_to}"` only stays on our origin when redirect_to starts
with exactly one '/'. These are the inputs that walk off it.

An open redirect at the end of a *genuine* Google login is a strong phishing
primitive — the victim sees our domain, signs in for real, and is handed to the
attacker — so this is a security test, not a formatting one.
"""

from __future__ import annotations

import pytest

from packages.core.urls import safe_redirect_path

WEB_URL = "https://seo.growleadsagency.com"

# Each of these, concatenated onto WEB_URL, resolves to a host we do not own.
ESCAPES = [
    ".evil.com",           # https://seo.growleadsagency.com.evil.com
    "@evil.com",           # userinfo trick — real host is evil.com
    "//evil.com",          # protocol-relative
    "/\\evil.com",         # browsers fold \ to / in the authority position
    "\\\\evil.com",
    "https://evil.com",
    "http://evil.com",
    "javascript:alert(1)",
    "evil.com",
    ":https://evil.com",
]


@pytest.mark.parametrize("probe", ESCAPES)
def test_off_origin_inputs_are_rejected(probe: str) -> None:
    assert safe_redirect_path(probe) == "/"


@pytest.mark.parametrize("probe", ESCAPES)
def test_rejected_inputs_cannot_leave_the_origin(probe: str) -> None:
    """The property that actually matters, asserted on the composed URL."""
    composed = f"{WEB_URL}{safe_redirect_path(probe)}"
    assert composed.startswith(f"{WEB_URL}/")
    assert "evil.com" not in composed


@pytest.mark.parametrize(
    "probe",
    ["/", "/connect", "/connect?partial=1", "/reports/abc#summary", "/a/b/c"],
)
def test_legitimate_paths_survive(probe: str) -> None:
    assert safe_redirect_path(probe) == probe


def test_header_injection_is_rejected() -> None:
    assert safe_redirect_path("/ok\r\nX-Injected: 1") == "/"
    assert safe_redirect_path("/ok\nSet-Cookie: a=b") == "/"


def test_empty_and_none_fall_back_to_the_default() -> None:
    assert safe_redirect_path(None) == "/"
    assert safe_redirect_path("") == "/"
    assert safe_redirect_path(None, "/connect") == "/connect"
    assert safe_redirect_path("@evil.com", "/connect") == "/connect"
