import json
from datetime import datetime, timezone

IN_PATH = "data/comments.jsonl"
OUT_PATH = "data/comments_filtered.jsonl"

START = "2024-10-20T00:00:00Z"
END   = "2024-11-10T00:00:00Z"

def parse_yt(ts: str) -> datetime:
    # "2025-12-04T16:52:09Z"
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

start_dt = parse_yt(START)
end_dt = parse_yt(END)

kept = 0
total = 0

with open(IN_PATH, "r", encoding="utf-8") as fin, open(OUT_PATH, "w", encoding="utf-8") as fout:
    for line in fin:
        total += 1
        row = json.loads(line)
        ts = row.get("published_at")
        if not ts:
            continue
        dt = parse_yt(ts)
        if start_dt <= dt <= end_dt:
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
            kept += 1

print(f"Total comments: {total}")
print(f"Kept in window [{START} .. {END}]: {kept}")
print(f"Saved: {OUT_PATH}")
