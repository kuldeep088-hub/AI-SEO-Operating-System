"""Report Narrator v2 — reasoning off, on measured evidence.

docs/07-ai-architecture.md §17 lists the Report Narrator as one of three agents
that run with `think` **on**, on the reasoning that its task is genuinely
open-ended prose rather than structured extraction. That was a design-time
judgement. This is the measurement, taken on this machine with qwen3.5:9b and a
deliberately small report payload:

    think=false    4.3s     76 output tokens
    think=true   187.0s     88 output tokens + 11,100 characters of
                            chain-of-thought, discarded

**43x the wall-clock for a materially identical summary.** On a full report
payload it exceeded a 300s ceiling entirely. §17's own headline finding is that
this flag cost the sibling project 27s → 0.8s; the same effect applies here, and
the schema constraint is doing the work that the reasoning was supposed to add.

docs/12-roadmap.md is explicit that week 7-8 exists to produce exactly this kind
of finding — "the moment to honestly assess whether the local model's narrative
quality is good enough. If it isn't, that finding arrives in week 8, not week
20." So it is recorded here rather than absorbed as a slow report.

This is also why prompts are data (§18). Nothing in `packages/ai/` changes: the
agent reads `model_hint` off whichever version is active. Turning reasoning
back on to compare quality is one UPDATE, and `agent_runs.prompt_version_id`
keeps every past report attributable to the version that produced it.

Revision ID: 0003
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A change inserts a new version and flips is_active — §18: prompts are
    # never edited in place, or the provenance recorded on past agent_runs rows
    # silently becomes wrong.
    #
    # Deactivate FIRST. Migration 0001 carries
    #   CREATE UNIQUE INDEX ON prompt_versions (key) WHERE is_active
    # which enforces exactly one live version per key, so inserting an active
    # v2 while v1 is still active raises UniqueViolation. The index is the
    # schema making §18's "flip is_active" rule non-optional — worth keeping
    # the order in mind for every future prompt revision.
    op.execute(
        sa.text(
            "UPDATE prompt_versions SET is_active = false "
            "WHERE key = :key AND version = 1"
        ).bindparams(key="report.narrator")
    )
    op.execute(
        sa.text(
            """
            INSERT INTO prompt_versions (key, version, body, output_schema,
                                         model_hint, is_active, notes)
            SELECT key, 2, body, output_schema, NULL, true, :notes
            FROM   prompt_versions
            WHERE  key = :key AND version = 1
            """
        ).bindparams(
            key="report.narrator",
            notes=(
                "Identical body and schema to v1; reasoning turned off. "
                "Measured on qwen3.5:9b: think=true 187s vs think=false 4.3s "
                "for an equivalent summary, and a full payload exceeded 300s. "
                "Set model_hint='think=on' to compare quality."
            ),
        )
    )


def downgrade() -> None:
    # Same ordering constraint in reverse: v2 has to stop being active before
    # v1 can start again.
    op.execute(
        sa.text(
            "DELETE FROM prompt_versions WHERE key = :key AND version = 2"
        ).bindparams(key="report.narrator")
    )
    op.execute(
        sa.text(
            "UPDATE prompt_versions SET is_active = true "
            "WHERE key = :key AND version = 1"
        ).bindparams(key="report.narrator")
    )
