from typing import Annotated
from langgraph.graph import MessagesState
from langgraph.graph.message import add_messages


class State(MessagesState):
    chat_history: Annotated[list, add_messages]
    query: str
    rewritten_query: str
    youtube_ans: str
    claims: list[str]
    facts: list[str]
    final_answer: str
