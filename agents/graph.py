from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agents.state import AgentState
from agents.nodes import fetch_data, detect_alerts, generate_briefings, human_review, should_generate

checkpointer = MemorySaver()


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("fetch_data", fetch_data)
    graph.add_node("detect_alerts", detect_alerts)
    graph.add_node("generate_briefings", generate_briefings)
    graph.add_node("human_review", human_review)

    graph.set_entry_point("fetch_data")

    graph.add_edge("fetch_data", "detect_alerts")
    graph.add_conditional_edges(
        "detect_alerts",
        should_generate,
        {"generate": "generate_briefings", "end": END},
    )
    graph.add_edge("generate_briefings", "human_review")
    graph.add_edge("human_review", END)

    return graph.compile(checkpointer=checkpointer, interrupt_before=["human_review"])


if __name__ == "__main__":
    from tools.player_store import load_players

    app = build_graph()
    players = [p.__dict__ for p in load_players()]

    config = {"configurable": {"thread_id": "run-1"}}

    print("Starting Football Agent...\n")
    print(f"Processing {len(players)} player(s): {', '.join(p['name'] for p in players)}\n")

    # Run until interrupt
    state = app.invoke({"players": players, "results": [], "pending_briefings": [], "human_approved": False}, config=config)

    # Show briefings and ask for approval
    print("\nBriefings ready. Type 'approve' to confirm or 'reject' to cancel: ", end="")
    answer = input().strip().lower()

    if answer == "approve":
        # Resume graph after human_review
        final = app.invoke(None, config=config)
        print("\nBriefings approved. Run complete.")
    else:
        print("\nRun cancelled by agent.")
