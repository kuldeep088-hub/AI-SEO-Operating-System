"""Report data assembly — docs/12-roadmap.md Phase 1 week 8.

Lives in `packages/` because both the worker (which generates reports on a
schedule) and the API (which regenerates one on demand) need it, and CLAUDE.md
rule 8 forbids duplicating domain logic between the two.
"""

from packages.reporting.assemble import assemble_report_data

__all__ = ["assemble_report_data"]
