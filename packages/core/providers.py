"""Provider adapters — the pattern that keeps this system at $0.

Both the LLM layer (§17) and the SERP layer (§27) use the same shape: a local
implementation that is the default and costs nothing, and a remote one that is
off unless the user explicitly enables it per task kind with their own key.

Three properties this guarantees:
  1. Nothing leaves the machine unless explicitly ticked in Settings.
  2. The platform never carries a recurring cost.
  3. No code path assumes a provider — switching is config, not a refactor.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from packages.core.config import settings


@runtime_checkable
class LLMProvider(Protocol):
    async def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
        think: bool = False,
    ) -> Any: ...


class OllamaProvider:
    """Default. Local inference on the Apple GPU. $0 at any volume.

    `think` defaults to False: Qwen 3.5 is a reasoning model, and with
    schema-constrained output the chain-of-thought buys nothing while costing
    ~30x the latency (measured 27s -> 0.8s in Growleads L.S).
    """

    def __init__(self, model: str | None = None) -> None:
        self.model = model or settings.ollama_model
        self.host = settings.ollama_host

    async def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
        think: bool = False,
    ) -> Any:
        raise NotImplementedError("Implemented in Phase 1 — see docs/07-ai-architecture.md §17")


class RemoteProvider:
    """Opt-in only. Uses the user's own API key, billed to them.

    Invoked exclusively for task kinds the user ticked in Settings. Never a
    default, never a fallback.
    """

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("RemoteProvider requires an API key")
        self.api_key = api_key
        self.model = model

    async def complete(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
        think: bool = False,
    ) -> Any:
        raise NotImplementedError("Implemented when a deliverable needs it — §17")


def provider_for(task_kind: str, org_settings: dict[str, Any] | None = None) -> LLMProvider:
    """Resolve the provider for a task. Local unless explicitly opted out."""
    remote = (org_settings or {}).get("remote_llm", {})
    if remote.get("enabled") and task_kind in remote.get("task_kinds", []):
        key = remote.get("api_key") or settings.remote_llm_api_key
        if key:
            return RemoteProvider(key, remote.get("model", ""))
    return OllamaProvider()


@runtime_checkable
class SerpProvider(Protocol):
    async def fetch(self, query: str, *, location: str, device: str) -> Any: ...


class LocalScraper:
    """Default. $0. Hard-capped and deliberately slow.

    The cap is enforced in code, not documented as a guideline: exceeding it
    produces CAPTCHAs, which produce garbage that silently pollutes
    rank_history — worse than no data at all. See §27.
    """

    DAILY_CAP = 200
    MIN_DELAY_S = 12

    async def fetch(self, query: str, *, location: str, device: str) -> Any:
        raise NotImplementedError("Implemented in Phase 3")


class ApifyProvider:
    """Opt-in. User's own token, user's own bill. Off by default."""

    def __init__(self, token: str, monthly_cap: int = 5000) -> None:
        if not token:
            raise ValueError("ApifyProvider requires a token")
        self.token = token
        self.monthly_cap = monthly_cap

    async def fetch(self, query: str, *, location: str, device: str) -> Any:
        raise NotImplementedError("Implemented if enabled — §27")


def serp_provider_for(org_settings: dict[str, Any] | None = None) -> SerpProvider:
    serp = (org_settings or {}).get("serp", {})
    if serp.get("provider") == "apify":
        token = serp.get("token") or settings.apify_token
        if token:
            return ApifyProvider(token, serp.get("monthly_cap", 5000))
    return LocalScraper()
