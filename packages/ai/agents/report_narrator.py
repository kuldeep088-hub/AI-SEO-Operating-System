"""Report Narrator — docs/07-ai-architecture.md §17, roster row 7.

Writes the executive summary and narrative sections of a monthly report. One
of the three agents that run with reasoning **on**, because the task is
genuinely open-ended prose rather than a structured extraction.

Two invariants this module exists to hold:

**The model never computes a number** (CLAUDE.md rule 6). Every figure in the
report is aggregated in SQL by `assemble_report_data` and handed over already
calculated. The model's job is to explain figures, not derive them — a 9B model
doing percentage change in its head produces a wrong number inside a confident
sentence, which is worse than no number.

**The model never states a cause** (CLAUDE.md rule 7). The prompt forbids it,
and `strip_causal_language` checks the output afterwards, because a prompt rule
is a request and this is a guarantee. Reports say "X happened, and Y occurred in
the same period" — never "X happened because of Y".
"""

from __future__ import annotations

import re
from typing import Any

import asyncpg

from packages.ai.client import chat
from packages.ai.prompts import load_prompt, xml_block, xml_rows
from packages.core.logging import get_logger

log = get_logger(__name__)

__all__ = ["CAUSAL_PATTERNS", "find_causal_language", "narrate_report"]

PROMPT_KEY = "report.narrator"

# Phrases that assert causation. Checked against the model's output because the
# prompt can only ask; this is what verifies. Deliberately narrow — matching
# "since" or "so" would fire on ordinary prose and train us to ignore it.
CAUSAL_PATTERNS = [
    r"\bbecause of\b",
    r"\bbecause\b",
    r"\bdue to\b",
    r"\bas a result of\b",
    r"\bdriven by\b",
    r"\bcaused by\b",
    r"\bresulted in\b",
    r"\bled to\b",
    r"\bthanks to\b",
    r"\bowing to\b",
]

_CAUSAL_RE = re.compile("|".join(CAUSAL_PATTERNS), re.IGNORECASE)


def find_causal_language(text: str) -> list[str]:
    """Every causal assertion in `text`. Empty means the output is compliant."""
    return [m.group(0) for m in _CAUSAL_RE.finditer(text)]


def _build_task(data: dict[str, Any]) -> str:
    """Layers 3 and 4 of §18's composition — context, then task.

    XML delimiters rather than markdown headings: a 9B model confuses `##` with
    content that itself contains markdown, and query strings and page titles
    frequently do.
    """
    site = data["site"]
    totals = data["totals"]

    blocks = [
        xml_block(
            "site",
            {
                "domain": site["domain"],
                "client": site["client_name"],
                "period": f"{data['period_start']} to {data['period_end']}",
                "days_of_data": data["days_with_data"],
            },
        ),
        xml_block(
            "search_performance",
            {
                "clicks": totals["clicks"],
                "clicks_previous_period": totals["prev_clicks"],
                "clicks_change_pct": totals["clicks_change_pct"],
                "impressions": totals["impressions"],
                "impressions_previous_period": totals["prev_impressions"],
                "impressions_change_pct": totals["impressions_change_pct"],
                "ctr_pct": totals["ctr_pct"],
                "average_position": totals["avg_position"],
                "average_position_previous_period": totals["prev_avg_position"],
                # Named so the model cannot mistake the sign convention: a
                # falling position number is an improvement.
                "position_change_lower_is_better": totals["position_change"],
            },
        ),
    ]

    if data["analytics"]:
        blocks.append(xml_block("analytics", data["analytics"]))

    if data["top_queries"]:
        blocks.append(xml_rows("top_queries", data["top_queries"], limit=15))
    if data["risers"]:
        blocks.append(xml_rows("queries_that_gained_clicks", data["risers"], limit=10))
    if data["fallers"]:
        blocks.append(xml_rows("queries_that_lost_clicks", data["fallers"], limit=10))
    if data["top_pages"]:
        blocks.append(xml_rows("top_pages", data["top_pages"], limit=10))
    if data["opportunities"]:
        blocks.append(
            xml_rows("queries_ranking_5_to_20", data["opportunities"], limit=10)
        )

    blocks.append(
        "<task>\n"
        "Write the narrative for this month's report.\n"
        "  - summary: 3-5 sentences the client reads first.\n"
        "  - sections: 2-4 sections covering what changed in search "
        "performance, which queries and pages moved, and where the "
        "opportunity is next month.\n"
        "  - confidence: how well the data supports what you have written.\n"
        "  - data_caveat: name any limitation a reader should know about, "
        "such as a short measurement period.\n"
        "Use only the numbers given above.\n"
        "</task>"
    )
    return "\n\n".join(blocks)


async def narrate_report(
    conn: asyncpg.Connection,
    *,
    org_id: str,
    site_id: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Generate the narrative and record the run in `agent_runs`.

    `conn` must already be tenant-scoped — `agent_runs` is an RLS-protected
    tenant table, so writing it without an org context fails its WITH CHECK.
    """
    prompt = await load_prompt(conn, PROMPT_KEY)
    task = _build_task(data)

    run_id = await conn.fetchval(
        """INSERT INTO agent_runs (org_id, site_id, agent, trigger,
                                   prompt_version_id, model, input, status)
           VALUES ($1, $2, 'report_narrator', 'job', $3, $4, $5::jsonb, 'running')
           RETURNING id""",
        org_id, site_id, prompt.id, "pending",
        _json({"period": f"{data['period_start']}..{data['period_end']}"}),
    )

    try:
        result = await chat(
            system=prompt.system,
            user=task,
            schema=prompt.output_schema,
            # think=on for this agent, carried as data on the prompt row.
            think=prompt.think,
            temperature=0.3,
            num_ctx=8192,
        )
        narrative: dict[str, Any] = result.json()
    except Exception as exc:
        await conn.execute(
            """UPDATE agent_runs SET status = 'failed', error = $2,
                                     finished_at = now() WHERE id = $1""",
            run_id, str(exc)[:500],
        )
        raise

    # The prompt asks the model not to assert causation. This verifies it.
    prose = " ".join(
        [narrative.get("summary", "")]
        + [s.get("body", "") for s in narrative.get("sections", [])]
    )
    violations = find_causal_language(prose)
    if violations:
        # Recorded, not silently accepted: rule 7 is a product guarantee, and a
        # regression here should be visible in the data rather than only in a
        # client's inbox.
        log.warning(
            "report_narrator.causal_language",
            site_id=site_id,
            phrases=sorted({v.lower() for v in violations}),
        )

    await conn.execute(
        """UPDATE agent_runs
           SET status = 'succeeded', output = $2::jsonb, model = $3,
               prompt_tokens = $4, completion_tokens = $5, duration_ms = $6,
               finished_at = now()
           WHERE id = $1""",
        run_id, _json(narrative), result.model,
        result.prompt_tokens, result.completion_tokens, result.duration_ms,
    )

    log.info(
        "report_narrator.done",
        site_id=site_id,
        duration_ms=result.duration_ms,
        sections=len(narrative.get("sections", [])),
        confidence=narrative.get("confidence"),
        causal_violations=len(violations),
    )

    narrative["_meta"] = {
        "prompt_version_id": prompt.id,
        "prompt_version": prompt.version,
        "model": result.model,
        "duration_ms": result.duration_ms,
        "causal_violations": sorted({v.lower() for v in violations}),
    }
    return narrative


def _json(value: Any) -> str:
    import json

    return json.dumps(value, default=str)
