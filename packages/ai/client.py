"""Ollama chat client — docs/07-ai-architecture.md §17.

Speaks Ollama's HTTP API directly through httpx rather than the `ollama`
Python package. The package would be a new dependency (CLAUDE.md rule 11) for
what is one POST to the loopback, and httpx is already here.

Two behaviours from §17 are enforced here rather than left to callers:

**Schema-constrained decoding.** `format` is a JSON Schema that Ollama's
sampler enforces, so the output is valid *by construction*. No regex scraping,
no parse-retry loop, no "please respond only with JSON" in the prompt.

**Reasoning off by default.** Qwen 3.5 is a reasoning model; left on it emits
hundreds of chain-of-thought tokens before the JSON and a structured call takes
minutes instead of seconds — the sibling project measured 27s → 0.8s from this
one flag. The schema already constrains the shape, so reasoning buys nothing
for structured work. Three agents turn it back on because they are genuinely
open-ended (Action Plan, Chat, Report Narrator); they do it per prompt via
`prompt_versions.model_hint`, never by changing this default.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import httpx

from packages.core.config import settings
from packages.core.errors import TransientError
from packages.core.logging import get_logger

log = get_logger(__name__)

__all__ = ["AiUnavailableError", "ChatResult", "chat", "health"]

# A structured call with reasoning off answers in a few seconds; a cold model
# load adds tens more. The ceiling is set for the reasoning-on case, which
# measured 187s on this machine for a *small* payload — see migration 0003.
DEFAULT_TIMEOUT_S = 900.0


class AiUnavailableError(TransientError):
    """Ollama is not reachable, or the model is not pulled.

    Transient on purpose: the queue should retry a report whose only problem is
    that Ollama was restarting, rather than marking it permanently dead.
    """


@dataclass(frozen=True, slots=True)
class ChatResult:
    content: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    duration_ms: int

    def json(self) -> Any:
        """Parse the content as JSON.

        Safe to call without a try/except only when the request supplied a
        `format` schema — that is what makes the output valid by construction.
        """
        return json.loads(self.content)


async def health() -> dict[str, Any]:
    """Whether Ollama is up and which models it has."""
    try:
        async with httpx.AsyncClient(timeout=5) as http:
            res = await http.get(f"{settings.ollama_host}/api/tags")
            res.raise_for_status()
            models = [m["name"] for m in res.json().get("models", [])]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        return {"ok": False, "error": str(exc)[:200], "models": []}

    return {
        "ok": settings.ollama_model in models,
        "models": models,
        "configured_model": settings.ollama_model,
    }


async def chat(
    *,
    system: str,
    user: str,
    schema: dict[str, Any] | None = None,
    think: bool | None = None,
    temperature: float = 0.2,
    num_ctx: int = 8192,
    model: str | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> ChatResult:
    """One call to the local model.

    `think` defaults to the global setting (normally False). Pass True only for
    the genuinely open-ended agents named in §17.
    """
    resolved_model = model or settings.ollama_model
    resolved_think = settings.ollama_think if think is None else think

    payload: dict[str, Any] = {
        "model": resolved_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "think": resolved_think,
        "options": {"temperature": temperature, "num_ctx": num_ctx},
    }
    if schema is not None:
        payload["format"] = schema

    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as http:
            res = await http.post(f"{settings.ollama_host}/api/chat", json=payload)
    # Timeout and unreachable are both httpx.HTTPError but mean entirely
    # different things, and reporting a slow model as "is it running?" sends
    # whoever reads the log to check a service that was never down.
    except httpx.TimeoutException as exc:
        raise AiUnavailableError(
            f"Ollama did not answer within {timeout_s:.0f}s "
            f"(model={resolved_model}, think={resolved_think}). Reasoning on is "
            f"roughly 40x slower than off; if this is a structured call it "
            f"almost certainly wants think=False."
        ) from exc
    except httpx.HTTPError as exc:
        raise AiUnavailableError(
            f"Ollama unreachable at {settings.ollama_host}. Is it running? "
            f"Start it with ./bin/ollama serve, or run ./setup.sh. ({exc})"
        ) from exc

    if res.status_code == 404:
        raise AiUnavailableError(
            f"Model '{resolved_model}' is not pulled. "
            f"Run: ./bin/ollama pull {resolved_model}"
        )
    if res.status_code >= 400:
        raise AiUnavailableError(f"Ollama returned {res.status_code}: {res.text[:200]}")

    body = res.json()
    duration_ms = int((time.monotonic() - started) * 1000)
    content = body.get("message", {}).get("content", "")

    log.info(
        "ai.chat",
        model=resolved_model,
        think=resolved_think,
        duration_ms=duration_ms,
        completion_tokens=body.get("eval_count"),
        structured=schema is not None,
    )

    return ChatResult(
        content=content,
        model=resolved_model,
        prompt_tokens=body.get("prompt_eval_count"),
        completion_tokens=body.get("eval_count"),
        duration_ms=duration_ms,
    )
