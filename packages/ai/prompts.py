"""Prompt loading and composition — docs/07-ai-architecture.md §18.

**Prompts are versioned data, not code** (CLAUDE.md rule 4). The body lives in
`prompt_versions`, never in a Python string literal, because:

- it can be tuned without a redeploy, which matters constantly while shaping a
  9B model's output;
- `agent_runs.prompt_version_id` records which version produced which output,
  so a quality regression is traceable to one edit;
- comparing two versions is a query rather than git archaeology.

A prompt is never edited in place. A change inserts a new row and flips
`is_active` — see migration 0002.

The four-layer composition (§18) is assembled here, most stable first, so the
model sees who it is before what it must do:

    1 IDENTITY  per agent, changes rarely   ─┐ stored in prompt_versions.body
    2 RULES     per agent                   ─┘
    3 CONTEXT   per site, from memory        ─┐ supplied per call
    4 TASK      per call                     ─┘

Layers 3 and 4 use XML-style delimiters rather than markdown headings. §18 is
specific about why: a 9B model confuses `## Heading` with content that itself
contains markdown, which crawled page bodies and query exports invariably do.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import asyncpg

from packages.core.errors import PermanentError
from packages.core.logging import get_logger

log = get_logger(__name__)

__all__ = ["PromptNotFoundError", "RenderedPrompt", "load_prompt", "xml_block"]


class PromptNotFoundError(PermanentError):
    """No active version for this key.

    Permanent rather than transient: retrying cannot conjure a prompt row, and
    a job that retries forever on a missing prompt hides the real problem.
    """


@dataclass(frozen=True, slots=True)
class RenderedPrompt:
    """An active prompt plus everything the caller needs to record the run."""

    id: str
    key: str
    version: int
    system: str
    output_schema: dict[str, Any] | None
    model_hint: str | None

    @property
    def think(self) -> bool:
        """Whether this prompt wants reasoning on.

        §17 keeps `think=False` global and lets three open-ended agents opt back
        in per prompt. `model_hint` carries that as `think=on`, so flipping it
        is a data edit rather than a code change.
        """
        return bool(self.model_hint and "think=on" in self.model_hint)


async def load_prompt(conn: asyncpg.Connection, key: str) -> RenderedPrompt:
    """The active version of `key`.

    `prompt_versions` is not a tenant table — prompts are system-wide — so this
    is safe on either a tenant or a system connection.
    """
    row = await conn.fetchrow(
        """SELECT id, key, version, body, output_schema, model_hint
           FROM   prompt_versions
           WHERE  key = $1 AND is_active
           ORDER  BY version DESC LIMIT 1""",
        key,
    )
    if row is None:
        raise PromptNotFoundError(
            f"No active prompt for '{key}'. Prompts are seeded by migration — "
            f"run `uv run alembic upgrade head`."
        )

    schema = row["output_schema"]
    if isinstance(schema, str):
        import json

        schema = json.loads(schema)

    return RenderedPrompt(
        id=str(row["id"]),
        key=row["key"],
        version=row["version"],
        system=row["body"],
        output_schema=schema,
        model_hint=row["model_hint"],
    )


def xml_block(tag: str, fields: dict[str, Any]) -> str:
    """One XML-delimited context block, per §18.

    Values are rendered as `key: value` lines rather than nested XML — the
    extra structure costs tokens and a 9B model reads the flat form at least as
    reliably.
    """
    lines = "\n".join(f"  {k}: {v}" for k, v in fields.items() if v is not None)
    return f"<{tag}>\n{lines}\n</{tag}>"


def xml_rows(tag: str, rows: list[dict[str, Any]], limit: int = 25) -> str:
    """A repeated block for tabular context (queries, pages, issues).

    Truncated deliberately: §17's third pattern is that a 9B model's attention
    degrades across long inputs, so the caller chunks and aggregates in code
    rather than pasting three thousand rows and hoping.
    """
    shown = rows[:limit]
    body = "\n".join(
        "  - " + ", ".join(f"{k}={v}" for k, v in row.items()) for row in shown
    )
    omitted = len(rows) - len(shown)
    suffix = f"\n  ({omitted} more not shown)" if omitted > 0 else ""
    return f"<{tag}>\n{body}{suffix}\n</{tag}>"
