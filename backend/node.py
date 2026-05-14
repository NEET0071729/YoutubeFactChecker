import os
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt
from tavily import TavilyClient

from state import State

# Full model for complex reasoning steps; lite model for cheaper extraction tasks
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GOOGLE_API_KEY"))
llm_lite = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", google_api_key=os.getenv("GOOGLE_API_KEY"))

_tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


def _text(response) -> str:
    """Flatten a Gemini response (plain string or content-block list) to a single string."""
    content = response.content
    if isinstance(content, list):
        return "".join(
            block["text"] if isinstance(block, dict) and "text" in block else str(block)
            for block in content
        )
    return content

# Must use the same collection name and persist directory as ingest.py
_embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
)
_vectorstore = Chroma(
    collection_name="youtube_transcripts",
    embedding_function=_embeddings,
    persist_directory="./chroma_db",
)


def add_query_to_state(state: State) -> dict:
    """Pause graph execution and wait for the user's next question via HTTP."""
    user_input = interrupt("Enter your question (or 'n' to exit): ")
    return {"query": user_input}


def rewrite_query(state: State) -> dict:
    """Rewrite the raw query using chat history to produce a more precise search string."""
    query = state["query"]
    chat_history = state.get("chat_history", [])

    history_text = (
        "\n".join(f"{m.type}: {m.content}" for m in chat_history)
        if chat_history
        else "No previous conversation."
    )

    messages = [
        SystemMessage(
            content=(
                "Given the conversation history and the user's current question, "
                "rewrite the question to be more specific and searchable. "
                "Return ONLY the rewritten query, nothing else."
            )
        ),
        HumanMessage(
            content=f"Chat History:\n{history_text}\n\nCurrent Question: {query}"
        ),
    ]

    response = llm_lite.invoke(messages)
    rewritten = _text(response).strip()
    return {"rewritten_query": rewritten if rewritten else query}


def youtube_vector_search(state: State) -> dict:
    """Retrieve the top-5 transcript chunks and synthesise an answer from them."""
    rewritten_query = state["rewritten_query"]

    docs = _vectorstore.similarity_search(rewritten_query, k=5)
    context = "\n\n".join(doc.page_content for doc in docs)

    messages = [
        SystemMessage(
            content=(
                "You are an assistant that answers questions based on YouTube video transcripts. "
                "Use the provided transcript excerpts to answer the question accurately. "
                "If the information is not in the transcripts, say so clearly."
            )
        ),
        HumanMessage(
            content=f"Transcript excerpts:\n{context}\n\nQuestion: {rewritten_query}"
        ),
    ]

    response = llm.invoke(messages)
    return {"youtube_ans": _text(response)}


def extract_claims(state: State) -> dict:
    """Parse the YouTube answer into a list of individual verifiable factual claims."""
    youtube_ans = state["youtube_ans"]

    messages = [
        SystemMessage(
            content=(
                "Extract all factual claims from the given text. "
                "Return each claim as a separate line starting with '- '. "
                "Only include specific, verifiable factual statements."
            )
        ),
        HumanMessage(content=youtube_ans),
    ]

    response = llm_lite.invoke(messages)

    claims = [
        line.strip().lstrip("-").strip()
        for line in _text(response).strip().splitlines()
        if line.strip().startswith("- ")
    ]
    return {"claims": claims}


def search_facts(state: State) -> dict:
    """Web-search each claim via Tavily and collect supporting/contradicting sources."""
    claims = state["claims"]
    facts = []

    for claim in claims:
        try:
            response = _tavily.search(claim, max_results=3)
            results = response.get("results", [])
            sources = (
                "\n".join(f"- {r['url']}: {r.get('content', '')[:200]}" for r in results)
                if results else "No results found."
            )
        except Exception as e:
            print(f"Search failed for claim '{claim[:60]}...': {e}")
            sources = "Search failed."
        facts.append(f"Claim: {claim}\nSources:\n{sources}")

    return {"facts": facts}


def generate_final_answer(state: State) -> dict:
    """Combine the YouTube answer, extracted claims, and web evidence into a fact-checked response."""
    youtube_ans = state["youtube_ans"]
    claims = state["claims"]
    facts = state["facts"]

    claims_text = "\n".join(f"- {c}" for c in claims)
    facts_text = "\n\n".join(facts)

    messages = [
        SystemMessage(
            content=(
                "You are a fact-checking assistant. Given a YouTube-based answer, "
                "the claims extracted from it, and internet search results for those claims, "
                "provide a comprehensive final answer that:\n"
                "1. Summarizes what was learned from the YouTube content.\n"
                "2. Identifies which claims are supported or contradicted by internet sources.\n"
                "3. Gives an overall accuracy assessment of the YouTube content."
            )
        ),
        HumanMessage(
            content=(
                f"YouTube Answer:\n{youtube_ans}\n\n"
                f"Claims Made:\n{claims_text}\n\n"
                f"Fact-Check Results:\n{facts_text}\n\n"
                "Please provide a comprehensive fact-checked final answer."
            )
        ),
    ]

    response = llm.invoke(messages)
    return {"final_answer": _text(response)}
