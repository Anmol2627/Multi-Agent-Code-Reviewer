# graph/state.py
# ─────────────────────────────────────────────────────────
# Defines the shared state TypedDict that flows through every
# node in the LangGraph graph. Every agent reads from and
# writes back to this single state object.
# ─────────────────────────────────────────────────────────

from typing import TypedDict, Annotated
from langgraph.graph import add_messages


class Finding(TypedDict):
    severity: str          # "critical" | "high" | "medium" | "low"
    line: int              # line number in diff (-1 if unknown)
    file: str              # file name
    description: str       # what the issue is
    recommendation: str    # how to fix it
    agent: str             # which agent found it


class ReviewState(TypedDict):
    # ── Input ──────────────────────────────────────────────
    pr_diff: str                        # raw unified diff string
    pr_metadata: dict                   # title, author, repo, pr_number, files

    # ── Per-agent findings ─────────────────────────────────
    security_findings: list[Finding]
    performance_findings: list[Finding]
    style_findings: list[Finding]

    # ── Synthesized output ─────────────────────────────────
    final_report: str                   # markdown PR comment
    severity_summary: dict              # {"critical":1,"high":2,...}
    total_issues: int

    # ── LangGraph message thread ───────────────────────────
    messages: Annotated[list, add_messages]

    # ── Metadata ───────────────────────────────────────────
    # Allow multiple agents to append error messages concurrently.
    error: Annotated[list[str], add_messages]


# ── IMPROVEMENT IDEAS ──────────────────────────────────────
# 1. Add "human_feedback" field for human-in-the-loop review
#    before the final report is posted to GitHub.
# 2. Add "language_detected" field — orchestrator detects the
#    language from the diff and specialized agents adjust prompts.
# 3. Add "previous_findings" to track repeat offenders across PRs.
# 4. Add "approved: bool" so you can add a conditional edge
#    that auto-approves PRs with zero critical/high findings.
