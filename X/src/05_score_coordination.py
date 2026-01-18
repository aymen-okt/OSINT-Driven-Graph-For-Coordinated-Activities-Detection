import json
import pandas as pd
from collections import defaultdict

COMMENTS_IN = "data/comments.jsonl"
VIDEOS_META = "data/videos.jsonl"
RULES_CSV = "data/arl_rules_fixed.csv"

OUT_USERS = "data/user_rule_hits.csv"

TOP_K_RULES = 200
MIN_LIFT = 1.1
MIN_CONF = 0.20

def load_video_to_channel():
    v2c = {}
    with open(VIDEOS_META, "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            vid = r.get("video_id")
            ch  = r.get("channel_id")
            if vid and ch:
                v2c[vid] = ch
    return v2c

def main():
    v2c = load_video_to_channel()

    user_items = defaultdict(set)
    with open(COMMENTS_IN, "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            u = r["author_id"]
            vid = r["video_id"]
            ch = v2c.get(vid)
            if ch:
                user_items[u].add(f"CH:{ch}")

            doms = r.get("domains", [])
            if doms:
                for d in doms:
                    if d:
                        user_items[u].add(f"DOM:{d.lower()}")

            tags = r.get("hashtags", [])
            if tags:
                for t in tags:
                    if t:
                        user_items[u].add(f"TAG:{t.lower()}")

            mentions = r.get("mentions", [])
            if mentions:
                for m in mentions:
                    if m:
                        user_items[u].add(f"MENT:{m.lower()}")

    rules = pd.read_csv(RULES_CSV)
    if len(rules) == 0:
        print("No rules found in", RULES_CSV)
        return
    rules = rules[(rules["lift"] >= MIN_LIFT) & (rules["confidence"] >= MIN_CONF)].copy()
    rules = rules.sort_values(["lift", "confidence", "support"], ascending=[False, False, False]).head(TOP_K_RULES)

    def to_set(s: str):
        if pd.isna(s) or not str(s).strip():
            return set()
        return set(x.strip() for x in str(s).split(",") if x.strip())

    rule_ants = [to_set(s) for s in rules["antecedents"].tolist()]

    rows = []
    for u, items in user_items.items():
        hits = 0
        for ant in rule_ants:
            if ant and ant.issubset(items):
                hits += 1
        rows.append({"author_id": u, "num_items": len(items), "rule_hits": hits})

    df = pd.DataFrame(rows).sort_values(["rule_hits","num_items"], ascending=[False, False])
    df.to_csv(OUT_USERS, index=False)
    print("Saved:", OUT_USERS)
    print(df.head(20).to_string(index=False))

if __name__ == "__main__":
    main()
