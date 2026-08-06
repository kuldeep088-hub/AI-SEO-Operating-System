"""Agents — docs/07-ai-architecture.md §17.

One job each, a fixed tool set, and a JSON schema for the output.
"""

from packages.ai.agents.report_narrator import narrate_report

__all__ = ["narrate_report"]
