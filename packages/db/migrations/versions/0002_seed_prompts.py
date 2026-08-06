"""Seed the Report Narrator prompt — docs/07-ai-architecture.md §18.

Prompts are versioned data, not code (CLAUDE.md rule 4), so the body lives in
this table rather than in a Python string literal in the agent. A later tuning
pass inserts version 2 and flips `is_active`; it never edits this row, so
`agent_runs.prompt_version_id` keeps pointing at whatever actually produced a
given piece of output.

Two things in the body are load-bearing rather than stylistic:

* **The causation rules.** CLAUDE.md rule 7 forbids stating a cause without
  evidence, and a narrative generator is the single most likely place in this
  system to break it — "traffic fell because of the Google update" is exactly
  the sentence a language model wants to write, and exactly the one that is
  unsupportable from the data given. The rules make co-occurrence the only
  claim available.
* **The arithmetic prohibition.** CLAUDE.md rule 6: every number is computed in
  SQL and passed in. The model's job is to explain figures, never to derive
  them. A 9B model doing percentage change in its head is a wrong number
  delivered in a confident sentence.

Revision ID: 0002
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


REPORT_NARRATOR_BODY = """\
You are an SEO analyst writing the narrative section of a monthly performance \
report. Your reader is the client: an intelligent business owner who does not \
work in SEO. They want to know what changed, what it means for them, and what \
happens next.

<rules>
  - Every number you need has already been calculated and is given to you in \
the data block. Never calculate, estimate, re-derive or round a number \
yourself. If a figure you want is not provided, write around it rather than \
inventing it.
  - Never state that one thing caused another. You may state that two things \
happened in the same period, and you may say a change is "consistent with" \
something, but you must not write "because", "due to", "as a result of", or \
"driven by" about anything you cannot see directly in the data.
  - Do not speculate about Google algorithm updates, competitor activity, or \
seasonality unless that information appears in the data block.
  - Write plainly. No jargon without a plain-English gloss. No filler openings \
like "In today's competitive landscape".
  - Be honest when performance declined. A report that spins a bad month \
destroys trust the first time the client checks.
  - Where the data is thin or the period is short, say so plainly rather than \
drawing a conclusion the sample cannot support.
</rules>

<style>
  - Second person, addressing the client directly.
  - Short paragraphs. No bulleted lists inside section bodies.
  - British English.
</style>
"""

# maxLength is the effective verbosity control for a 9B model — far more
# reliable than "be concise" in the prompt (§18).
REPORT_NARRATOR_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "maxLength": 900},
        "sections": {
            "type": "array",
            "minItems": 2,
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string", "maxLength": 80},
                    "body": {"type": "string", "maxLength": 1200},
                },
                "required": ["heading", "body"],
                "additionalProperties": False,
            },
        },
        # Required so the model has a legitimate way to hedge *inside the
        # structure* rather than hedging in prose, which is what produces the
        # mushy "it may be possible that…" register that makes AI text obvious.
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "data_caveat": {"type": "string", "maxLength": 300},
    },
    "required": ["summary", "sections", "confidence"],
    "additionalProperties": False,
}


def upgrade() -> None:
    # Bound parameters rather than an f-string. A prompt body is prose full of
    # apostrophes and angle brackets, which is precisely the shape that makes
    # hand-rolled SQL escaping a bad idea — and it means the injection warning
    # is genuinely resolved rather than suppressed with a lint exemption.
    op.execute(
        sa.text(
            """
            INSERT INTO prompt_versions (key, version, body, output_schema,
                                         model_hint, is_active, notes)
            VALUES (:key, :version, :body, CAST(:schema AS jsonb),
                    :model_hint, true, :notes)
            """
        ).bindparams(
            key="report.narrator",
            version=1,
            body=REPORT_NARRATOR_BODY,
            schema=json.dumps(REPORT_NARRATOR_SCHEMA),
            # §17: reasoning is off globally and three open-ended agents turn it
            # back on. The Report Narrator is one of them, and it says so here
            # as data rather than in code.
            model_hint="think=on",
            notes=(
                "Initial Report Narrator. The causation and arithmetic "
                "prohibitions are CLAUDE.md rules 6 and 7 expressed as prompt "
                "rules."
            ),
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM prompt_versions WHERE key = :key AND version = :version"
        ).bindparams(key="report.narrator", version=1)
    )
