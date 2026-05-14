"""
Run this script locally (not on EC2) to ingest a YouTube video.
Your local machine has a residential IP so YouTube won't block the request.
The transcript is then POSTed to your EC2 backend for storage.

Usage:
    python ingest_local.py <youtube_url_or_video_id>

    # Custom EC2 host:
    python ingest_local.py <youtube_url_or_video_id> --host http://23.22.168.1:8000
"""

import re
import sys
import argparse
import requests
from youtube_transcript_api import YouTubeTranscriptApi

EC2_HOST = "http://23.22.168.1:8000"


def extract_video_id(url_or_id: str) -> str:
    for pattern in [r"(?:v=|\/)([0-9A-Za-z_-]{11})", r"^([0-9A-Za-z_-]{11})$"]:
        m = re.search(pattern, url_or_id)
        if m:
            return m.group(1)
    raise ValueError(f"Could not extract video ID from: {url_or_id}")


def fetch_transcript(video_id: str) -> str:
    api = YouTubeTranscriptApi()
    fetched = api.fetch(video_id)
    return " ".join(snippet.text for snippet in fetched)


def push_to_ec2(video_id: str, transcript: str, host: str) -> dict:
    resp = requests.post(
        f"{host}/ingest-text",
        json={"video_id": video_id, "transcript": transcript},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser(description="Ingest YouTube transcript via local machine")
    parser.add_argument("url", help="YouTube URL or video ID")
    parser.add_argument("--host", default=EC2_HOST, help="EC2 backend URL")
    args = parser.parse_args()

    video_id = extract_video_id(args.url)
    print(f"Fetching transcript for {video_id} ...")
    transcript = fetch_transcript(video_id)
    print(f"Fetched {len(transcript)} characters. Pushing to {args.host} ...")
    result = push_to_ec2(video_id, transcript, args.host)
    print(f"Done — {result['chunks_ingested']} chunks ingested for video {result['video_id']}")


if __name__ == "__main__":
    main()
