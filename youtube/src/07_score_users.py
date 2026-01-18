import json
import pandas as pd
from collections import defaultdict

COMMENTS_IN = "data/comments_filtered.jsonl"
VIDEOS_META = "data/videos.jsonl"
RULES_CSV = "data/arl_rules_fixed.csv"

OUT_USERS = "data/user_rule_hits.csv"

# Use only strongest rules to avoid noise
TOP_K_RULES = 100
MIN_LIFT = 50   # your lifts are huge; 50 is safe
MIN_CONF = 0.8  # keep high-confidence rules

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

    # user -> set(CH:...)
    user_items = defaultdict(set)
    with open(COMMENTS_IN, "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            u = r["author_id"]
            vid = r["video_id"]
            ch = v2c.get(vid)
            if ch:
                user_items[u].add(f"CH:{ch}")

    # Load rules
    rules = pd.read_csv(RULES_CSV)

    # Filter strong rules and take top K by lift
    rules = rules[(rules["lift"] >= MIN_LIFT) & (rules["confidence"] >= MIN_CONF)].copy()
    rules = rules.sort_values(["lift", "confidence", "support"], ascending=[False, False, False]).head(TOP_K_RULES)

    # Parse antecedents/consequents into sets
    def to_set(s: str):
        if pd.isna(s) or not str(s).strip():
            return set()
        return set(x.strip() for x in str(s).split(",") if x.strip())

    rule_ants = [to_set(s) for s in rules["antecedents"].tolist()]
    rule_cons = [to_set(s) for s in rules["consequents"].tolist()]

    rows = []
    for u, items in user_items.items():
        hits = 0
        for ant, con in zip(rule_ants, rule_cons):
            if ant and ant.issubset(items):
                hits += 1
        rows.append({
            "author_id": u,
            "num_channels": len(items),
            "rule_hits": hits
        })

    df = pd.DataFrame(rows).sort_values(["rule_hits","num_channels"], ascending=[False, False])
    df.to_csv(OUT_USERS, index=False)
    print("Saved:", OUT_USERS)
    print(df.head(20).to_string(index=False))

if __name__ == "__main__":
    main()
