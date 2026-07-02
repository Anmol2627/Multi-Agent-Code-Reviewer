# agents/orchestrator.py
# ─────────────────────────────────────────────────────────
# The orchestrator is the FIRST node in the graph.
# Its job: inspect the diff, detect language, extract metadata,
# and set up shared context for the specialist agents.
# It does NOT do code review itself.
# ─────────────────────────────────────────────────────────

import json
from langchain_openai import ChatOpenAI
from graph.state import ReviewState

llm = ChatOpenAI(model="gpt-4o", temperature=0)

ORCHESTRATOR_PROMPT = """You are the orchestrator of a multi-agent code review system.
Your ONLY job is to analyse the PR metadata and prepare a structured context summary.

Given a PR diff, extract and return JSON with:
{
  "language": "python | javascript | typescript | go | java | other",
  "complexity": "low | medium | high",
  "files_changed": ["list", "of", "filenames"],
  "change_type": "feature | bugfix | refactor | config | test | docs",
  "summary": "One sentence describing what this PR does",
  "focus_areas": ["list of areas specialist agents should pay special attention to"]
}

Return ONLY valid JSON. No preamble, no explanation.
"""


def orchestrator_node(state: ReviewState) -> dict:
    """
    Analyses the diff and enriches pr_metadata with orchestrator insights.
    Downstream agents can read state['pr_metadata']['orchestrator'] for context.
    """
    try:
        response = llm.invoke([
            {"role": "system", "content": ORCHESTRATOR_PROMPT},
            {"role": "user",   "content": f"Analyse this PR diff:\n\n{state['pr_diff']}"}
        ])

        orchestrator_data = json.loads(response.content)

        # Merge orchestrator data into pr_metadata
        updated_metadata = {
            **state.get("pr_metadata", {}),
            "orchestrator": orchestrator_data
        }

        return {
            "pr_metadata": updated_metadata,
            # Initialise findings lists so parallel agents don't hit KeyError
            "security_findings":    [],
            "performance_findings": [],
            "style_findings":       [],
            "error":                ""
        }

    except (json.JSONDecodeError, Exception) as e:
        # Graceful degradation: orchestrator failure should not kill the review
        return {
            "pr_metadata": {
                **state.get("pr_metadata", {}),
                "orchestrator": {"language": "unknown", "summary": "Parse failed"}
            },
            "security_findings":    [],
            "performance_findings": [],
            "style_findings":       [],
            "error": [f"Orchestrator error: {str(e)}"]
        }


# ── IMPROVEMENT IDEAS ──────────────────────────────────────
# 1. Add language detection using pygments instead of LLM —
#    faster and cheaper for a task that doesn't need intelligence.
#
# 2. Add diff size check: if len(state['pr_diff']) > 50_000 chars,
#    chunk the diff and run agents on each chunk separately.
#
# 3. Add a "skip_review" flag: if the PR only changes markdown/
#    config files with no logic, set skip_review=True and route
#    to a lightweight summarizer instead of all three agents.
#
# 4. Fetch PR description and linked issue from GitHub and include
#    in context — agents can check if the code matches the intent.
