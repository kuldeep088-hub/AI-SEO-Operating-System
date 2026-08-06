"""Structured JSON logging with secret redaction.

Redaction is a processor, not a convention. A convention fails the first time
someone logs an exception whose message contains a URL with a token in it.
See docs/09-security-ops.md §30.
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import MutableMapping
from logging.handlers import RotatingFileHandler
from typing import Any

import structlog

from packages.core.config import settings

SECRET_KEYS = {
    "access_token", "refresh_token", "id_token", "api_key", "token",
    "password", "secret", "authorization", "cookie", "session",
    "apify_token", "passcode", "client_secret", "token_encryption_key",
}

SECRET_PATTERNS = [
    re.compile(r"\bya29\.[\w\-.]+"),            # Google access tokens
    re.compile(r"\b1//[\w\-.]{20,}"),           # Google refresh tokens
    re.compile(r"\bsk-[A-Za-z0-9\-_]{20,}"),
    re.compile(r"\bapify_api_[A-Za-z0-9]+"),
    re.compile(r"\bgAAAAA[A-Za-z0-9\-_=]{20,}"),  # Fernet ciphertext
]


def redact_secrets(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key in list(event_dict):
        if key.lower() in SECRET_KEYS:
            event_dict[key] = "[redacted]"
            continue
        value = event_dict[key]
        if isinstance(value, str):
            for pattern in SECRET_PATTERNS:
                value = pattern.sub("[redacted]", value)
            event_dict[key] = value
    return event_dict


def configure_logging() -> None:
    settings.logs_dir.mkdir(exist_ok=True)

    handlers: list[logging.Handler] = [
        RotatingFileHandler(
            settings.logs_dir / "app.log", maxBytes=50 * 1024 * 1024, backupCount=5
        )
    ]
    if not settings.is_prod:
        handlers.append(logging.StreamHandler(sys.stdout))

    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        handlers=handlers,
    )

    renderer: Any = (
        structlog.processors.JSONRenderer()
        if settings.is_prod
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            redact_secrets,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> Any:
    return structlog.get_logger(name)
