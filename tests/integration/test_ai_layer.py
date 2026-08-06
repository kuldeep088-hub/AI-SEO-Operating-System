"""The AI layer's invariants — docs/07-ai-architecture.md §17–18.

These test the rules that make the output trustworthy, not the model. Model
quality is judged by reading a report; what has to be *guaranteed* is that
prompts are data, that reasoning is off unless a prompt asks for it, and that
causal language is detected when it appears.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from packages.ai.agents.report_narrator import find_causal_language
from packages.ai.prompts import PromptNotFoundError, load_prompt, xml_block, xml_rows
from packages.db.engine import close_pool, init_pool, system_tx


@pytest_asyncio.fixture
async def engine_pool() -> AsyncIterator[None]:
    await init_pool(min_size=1, max_size=2)
    try:
        yield
    finally:
        await close_pool()


# ── Prompts are data, not code (CLAUDE.md rule 4) ────────────────────────────


@pytest.mark.asyncio
async def test_narrator_prompt_is_loaded_from_the_database(
    engine_pool: None,
) -> None:
    async with system_tx() as conn:
        prompt = await load_prompt(conn, "report.narrator")

    assert prompt.system, "the body lives in prompt_versions, not a string literal"
    assert prompt.output_schema is not None
    assert prompt.id, "agent_runs.prompt_version_id needs this for provenance"


@pytest.mark.asyncio
async def test_missing_prompt_fails_loudly(engine_pool: None) -> None:
    """Permanent, not transient — retrying cannot conjure a prompt row."""
    async with system_tx() as conn:
        with pytest.raises(PromptNotFoundError):
            await load_prompt(conn, "no.such.prompt")


@pytest.mark.asyncio
async def test_exactly_one_active_version_per_key(engine_pool: None) -> None:
    """Migration 0001's partial unique index is what enforces §18's rule that a
    change flips is_active rather than editing in place."""
    async with system_tx() as conn:
        active = await conn.fetchval(
            "SELECT count(*) FROM prompt_versions WHERE key = $1 AND is_active",
            "report.narrator",
        )
    assert active == 1


@pytest.mark.asyncio
async def test_reasoning_is_off_for_the_active_narrator(engine_pool: None) -> None:
    """Measured, not assumed: think=on cost 187s vs 4.3s for equivalent output
    on this model, so migration 0003 turned it off. If someone reactivates v1
    this fails, which is the point — it should be a deliberate choice."""
    async with system_tx() as conn:
        prompt = await load_prompt(conn, "report.narrator")
    assert prompt.think is False


# ── Never state a cause without evidence (CLAUDE.md rule 7) ──────────────────


@pytest.mark.parametrize(
    "text",
    [
        "Clicks rose because of the new page.",
        "Traffic fell due to the algorithm update.",
        "The increase was driven by branded search.",
        "This resulted in more conversions.",
        "The redesign led to better rankings.",
        "Rankings improved thanks to the fixes.",
    ],
)
def test_causal_claims_are_detected(text: str) -> None:
    assert find_causal_language(text), f"undetected causal claim: {text!r}"


@pytest.mark.parametrize(
    "text",
    [
        "Clicks rose by 40%, and the new page went live in the same period.",
        "Traffic fell 12% over the month. A Google update was announced on 14 June.",
        "Impressions grew while average position held at 8.8.",
        "This change is consistent with the additional coverage.",
    ],
)
def test_co_occurrence_phrasing_is_allowed(text: str) -> None:
    """The permitted register: two things happened, no claim about which caused
    which. If this ever starts failing, the report copy has been made unusable
    rather than made safe."""
    assert find_causal_language(text) == []


# ── Prompt composition (§18) ─────────────────────────────────────────────────


def test_xml_block_uses_tags_not_markdown() -> None:
    """§18: a 9B model confuses markdown headings with content that itself
    contains markdown, which crawled pages and query strings routinely do."""
    out = xml_block("site", {"domain": "acme.com", "pages": 1842})
    assert out.startswith("<site>") and out.endswith("</site>")
    assert "domain: acme.com" in out
    assert "#" not in out


def test_xml_block_omits_missing_values() -> None:
    """A `key: None` line invites the model to write about a null."""
    out = xml_block("site", {"domain": "acme.com", "platform": None})
    assert "platform" not in out


def test_xml_rows_truncates_and_says_so() -> None:
    """§17's third pattern: attention degrades over long inputs, so the caller
    chunks — and the model is told rows were withheld rather than being left to
    assume it saw everything."""
    rows = [{"query": f"q{i}", "clicks": i} for i in range(40)]
    out = xml_rows("top_queries", rows, limit=10)

    assert out.count("- query=") == 10
    assert "(30 more not shown)" in out
