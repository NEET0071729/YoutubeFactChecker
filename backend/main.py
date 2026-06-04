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
from ingest import ingest as ingest_video, ingest_text as ingest_raw_text

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


class IngestTextRequest(BaseModel):
    video_id: str
    transcript: str


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
        from ingest import _extract_video_id
        video_id = _extract_video_id(req.url)
        return IngestResponse(video_id=video_id, chunks_ingested=count)
    except Exception as e:
        msg = str(e)
        if "ip" in msg.lower() or "blocked" in msg.lower() or "cloud" in msg.lower() or "transcript" in msg.lower():
            raise HTTPException(status_code=403, detail="YouTube is blocking transcript requests from this server's IP. This is a known restriction on cloud provider IPs (AWS, GCP, Azure).")
        raise HTTPException(status_code=400, detail=msg)


@app.post("/ingest-text", response_model=IngestResponse)
def ingest_text_endpoint(req: IngestTextRequest):
    try:
        count = ingest_raw_text(req.video_id, req.transcript)
        return IngestResponse(video_id=req.video_id, chunks_ingested=count)
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
