# YouTube Fact Checker

An AI-powered application that ingests YouTube video transcripts and fact-checks their content against live web sources. Ask questions about any indexed video and get answers with automatic claim verification.

## How It Works

```
YouTube URL → Transcript Extraction → ChromaDB Vector Store
                                              ↓
User Question → Query Rewriting → Vector Search → Claim Extraction → Web Search → Verified Answer
```

The backend runs a multi-step [LangGraph](https://github.com/langchain-ai/langgraph) workflow:

1. **Rewrite Query** — Contextualizes the question using conversation history
2. **Vector Search** — Finds relevant transcript chunks from ChromaDB
3. **Extract Claims** — Gemini LLM pulls out specific factual claims from the retrieved content
4. **Search Facts** — Tavily searches the web to verify each claim (up to 3 sources per claim)
5. **Generate Answer** — Final response synthesizes YouTube content, claims, and web sources

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Google Gemini 2.5 Flash / Flash-Lite |
| Embeddings | Google Gemini Embedding Model |
| Vector DB | ChromaDB (persisted locally) |
| Web Search | Tavily API |
| Workflow | LangGraph |
| Backend | FastAPI + Uvicorn |
| Frontend | React 18 + TypeScript + Vite |
| Containers | Docker + Nginx |

## Prerequisites

- Python 3.12+
- Node.js 18+
- A [Google AI Studio](https://aistudio.google.com/) API key (for Gemini)
- A [Tavily](https://tavily.com/) API key (for web search)

## Setup

### 1. Environment Variables

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

```env
GOOGLE_API_KEY=your_google_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
```

### 2. Backend

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt

python backend/main.py
# Runs on http://localhost:8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
# Runs on http://localhost:3000
```

The Vite dev server proxies `/api/*` to `http://localhost:8000`.

## Docker

```bash
docker-compose up --build
```

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:80`

ChromaDB data is persisted in a named Docker volume so indexed videos survive restarts.

## Usage

### Ingest a Video

1. Paste a YouTube URL into the sidebar panel and click **Ingest**
2. The transcript is extracted, chunked, and stored in ChromaDB
3. Ingestion history (last 20 videos) is saved to localStorage

You can also ingest from the command line:

```bash
python backend/ingest.py "https://youtube.com/watch?v=VIDEO_ID"
```

### Ingesting on EC2 (YouTube IP blocks)

When the backend is deployed on EC2, YouTube often blocks transcript requests from datacenter IPs. Use `ingest_local.py` to fetch the transcript on your local machine and push it to the remote backend:

```bash
pip install youtube-transcript-api requests

python ingest_local.py "https://youtube.com/watch?v=VIDEO_ID"

# Custom backend host:
python ingest_local.py "https://youtube.com/watch?v=VIDEO_ID" --host http://<EC2_IP>:8000
```

This fetches the transcript locally (residential IP) and POSTs it to the `/ingest-text` endpoint on the server.

### Ask Questions

Type a question in the chat panel. The app supports multi-turn conversations — each thread maintains its own context. Start a new conversation with the **+** button.

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/ingest` | Ingest a YouTube video by URL |
| `POST` | `/ingest-text` | Ingest a pre-fetched transcript (used by `ingest_local.py`) |
| `POST` | `/chat` | Send a message and get a fact-checked answer |

**Ingest request:**
```json
{ "url": "https://youtube.com/watch?v=..." }
```

**Ingest-text request:**
```json
{ "video_id": "VIDEO_ID", "transcript": "full transcript text..." }
```

**Chat request:**
```json
{ "message": "Is this claim accurate?", "thread_id": "optional-uuid" }
```

**Chat response:**
```json
{ "thread_id": "uuid", "final_answer": "...", "status": "ended" }
```

## Project Structure

```
YoutubeFactChecker/
├── backend/
│   ├── main.py       # FastAPI app and endpoints
│   ├── graph.py      # LangGraph workflow definition
│   ├── state.py      # Workflow state schema
│   ├── node.py       # LLM workflow nodes
│   └── ingest.py     # Transcript ingestion pipeline
├── frontend/
│   └── src/
│       └── App.tsx   # Main React UI
├── ingest_local.py   # Local ingestion helper for EC2 deployments
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```
