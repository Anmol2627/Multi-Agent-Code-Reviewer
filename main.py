# main.py
# ─────────────────────────────────────────────────────────
# CLI entry point for quick local testing of the agent graph
# without needing FastAPI, Celery, or Redis running.
# Usage: python main.py path/to/sample.diff
# ─────────────────────────────────────────────────────────

import sys
import json
from graph.builder import build_graph


SAMPLE_DIFF = '''diff --git a/app.py b/app.py
index 83db48f..bf269e4 100644
--- a/app.py
+++ b/app.py
@@ -10,6 +10,12 @@ from flask import Flask, request
 app = Flask(__name__)
+API_KEY = "sk-live-4f9a2b8c1d3e5f7a9b1c3d5e7f9a1b3c"
+
+def get_user(username):
+    query = "SELECT * FROM users WHERE username = '" + username + "'"
+    cursor.execute(query)
+    return cursor.fetchone()
+
+def process_items(items):
+    result = []
+    for item in items:
+        for other in items:
+            if item.id == other.related_id:
+                result.append(other)
+    return result
'''


def main():
    diff_path = sys.argv[1] if len(sys.argv) > 1 else None

    if diff_path:
        with open(diff_path, "r") as f:
            diff_content = f.read()
    else:
        print("No diff file provided — using built-in sample diff with intentional issues.\n")
        diff_content = SAMPLE_DIFF

    print("Building graph...")
    graph = build_graph()

    print("Running multi-agent review (this calls the LLM 5 times: "
          "orchestrator + 3 agents + synthesizer)...\n")

    result = graph.invoke({
        "pr_diff": diff_content,
        "pr_metadata": {"title": "Local test review", "author": "cli-user"},
    })

    print("=" * 60)
    print(result["final_report"])
    print("=" * 60)
    print(f"\nSeverity summary: {json.dumps(result['severity_summary'], indent=2)}")
    print(f"Total issues: {result['total_issues']}")


if __name__ == "__main__":
    main()


# ── IMPROVEMENT IDEAS ──────────────────────────────────────
# 1. Add argparse for flags: --output report.md, --json results.json
# 2. Add a --no-llm dry-run mode that validates the graph wiring
#    without spending API credits (mock LLM responses).
# 3. Turn this into a proper CLI tool with `click` for pip distribution
#    so people can `pip install your-code-reviewer` and run it on
#    any local git diff: `code-reviewer review --staged`
