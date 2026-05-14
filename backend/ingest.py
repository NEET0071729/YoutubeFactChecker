import os
import re
from langchain_community.document_loaders import YoutubeLoader
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter


# Shared embedding model used to vectorise transcript chunks
_embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
)

# Persistent Chroma collection — same collection name as node.py so searches hit ingested content
_vectorstore = Chroma(
    collection_name="youtube_transcripts",
    embedding_function=_embeddings,
    persist_directory="./chroma_db",
)

# 200-token overlap prevents context loss at chunk boundaries
_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
)


def _extract_video_id(url_or_id: str) -> str:
    """Return the 11-char YouTube video ID from a full URL or a bare ID."""
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11})",
        r"^([0-9A-Za-z_-]{11})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract video ID from: {url_or_id}")


def ingest(url_or_id: str) -> int:
    """Load a YouTube transcript, split it into chunks, and store them in Chroma."""
    video_id = _extract_video_id(url_or_id)

    loader = YoutubeLoader.from_youtube_url(
        f"https://www.youtube.com/watch?v={video_id}",
        add_video_info=False,
    )
    docs = loader.load()
    chunks = _splitter.split_documents(docs)

    _vectorstore.add_documents(chunks)
    print(f"Ingested {len(chunks)} chunks from video {video_id}")
    return len(chunks)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python ingest.py <youtube_url_or_video_id>")
        sys.exit(1)

    ingest(sys.argv[1])
