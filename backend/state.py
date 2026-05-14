from typing import Annotated
from langgraph.graph import MessagesState
from langgraph.graph.message import add_messages


# Shared state passed between all graph nodes throughout a conversation thread.
class State(MessagesState):
    chat_history: Annotated[list, add_messages]  # accumulated message history for context
    query: str                  # raw user question from the interrupt
    rewritten_query: str        # LLM-rewritten query optimised for vector search
    youtube_ans: str            # answer synthesised from transcript excerpts
    claims: list[str]           # factual claims extracted from youtube_ans
    facts: list[str]            # web search results for each claim
    final_answer: str           # fact-checked final response shown to the user
