"""The local AI layer — docs/07-ai-architecture.md §17–18.

Everything here talks to Ollama on the loopback. There is no cloud fallback in
a default path: `packages/core/providers.py` holds the opt-in `RemoteProvider`
behind `LLMProvider`, and turning it on is a deliberate decision, not a config
accident (CLAUDE.md rule 1).
"""

from packages.ai.client import AiUnavailableError, ChatResult, chat, health
from packages.ai.prompts import PromptNotFoundError, RenderedPrompt, load_prompt

__all__ = [
    "AiUnavailableError",
    "ChatResult",
    "PromptNotFoundError",
    "RenderedPrompt",
    "chat",
    "health",
    "load_prompt",
]
