# agents/performance_agent.py
# ─────────────────────────────────────────────────────────
# Specialist agent focused exclusively on performance issues.
# Runs in parallel with security and style agents.
# ─────────────────────────────────────────────────────────

import json
from langchain_openai import ChatOpenAI
from graph.state import ReviewState, Finding

llm = ChatOpenAI(model="gpt-4o", temperature=0)

PERFORMANCE_PROMPT = """You are a senior performance engineer doing a pull request review.
Your ONLY job is identifying performance problems. Do not comment on security or style.

Scan the diff for:
- N+1 query patterns (database queries inside loops)
- Missing database indexes on frequently queried columns
- Inefficient algorithms (O(n²) where O(n) is achievable)
- Unnecessary re-computation inside loops (move outside)
- Missing caching where repeated identical calls occur
- Blocking I/O in async code paths
- Memory leaks (unclosed resources, growing lists in loops)
- Excessive object creation in hot paths
- Missing pagination on large dataset queries
- Unoptimised regex compiled inside loops

Return a JSON object:
{
  "findings": [
    {
      "severity": "critical | high | medium | low",
      "line": <line number as integer, -1 if unknown>,
      "file": "<filename>",
      "description": "<what the performance issue is and its impact>",
      "recommendation": "<concrete optimisation with example if possible>",
      "agent": "performance"
    }
  ]
}

If you find NO issues, return: {"findings": []}
Return ONLY valid JSON. No preamble, no markdown fences.
"""


def performance_node(state: ReviewState) -> dict:
    """
    Runs performance analysis on the PR diff.
    Returns performance_findings list to be merged into shared state.
    """
    try:
        orchestrator_ctx = state.get("pr_metadata", {}).get("orchestrator", {})
        complexity_note = ""
        if orchestrator_ctx.get("complexity") == "high":
            complexity_note = "\nThis PR is flagged as HIGH complexity — be thorough."

        response = llm.invoke([
            {"role": "system", "content": PERFORMANCE_PROMPT},
            {"role": "user",   "content": (
                f"Review this PR diff for performance issues.{complexity_note}\n\n"
                f"Diff:\n{state['pr_diff']}"
            )}
        ])

        data = json.loads(response.content)
        findings: list[Finding] = data.get("findings", [])

        for f in findings:
            f["agent"] = "performance"

        return {"performance_findings": findings}

    except Exception as e:
        return {
            "performance_findings": [],
            "error": f"Performance agent error: {str(e)}"
        }


# ── IMPROVEMENT IDEAS ──────────────────────────────────────
# 1. Add radon (Python) complexity analysis as a tool:
#    Run `radon cc <file> -s` on changed files and inject the
#    cyclomatic complexity scores into the prompt context.
#
# 2. Add language-specific linter output:
#    Python → pylint, JavaScript → ESLint with perf rules.
#    Run as subprocess, parse output, feed into prompt.
#
# 3. For database-heavy diffs, detect SQL patterns using regex
#    first (find SELECT inside for-loops) before even calling
#    the LLM — saves tokens on obvious N+1 cases.
#
# 4. Add benchmark suggestion: if a critical performance issue
#    is found, auto-generate a pytest-benchmark snippet the
#    developer can run to measure the improvement.
