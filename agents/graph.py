from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agents.state import AgentState
from agents.nodes import (
    fetch_data, detect_signals, detect_alerts, generate_briefings,
    critique_briefings,
    should_generate, should_retry,
)

checkpointer = MemorySaver()


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("fetch_data", fetch_data)
    graph.add_node("detect_signals", detect_signals)
    graph.add_node("detect_alerts", detect_alerts)
    graph.add_node("generate_briefings", generate_briefings)
    graph.add_node("critique_briefings", critique_briefings)

    graph.set_entry_point("fetch_data")

    graph.add_edge("fetch_data", "detect_signals")
    graph.add_edge("detect_signals", "detect_alerts")
    graph.add_conditional_edges(
        "detect_alerts",
        should_generate,
        {"generate": "generate_briefings", "end": END},
    )
    graph.add_edge("generate_briefings", "critique_briefings")
    graph.add_conditional_edges(
        "critique_briefings",
        should_retry,
        {"generate_briefings": "generate_briefings", "end": END},
    )

    return graph.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    from tools.player_store import load_players

    app = build_graph()
    players = [p.__dict__ for p in load_players()]

    config = {"configurable": {"thread_id": "run-1"}}

    print("Starting Football Agent...\n")
    print(f"Processing {len(players)} player(s): {', '.join(p['name'] for p in players)}\n")

    state = app.invoke(
        {"players": players, "results": [], "pending_briefings": [], "briefing_attempts": 0},
        config=config,
    )
    print("\nRun complete. Briefings ready for review.")
