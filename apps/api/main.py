"""FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
import ulid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.deps import SESSION_COOKIE
from apps.api.routers import auth, google, jobs, orgs
from packages.ai import health as ai_health
from packages.core.config import settings
from packages.core.crypto import hash_token
from packages.core.errors import AuthError, PermanentError, QuotaError, TransientError
from packages.core.logging import configure_logging, get_logger
from packages.core.ratelimit import MUTATION, READ, client_ip, limiter
from packages.db.engine import close_pool, healthcheck, init_pool

configure_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await init_pool()
    log.info("api.started", env=settings.env, url=settings.api_url)
    yield
    await close_pool()
    log.info("api.stopped")


app = FastAPI(
    title="AI SEO Operating System",
    description="Local-first SEO platform. $0/month.",
    version="0.1.0",
    docs_url="/v1/docs",
    openapi_url="/v1/openapi.json",
    lifespan=lifespan,
)

# The web app runs on :3000. Cookies are shared because ports don't isolate
# cookies — same host, so the session set here is readable there.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Paths that must stay reachable regardless of load: the health probe the login
# page uses on the loopback, and the schema the docs page fetches.
_UNLIMITED = frozenset({"/health", "/v1/openapi.json", "/v1/docs"})

# Server-sent event streams are long-lived by design. They are opened once
# per page rather than per interaction, and counting a 15-minute stream
# against a per-minute budget would throttle a user who did nothing wrong.
_UNLIMITED_PREFIXES = ("/v1/jobs/stream/",)

# Safe methods get the read budget, everything else the mutation budget.
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


@app.middleware("http")
async def rate_limit(request: Request, call_next: Any) -> Any:
    """Per-session where there is a session, per-IP where there is not.

    docs/08-infrastructure.md §27 Layer 4 keys every limit to a session or an
    org, which leaves unauthenticated callers unbounded — fine when the app only
    ever listened on localhost, not fine once it is on the internet. Falling
    back to the source address closes that gap.
    """
    if request.url.path in _UNLIMITED or request.url.path.startswith(
        _UNLIMITED_PREFIXES
    ):
        return await call_next(request)

    token = request.cookies.get(SESSION_COOKIE)
    if token:
        # Hashed, so a bucket key is never the live session secret.
        key, scope = hash_token(token), "session"
    else:
        key, scope = client_ip(request), "ip"

    rule = READ if request.method in _SAFE_METHODS else MUTATION
    if not limiter.allow(key, rule, scope=scope):
        retry = limiter.retry_after(key, rule, scope=scope)
        log.warning("http.rate_limited", path=request.url.path, scope=scope)
        response = _problem(
            429, "rate-limited", "Too many requests",
            "Slow down and try again.", retry_after=retry,
        )
        response.headers["Retry-After"] = str(retry)
        return response

    return await call_next(request)


@app.middleware("http")
async def request_context(request: Request, call_next: Any) -> Any:
    request_id = str(ulid.ULID())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    if request.url.path not in ("/health", "/v1/openapi.json"):
        log.info(
            "http.request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
        )
    return response


def _problem(status: int, kind: str, title: str, detail: str, **extra: Any) -> JSONResponse:
    """RFC 9457 Problem Details — see docs/06-api-auth.md §15."""
    return JSONResponse(
        status_code=status,
        content={
            "type": f"https://seo-os.local/errors/{kind}",
            "title": title,
            "status": status,
            "detail": detail,
            **extra,
        },
    )


@app.exception_handler(QuotaError)
async def handle_quota(_r: Request, exc: QuotaError) -> JSONResponse:
    return _problem(429, "quota-exhausted", "Upstream quota exhausted",
                    str(exc), retry_after=exc.retry_after)


@app.exception_handler(AuthError)
async def handle_auth(_r: Request, exc: AuthError) -> JSONResponse:
    return _problem(403, "forbidden", "Not permitted", str(exc))


@app.exception_handler(PermanentError)
async def handle_permanent(_r: Request, exc: PermanentError) -> JSONResponse:
    return _problem(400, "invalid-request", "Request cannot be completed", str(exc))


@app.exception_handler(TransientError)
async def handle_transient(_r: Request, exc: TransientError) -> JSONResponse:
    return _problem(503, "temporarily-unavailable", "Temporarily unavailable", str(exc))


@app.exception_handler(Exception)
async def handle_unhandled(request: Request, exc: Exception) -> JSONResponse:
    error_id = str(ulid.ULID())
    log.exception("unhandled", error_id=error_id, path=request.url.path)
    return _problem(
        500, "internal", "Something went wrong",
        f"Error ID {error_id}. See logs/app.log.",
    )


@app.get("/health", tags=["ops"])
async def health() -> JSONResponse:
    db = await healthcheck()
    checks = {
        "postgres": db,
        "google_oauth": {"configured": settings.google_configured},
        # Reported but NOT part of `ok`: the pipeline, dashboards and analytics
        # all work with Ollama down. Only report generation stops, and failing
        # the whole health check for that would take the app out of service
        # over a degraded feature.
        "ollama": await ai_health(),
    }
    ok = bool(db.get("ok"))
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"ok": ok, "version": app.version, "env": settings.env, "checks": checks},
    )


app.include_router(auth.router)
app.include_router(orgs.router)
app.include_router(google.router)
app.include_router(jobs.router)
