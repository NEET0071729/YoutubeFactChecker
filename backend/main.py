import uuid
import os
from dotenv import load_dotenv, find_dotenv

# Load .env before any module that reads env vars at import time (e.g. graph, ingest)
load_dotenv(find_dotenv())

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langgraph.types import Command
import uvicorn

from graph import graph
from ingest import ingest as ingest_video

app = FastAPI(title="YouTube Fact Checker API")

# Allow all origins in dev; tighten allow_origins for production deployments
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- request / response models ----------

class IngestRequest(BaseModel):
    url: str


class IngestResponse(BaseModel):
    video_id: str
    chunks_ingested: int


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None  # omit to start a new conversation thread


class ChatResponse(BaseModel):
    thread_id: str
    final_answer: str | None
    status: str  # "waiting" = graph paused at interrupt | "ended" = user typed "n"


# ---------- helpers ----------

def _config(thread_id: str) -> dict:
    """Build the LangGraph config dict for a given thread."""
    return {"configurable": {"thread_id": thread_id}}


def _is_new_thread(thread_id: str) -> bool:
    """Return True if no checkpointed state exists for this thread yet."""
    state = graph.get_state(_config(thread_id))
    return not state.values


# ---------- routes ----------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse)
def ingest_endpoint(req: IngestRequest):
    try:
        count = ingest_video(req.url)
        # Re-use the private helper to parse the video ID for the response
        from ingest import _extract_video_id
        video_id = _extract_video_id(req.url)
        return IngestResponse(video_id=video_id, chunks_ingested=count)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    thread_id = req.thread_id or str(uuid.uuid4())
    config = _config(thread_id)

    try:
        if _is_new_thread(thread_id):
            # Prime the graph so it advances to the first interrupt before we resume
            graph.invoke({"messages": []}, config)

        result = graph.invoke(Command(resume=req.message), config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    final_state = graph.get_state(config)
    is_ended = len(final_state.next) == 0  # no pending nodes means the graph reached END

    return ChatResponse(
        thread_id=thread_id,
        final_answer=result.get("final_answer"),
        status="ended" if is_ended else "waiting",
    )


# ---------- entry point ----------

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
