# graph/builder.py
# ─────────────────────────────────────────────────────────
# Wires all agent nodes into a LangGraph StateGraph.
# Key pattern: orchestrator → (security, performance, style)
# in PARALLEL → synthesizer → END
# ─────────────────────────────────────────────────────────

from langgraph.graph import StateGraph, END, START
from graph.state import ReviewState
from agents.orchestrator import orchestrator_node
from agents.security_agent import security_node
from agents.performance_agent import performance_node
from agents.style_agent import style_node
from agents.synthesizer import synthesizer_node


def build_graph() -> StateGraph:
    graph = StateGraph(ReviewState)

    # ── Register nodes ─────────────────────────────────────
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("security",     security_node)
    graph.add_node("performance",  performance_node)
    graph.add_node("style",        style_node)
    graph.add_node("synthesizer",  synthesizer_node)

    # ── Entry point ────────────────────────────────────────
    graph.add_edge(START, "orchestrator")

    # ── Fan-out: orchestrator → all three agents in parallel ─
    # LangGraph executes these concurrently when possible
    graph.add_edge("orchestrator", "security")
    graph.add_edge("orchestrator", "performance")
    graph.add_edge("orchestrator", "style")

    # ── Fan-in: all three agents → synthesizer ─────────────
    graph.add_edge("security",    "synthesizer")
    graph.add_edge("performance", "synthesizer")
    graph.add_edge("style",       "synthesizer")

    # ── Terminal edge ──────────────────────────────────────
    graph.add_edge("synthesizer", END)

    return graph.compile()


# ── IMPROVEMENT IDEAS ──────────────────────────────────────
# 1. Add a "human_review" node between synthesizer and END.
#    Use graph.add_conditional_edges() to route there only
#    when critical findings exist — requires human approval
#    before posting. Use LangGraph's interrupt_before param.
#
# 2. Add a "language_router" conditional edge after orchestrator:
#    graph.add_conditional_edges("orchestrator", route_by_language,
#        {"python": "security", "javascript": "security", ...})
#    Each language gets slightly different agent prompts.
#
# 3. Add a "retry" node that re-runs failed agents:
#    graph.add_conditional_edges("security", check_for_error,
#        {"error": "security", "ok": "synthesizer"})
#
# 4. Add checkpointing for long-running reviews:
#    from langgraph.checkpoint.sqlite import SqliteSaver
#    memory = SqliteSaver.from_conn_string("reviews.db")
#    return graph.compile(checkpointer=memory)
