# agents/security_agent.py
# ─────────────────────────────────────────────────────────
# Specialist agent focused exclusively on security issues.
# Runs in parallel with performance and style agents.
# ─────────────────────────────────────────────────────────

import json
from langchain_openai import ChatOpenAI
from graph.state import ReviewState, Finding

llm = ChatOpenAI(model="gpt-4o", temperature=0)

SECURITY_PROMPT = """You are a senior application security engineer doing a pull request review.
Your ONLY job is identifying security vulnerabilities. Do not comment on style or performance.

Scan the diff for:
- SQL injection, command injection, XSS, XXE vulnerabilities
- Hardcoded secrets, API keys, passwords, tokens
- Insecure deserialization or unsafe eval() usage
- Authentication or authorisation flaws (missing checks, broken logic)
- Sensitive data exposure (PII in logs, unencrypted storage)
- Known CVE patterns (e.g., outdated dependency usage)
- Path traversal, SSRF, CSRF vulnerabilities
- Cryptographic weaknesses (MD5, SHA1, hardcoded salts)

Return a JSON object:
{
  "findings": [
    {
      "severity": "critical | high | medium | low",
      "line": <line number as integer, -1 if unknown>,
      "file": "<filename>",
      "description": "<what the vulnerability is and why it matters>",
      "recommendation": "<concrete fix with example code if possible>",
      "agent": "security"
    }
  ]
}

If you find NO issues, return: {"findings": []}
Return ONLY valid JSON. No preamble, no markdown fences.
"""


def security_node(state: ReviewState) -> dict:
    """
    Runs security analysis on the PR diff.
    Returns security_findings list to be merged into shared state.
    """
    try:
        # Build context-aware prompt using orchestrator's summary
        orchestrator_ctx = state.get("pr_metadata", {}).get("orchestrator", {})
        context_note = ""
        if orchestrator_ctx.get("focus_areas"):
            context_note = f"\nPay special attention to: {', '.join(orchestrator_ctx['focus_areas'])}"

        response = llm.invoke([
            {"role": "system", "content": SECURITY_PROMPT},
            {"role": "user",   "content": (
                f"Review this PR diff for security issues.{context_note}\n\n"
                f"Diff:\n{state['pr_diff']}"
            )}
        ])

        data = json.loads(response.content)
        findings: list[Finding] = data.get("findings", [])

        # Ensure agent field is set on every finding
        for f in findings:
            f["agent"] = "security"

        return {"security_findings": findings}

    except Exception as e:
        return {
            "security_findings": [],
            "error": f"Security agent error: {str(e)}"
        }


# ── IMPROVEMENT IDEAS ──────────────────────────────────────
# 1. Add Bandit (Python) or ESLint security plugin output as
#    ADDITIONAL context alongside the LLM — hybrid static + AI.
#    Run subprocess, capture output, inject into the prompt.
#
# 2. Add a CVE lookup tool: if the diff changes a dependency version,
#    call the OSV.dev API to check for known vulnerabilities.
#    from langchain.tools import tool
#    @tool
#    def check_cve(package: str, version: str) -> str: ...
#
# 3. Add severity scoring calibration: post-process findings and
#    auto-downgrade "critical" to "high" if the project is internal-only.
#
# 4. Add a "false positive filter": run a second LLM call that
#    acts as a critic and removes low-confidence findings.
#    This improves precision significantly.
