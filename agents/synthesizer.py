# agents/synthesizer.py
# ─────────────────────────────────────────────────────────
# The synthesizer is the LAST node before END.
# It merges all agent findings, deduplicates, ranks by severity,
# and generates the final markdown PR comment.
# ─────────────────────────────────────────────────────────

import json
from langchain_openai import ChatOpenAI
from graph.state import ReviewState, Finding

llm = ChatOpenAI(model="gpt-4o", temperature=0)

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

SYNTHESIZER_PROMPT = """You are writing the final comment for a GitHub Pull Request code review.
You have been given structured findings from three specialist AI agents: security, performance, and style.

Your job:
1. Write a professional, helpful, and concise PR review comment in GitHub Markdown
2. Group findings by severity (critical first, then high, medium, low)
3. Be constructive — frame issues as suggestions, not criticisms
4. Include a summary section at the top
5. If there are zero issues across all agents, write an encouraging approval comment

Format the comment EXACTLY like this:

## 🤖 AI Code Review

### Summary
<One paragraph summarising the PR and overall code quality>

**{total} issue(s) found** — {critical} critical · {high} high · {medium} medium · {low} low

---

### 🔴 Critical Issues
<findings or "None">

### 🟠 High Issues  
<findings or "None">

### 🟡 Medium Issues
<findings or "None">

### 🟢 Low / Nitpicks
<findings or "None">

---
*Review by [Security Agent 🛡️] [Performance Agent ⚡] [Style Agent ✨] via LangGraph*

For each finding use this format:
**[AGENT_EMOJI] `filename:line`** — description
> 💡 _Recommendation: ..._
"""


def synthesizer_node(state: ReviewState) -> dict:
    """
    Merges all agent findings and generates the final markdown report.
    """
    # ── Combine all findings ───────────────────────────────
    all_findings: list[Finding] = (
        state.get("security_findings",    []) +
        state.get("performance_findings", []) +
        state.get("style_findings",       [])
    )

    # ── Deduplicate: remove findings about the same file+line ─
    seen = set()
    unique_findings = []
    for f in all_findings:
        key = (f.get("file", ""), f.get("line", -1), f.get("agent", ""))
        if key not in seen:
            seen.add(key)
            unique_findings.append(f)

    # ── Sort by severity ───────────────────────────────────
    sorted_findings = sorted(
        unique_findings,
        key=lambda x: SEVERITY_ORDER.get(x.get("severity", "low"), 4)
    )

    # ── Build severity summary ─────────────────────────────
    severity_summary = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in sorted_findings:
        sev = f.get("severity", "low")
        severity_summary[sev] = severity_summary.get(sev, 0) + 1

    total_issues = len(sorted_findings)

    # ── Agent emoji map ────────────────────────────────────
    agent_emoji = {
        "security":    "🛡️",
        "performance": "⚡",
        "style":       "✨"
    }
    for f in sorted_findings:
        f["agent_emoji"] = agent_emoji.get(f.get("agent", ""), "🔍")

    # ── Generate final markdown report ─────────────────────
    findings_json = json.dumps(sorted_findings, indent=2)
    pr_meta = state.get("pr_metadata", {})
    orchestrator = pr_meta.get("orchestrator", {})

    prompt_context = f"""
PR Title: {pr_meta.get('title', 'Unknown')}
PR Author: {pr_meta.get('author', 'Unknown')}
Change Type: {orchestrator.get('change_type', 'Unknown')}
PR Summary by Orchestrator: {orchestrator.get('summary', 'N/A')}

Severity Counts:
- Critical: {severity_summary['critical']}
- High: {severity_summary['high']}
- Medium: {severity_summary['medium']}
- Low: {severity_summary['low']}
Total: {total_issues}

All Findings (sorted by severity):
{findings_json}
"""

    try:
        response = llm.invoke([
            {"role": "system", "content": SYNTHESIZER_PROMPT},
            {"role": "user",   "content": prompt_context}
        ])
        final_report = response.content

    except Exception as e:
        # Fallback: build a basic report without LLM if synthesis fails
        final_report = _build_fallback_report(sorted_findings, severity_summary, total_issues)

    return {
        "final_report":    final_report,
        "severity_summary": severity_summary,
        "total_issues":    total_issues
    }


def _build_fallback_report(
    findings: list[Finding],
    severity_summary: dict,
    total: int
) -> str:
    """
    Builds a plain markdown report without LLM — used as fallback.
    """
    lines = [
        "## 🤖 AI Code Review\n",
        f"**{total} issue(s) found** — "
        f"{severity_summary['critical']} critical · "
        f"{severity_summary['high']} high · "
        f"{severity_summary['medium']} medium · "
        f"{severity_summary['low']} low\n",
        "---\n"
    ]
    for sev in ["critical", "high", "medium", "low"]:
        group = [f for f in findings if f.get("severity") == sev]
        if group:
            lines.append(f"### {sev.capitalize()} Issues\n")
            for f in group:
                lines.append(
                    f"**`{f.get('file','?')}:{f.get('line','?')}`** — {f.get('description','')}\n"
                    f"> 💡 _{f.get('recommendation','')}_\n"
                )
    return "\n".join(lines)


# ── IMPROVEMENT IDEAS ──────────────────────────────────────
# 1. Add deduplication across SIMILAR findings (not just exact):
#    use embeddings to cluster semantically similar findings
#    and pick the best-worded one from each cluster.
#
# 2. Add "auto-approve" logic: if total critical+high == 0,
#    programmatically approve the PR via GitHub API instead
#    of just posting a comment.
#
# 3. Add a "trends" section: compare this PR's findings against
#    the past 10 PRs (stored in SQLite) and call out repeat
#    issues: "SQL injection is a recurring issue in 3 of your last 5 PRs."
#
# 4. Add PR score: calculate a 0-100 quality score based on
#    severity-weighted finding count and include it in the comment.
#    Great for the Streamlit dashboard visualisation.
