# src/02_fetch_comments.py
import os, json, time, re, hashlib
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()
API_KEY = os.getenv("YT_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing YT_API_KEY in .env")

youtube = build("youtube", "v3", developerKey=API_KEY)

DATA_DIR = "data"
VIDEO_IDS_PATH = os.path.join(DATA_DIR, "video_ids.json")
OUT_COMMENTS = os.path.join(DATA_DIR, "comments.jsonl")
PROGRESS_PATH = os.path.join(DATA_DIR, "comments_progress.json")
ERRORS_PATH = os.path.join(DATA_DIR, "errors.jsonl")

MAX_PAGES_PER_VIDEO = 5     # 5 pages = up to 500 top-level comments
SLEEP_BETWEEN_CALLS = 0.25  # be gentle

URL_RE = re.compile(r"https?://\S+")
HASHTAG_RE = re.compile(r"#\w+")

def hash_id(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

def extract(text: str):
    urls = URL_RE.findall(text)
    hashtags = HASHTAG_RE.findall(text)
    domains = []
    for u in urls:
        d = re.sub(r"^https?://", "", u).split("/")[0].lower()
        domains.append(d)
    return urls, domains, hashtags

def append_jsonl(path, rows):
    with open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def load_progress():
    if not os.path.exists(PROGRESS_PATH):
        return {"done_videos": []}
    with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_progress(progress):
    with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)

def fetch_comments(video_id: str, max_pages=5):
    rows = []
    token = None
    pages = 0

    while pages < max_pages:
        res = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=100,
            pageToken=token,
            textFormat="plainText"
        ).execute()

        for item in res.get("items", []):
            top = item["snippet"]["topLevelComment"]["snippet"]
            author = top.get("authorChannelId", {}).get("value", "unknown")
            text = top.get("textDisplay", "")

            urls, domains, hashtags = extract(text)

            rows.append({
                "video_id": video_id,
                "comment_id": item["snippet"]["topLevelComment"]["id"],
                "author_id": hash_id(author),     # privacy-friendly
                "published_at": top.get("publishedAt"),
                "like_count": top.get("likeCount", 0),
                "reply_count": item["snippet"].get("totalReplyCount", 0),
                "text": text,
                "urls": urls,
                "domains": domains,
                "hashtags": hashtags
            })

        token = res.get("nextPageToken")
        pages += 1
        if not token:
            break
        time.sleep(SLEEP_BETWEEN_CALLS)

    return rows

def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    with open(VIDEO_IDS_PATH, "r", encoding="utf-8") as f:
        video_ids = json.load(f)

    progress = load_progress()
    done = set(progress.get("done_videos", []))

    total = len(video_ids)
    processed = 0

    for i, vid in enumerate(video_ids, 1):
        if vid in done:
            continue

        try:
            rows = fetch_comments(vid, max_pages=MAX_PAGES_PER_VIDEO)
            append_jsonl(OUT_COMMENTS, rows)

            done.add(vid)
            progress["done_videos"] = sorted(done)
            save_progress(progress)

            processed += 1
            print(f"[{i}/{total}] {vid} -> {len(rows)} comments (processed {processed})")

        except HttpError as e:
            err = {"video_id": vid, "error": str(e)}
            append_jsonl(ERRORS_PATH, [err])
            print(f"[{i}/{total}] {vid} -> ERROR: {e}")
            time.sleep(1)

    print("Done. Comments saved to:", OUT_COMMENTS)

if __name__ == "__main__":
    main()
