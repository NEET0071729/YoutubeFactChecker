from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from state import State
from node import (
    add_query_to_state,
    rewrite_query,
    youtube_vector_search,
    extract_claims,
    search_facts,
    generate_final_answer,
)


def route_after_query(state: State) -> str:
    # "n" lets the user exit the conversation loop gracefully
    return END if state["query"].strip().lower() == "n" else "rewrite_query"


builder = StateGraph(State)

# Register each processing step as a named node
builder.add_node("add_query", add_query_to_state)
builder.add_node("rewrite_query", rewrite_query)
builder.add_node("youtube_search", youtube_vector_search)
builder.add_node("extract_claims", extract_claims)
builder.add_node("search_facts", search_facts)
builder.add_node("final_answer", generate_final_answer)

# Wire the pipeline: collect query → rewrite → search transcripts → extract claims → verify → answer → loop
builder.add_edge(START, "add_query")
builder.add_conditional_edges("add_query", route_after_query, {"rewrite_query": "rewrite_query", END: END})
builder.add_edge("rewrite_query", "youtube_search")
builder.add_edge("youtube_search", "extract_claims")
builder.add_edge("extract_claims", "search_facts")
builder.add_edge("search_facts", "final_answer")
builder.add_edge("final_answer", "add_query")  # loop back for the next question

# MemorySaver persists thread state in-process (sufficient for dev; swap for a DB checkpointer in prod)
graph = builder.compile(checkpointer=MemorySaver())
