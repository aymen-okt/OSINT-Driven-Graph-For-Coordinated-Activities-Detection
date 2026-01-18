"""
01_search_videos.py
-------------------
Collect a reproducible list of YouTube video IDs for a topic (US elections) within a time window.

What it does:
- Loads YT_API_KEY from .env
- Runs multiple keyword queries (to increase coverage + diversity)
- Paginates search results (maxResults=50)
- De-duplicates video IDs across queries
- Fetches video metadata in batches (videos.list)
- Saves:
    - data/video_ids.json          (list of video IDs)
    - data/videos.jsonl            (one JSON object per video)
    - data/search_log.json         (queries + counts + timestamps)

Notes:
- search.list is quota-expensive, so keep (queries * pages) reasonable.
- videos.list is cheap and gives you channel_id, title, publish date, etc.
"""

import os
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# ----------------------------
# CONFIG (edit these)
# ----------------------------

# Time window (UTC, ISO-8601 with Z)
PUBLISHED_AFTER = "2024-10-20T00:00:00Z"
PUBLISHED_BEFORE = "2024-11-10T00:00:00Z"

# Multiple queries to reduce bias and increase coverage
QUERIES = [
    "US election 2024",
    "election day 2024",
    "presidential election 2024",
    "vote ballot",
    "mail-in ballot",
    "voter fraud claims",
    "swing states election",
    "election debate 2024",
    "voter registration",
    "election results 2024",
]

# Search paging:
# - Each page returns up to 50 videos.
# - Example: max_pages_per_query=3 => up to 150 results per query.
MAX_PAGES_PER_QUERY = 3

# Final cap on unique videos (recommended 200–300 for SNA + ARL)
FINAL_VIDEO_CAP = 250

# Optional: filter by region/language (leave as None if you want global results)
REGION_CODE = "US"  # e.g., "US"
RELEVANCE_LANGUAGE = "en"  # e.g., "en"

# Sleep between API calls to be nice (and reduce 429/rate issues)
SLEEP_BETWEEN_CALLS = 0.15

# Output paths
DATA_DIR = "data"
VIDEO_IDS_PATH = os.path.join(DATA_DIR, "video_ids.json")
VIDEOS_JSONL_PATH = os.path.join(DATA_DIR, "videos.jsonl")
SEARCH_LOG_PATH = os.path.join(DATA_DIR, "search_log.json")


# ----------------------------
# Helper functions
# ----------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def unique_keep_order(items: List[str]) -> List[str]:
    # De-duplicate while preserving order
    return list(dict.fromkeys(items))

def chunked(lst: List[str], n: int) -> List[List[str]]:
    return [lst[i:i+n] for i in range(0, len(lst), n)]

def append_jsonl(path: str, rows: List[dict]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ----------------------------
# YouTube API calls
# ----------------------------

def build_client():
    load_dotenv()
    api_key = os.getenv("YT_API_KEY")
    if not api_key:
        raise RuntimeError("Missing YT_API_KEY. Put it in a .env file: YT_API_KEY=YOUR_KEY")
    return build("youtube", "v3", developerKey=api_key)

def search_videos(
    youtube,
    query: str,
    published_after: str,
    published_before: str,
    max_pages: int,
    region_code: Optional[str] = None,
    relevance_language: Optional[str] = None,
) -> Tuple[List[str], Dict]:
    """
    Returns:
      - list of video IDs
      - stats dict for logging
    """
    video_ids: List[str] = []
    page_token: Optional[str] = None

    stats = {
        "query": query,
        "pages_requested": max_pages,
        "pages_fetched": 0,
        "items_returned": 0,
        "unique_videos_returned": 0,
        "published_after": published_after,
        "published_before": published_before,
        "timestamp_utc": utc_now_iso(),
    }

    for _ in range(max_pages):
        try:
            req = youtube.search().list(
                part="id",
                q=query,
                type="video",
                order="relevance",
                maxResults=50,
                publishedAfter=published_after,
                publishedBefore=published_before,
                pageToken=page_token,
                regionCode=region_code if region_code else None,
                relevanceLanguage=relevance_language if relevance_language else None,
            )
            res = req.execute()
        except HttpError as e:
            # Log and stop paging for this query
            stats["error"] = str(e)
            break

        items = res.get("items", [])
        stats["pages_fetched"] += 1
        stats["items_returned"] += len(items)

        for it in items:
            vid = it.get("id", {}).get("videoId")
            if vid:
                video_ids.append(vid)

        page_token = res.get("nextPageToken")
        time.sleep(SLEEP_BETWEEN_CALLS)

        if not page_token:
            break

    video_ids = unique_keep_order(video_ids)
    stats["unique_videos_returned"] = len(video_ids)
    return video_ids, stats

def fetch_video_metadata(youtube, video_ids: List[str]) -> List[dict]:
    """
    Fetch metadata for video IDs using videos.list (cheap).
    Returns a list of dicts (one per video).
    """
    results: List[dict] = []
    for chunk in chunked(video_ids, 50):  # max 50 IDs per call
        try:
            res = youtube.videos().list(
                part="snippet,statistics,contentDetails",
                id=",".join(chunk),
                maxResults=50
            ).execute()
        except HttpError as e:
            # Skip this chunk on error
            print("videos.list error:", e)
            time.sleep(1)
            continue

        for item in res.get("items", []):
            sn = item.get("snippet", {})
            stats = item.get("statistics", {})
            cd = item.get("contentDetails", {})
            results.append({
                "video_id": item.get("id"),
                "channel_id": sn.get("channelId"),
                "channel_title": sn.get("channelTitle"),
                "published_at": sn.get("publishedAt"),
                "title": sn.get("title"),
                "description": sn.get("description"),
                "tags": sn.get("tags", []),
                "category_id": sn.get("categoryId"),
                "default_language": sn.get("defaultLanguage"),
                "default_audio_language": sn.get("defaultAudioLanguage"),
                "view_count": stats.get("viewCount"),
                "like_count": stats.get("likeCount"),
                "comment_count": stats.get("commentCount"),
                "duration": cd.get("duration"),
            })

        time.sleep(SLEEP_BETWEEN_CALLS)

    return results


# ----------------------------
# Main
# ----------------------------

def main():
    ensure_dir(DATA_DIR)

    # Clear outputs for a fresh run (optional)
    # If you want to append, comment these out.
    if os.path.exists(VIDEOS_JSONL_PATH):
        os.remove(VIDEOS_JSONL_PATH)

    youtube = build_client()

    all_video_ids: List[str] = []
    search_logs: List[dict] = []

    print("=== Searching videos ===")
    for q in QUERIES:
        vids, log = search_videos(
            youtube=youtube,
            query=q,
            published_after=PUBLISHED_AFTER,
            published_before=PUBLISHED_BEFORE,
            max_pages=MAX_PAGES_PER_QUERY,
            region_code=REGION_CODE,
            relevance_language=RELEVANCE_LANGUAGE,
        )
        search_logs.append(log)
        all_video_ids.extend(vids)
        print(f"- Query: {q!r} -> {len(vids)} unique videos")

    # De-duplicate across all queries
    unique_ids = unique_keep_order(all_video_ids)
    print(f"Total unique videos before cap: {len(unique_ids)}")

    # Cap to a manageable size
    unique_ids = unique_ids[:FINAL_VIDEO_CAP]
    print(f"Total unique videos after cap:  {len(unique_ids)}")

    # Save video IDs
    with open(VIDEO_IDS_PATH, "w", encoding="utf-8") as f:
        json.dump(unique_ids, f, indent=2)

    # Fetch and save metadata
    print("=== Fetching video metadata ===")
    meta = fetch_video_metadata(youtube, unique_ids)
    append_jsonl(VIDEOS_JSONL_PATH, meta)
    print(f"Saved metadata for {len(meta)} videos to {VIDEOS_JSONL_PATH}")

    # Save logs
    log_obj = {
        "created_utc": utc_now_iso(),
        "published_after": PUBLISHED_AFTER,
        "published_before": PUBLISHED_BEFORE,
        "region_code": REGION_CODE,
        "relevance_language": RELEVANCE_LANGUAGE,
        "max_pages_per_query": MAX_PAGES_PER_QUERY,
        "final_video_cap": FINAL_VIDEO_CAP,
        "queries": QUERIES,
        "per_query_logs": search_logs,
        "total_unique_before_cap": len(unique_keep_order(all_video_ids)),
        "total_unique_after_cap": len(unique_ids),
    }
    with open(SEARCH_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log_obj, f, indent=2)

    print("=== Done ===")
    print(f"- Video IDs: {VIDEO_IDS_PATH}")
    print(f"- Video metadata: {VIDEOS_JSONL_PATH}")
    print(f"- Search logs: {SEARCH_LOG_PATH}")


if __name__ == "__main__":
    main()
