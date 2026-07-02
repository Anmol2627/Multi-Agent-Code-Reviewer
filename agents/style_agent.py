# agents/style_agent.py
# ─────────────────────────────────────────────────────────
# Specialist agent focused on code quality and maintainability.
# Runs in parallel with security and performance agents.
# ─────────────────────────────────────────────────────────

import json
from langchain_openai import ChatOpenAI
from graph.state import ReviewState, Finding

llm = ChatOpenAI(model="gpt-4o", temperature=0)

STYLE_PROMPT = """You are a senior software engineer focused on code quality and maintainability.
Your ONLY job is identifying style, readability, and maintainability issues.
Do not comment on security or performance.

Scan the diff for:
- Unclear, ambiguous, or misleading variable/function names
- Missing docstrings or comments on public functions and classes
- Functions longer than 50 lines (suggest splitting)
- Code duplication (DRY violations — same logic copy-pasted)
- Missing or inconsistent error handling
- Magic numbers/strings (should be named constants)
- Deep nesting (>3 levels — suggest early returns)
- Dead code or commented-out code blocks
- Inconsistent naming conventions (camelCase vs snake_case)
- Missing type annotations (Python) or type definitions (TypeScript)

Return a JSON object:
{
  "findings": [
    {
      "severity": "high | medium | low",
      "line": <line number as integer, -1 if unknown>,
      "file": "<filename>",
      "description": "<what the style issue is and why it hurts maintainability>",
      "recommendation": "<concrete suggestion with example if possible>",
      "agent": "style"
    }
  ]
}

Style issues are NEVER "critical". Maximum severity is "high".
If you find NO issues, return: {"findings": []}
Return ONLY valid JSON. No preamble, no markdown fences.
"""


def style_node(state: ReviewState) -> dict:
    """
    Runs style/quality analysis on the PR diff.
    Returns style_findings list to be merged into shared state.
    """
    try:
        orchestrator_ctx = state.get("pr_metadata", {}).get("orchestrator", {})
        change_type_note = ""
        if orchestrator_ctx.get("change_type") == "test":
            change_type_note = "\nThis is a test file PR — focus on test quality: coverage, naming, assertions."

        response = llm.invoke([
            {"role": "system", "content": STYLE_PROMPT},
            {"role": "user",   "content": (
                f"Review this PR diff for style and maintainability issues.{change_type_note}\n\n"
                f"Diff:\n{state['pr_diff']}"
            )}
        ])

        data = json.loads(response.content)
        findings: list[Finding] = data.get("findings", [])

        for f in findings:
            f["agent"] = "style"
            # Enforce: style findings can't be critical
            if f.get("severity") == "critical":
                f["severity"] = "high"

        return {"style_findings": findings}

    except Exception as e:
        return {
            "style_findings": [],
            "error": f"Style agent error: {str(e)}"
        }


# ── IMPROVEMENT IDEAS ──────────────────────────────────────
# 1. Run black/prettier/ruff as a subprocess and inject the
#    formatted diff vs original into the prompt — shows exactly
#    which formatting changes are needed.
#
# 2. Add a "team style guide" context: let users upload a
#    STYLE_GUIDE.md and inject it into the system prompt so
#    the agent checks against their specific conventions.
#
# 3. Add complexity threshold configuration: let users set
#    max_function_length, max_nesting_depth via a config.yaml
#    and inject those as constraints into the prompt.
#
# 4. Separate "nitpick" findings (severity=low) from the main
#    PR comment into a collapsible GitHub section, so they
#    don't clutter the important findings.
