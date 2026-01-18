import json
import os
import pandas as pd
from collections import defaultdict
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import association_rules, fpgrowth

COMMENTS_IN = "data/comments.jsonl"
COMMENTS_FALLBACK = "data/comments_filtered.jsonl"
VIDEOS_META = "data/videos.jsonl"

OUT_RULES = "data/arl_rules_fixed.csv"
OUT_FREQ  = "data/arl_frequent_itemsets_fixed.csv"

MIN_SUPPORT = 0.0005
MIN_CONFIDENCE = 0.20
MIN_LIFT = 1.1
MAX_ITEMS_PER_TX = 80
MAX_ITEMS_GLOBAL = 3000

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
    tx = defaultdict(set)

    total = 0
    has_domains = 0

    in_path = COMMENTS_IN if os.path.exists(COMMENTS_IN) else COMMENTS_FALLBACK
    if not os.path.exists(in_path):
        raise FileNotFoundError(f"Missing input file: {COMMENTS_IN} (fallback: {COMMENTS_FALLBACK})")

    with open(in_path, "r", encoding="utf-8") as f:
        for line in f:
            total += 1
            r = json.loads(line)
            u = r["author_id"]
            vid = r["video_id"]

            ch = v2c.get(vid)
            if ch:
                tx[u].add(f"CH:{ch}")

            doms = r.get("domains", [])
            if doms:
                has_domains += 1
                for d in doms:
                    if d:
                        tx[u].add(f"DOM:{d.lower()}")

            tags = r.get("hashtags", [])
            if tags:
                for t in tags:
                    if t:
                        tx[u].add(f"TAG:{t.lower()}")

            mentions = r.get("mentions", [])
            if mentions:
                for m in mentions:
                    if m:
                        tx[u].add(f"MENT:{m.lower()}")

    item_counts = defaultdict(int)
    for items in tx.values():
        for it in items:
            item_counts[it] += 1

    n_users = len(tx)
    min_count = max(1, int(MIN_SUPPORT * n_users))
    keep_items = {it for it, c in item_counts.items() if c >= min_count}

    if MAX_ITEMS_GLOBAL and len(keep_items) > MAX_ITEMS_GLOBAL:
        top_items = sorted(keep_items, key=lambda x: item_counts.get(x, 0), reverse=True)
        keep_items = set(top_items[:MAX_ITEMS_GLOBAL])

    transactions = []
    for _, items in tx.items():
        items = [it for it in items if it in keep_items]
        if len(items) > MAX_ITEMS_PER_TX:
            items = items[:MAX_ITEMS_PER_TX]
        if len(items) >= 2:
            transactions.append(items)

    print("Total comments read:", total)
    print("Transactions (per user):", len(transactions))
    print("Comments with domains:", has_domains, f"({has_domains/total:.2%})")

    print("Unique items:", len(item_counts))
    print("Kept items:", len(keep_items), "Min count:", min_count)

    te = TransactionEncoder()
    te_ary = te.fit(transactions).transform(transactions, sparse=True)
    df = pd.DataFrame.sparse.from_spmatrix(te_ary, columns=te.columns_)

    freq = fpgrowth(df, min_support=MIN_SUPPORT, use_colnames=True)
    if len(freq) == 0:
        print("No frequent itemsets. Lower MIN_SUPPORT.")
        return

    freq["itemset_len"] = freq["itemsets"].apply(lambda s: len(s))
    freq = freq.sort_values(["itemset_len", "support"], ascending=[False, False])
    freq.to_csv(OUT_FREQ, index=False)
    print("Frequent itemsets saved:", OUT_FREQ, "count:", len(freq))
    print("Max itemset length:", int(freq["itemset_len"].max()))

    rules = association_rules(freq, metric="confidence", min_threshold=MIN_CONFIDENCE)
    if len(rules) == 0:
        print("No rules. Lower MIN_CONFIDENCE or MIN_SUPPORT.")
        return

    rules = rules[rules["lift"] >= MIN_LIFT].copy()
    rules = rules.sort_values(["lift", "confidence", "support"], ascending=[False, False, False])

    rules["antecedents"] = rules["antecedents"].apply(lambda s: ", ".join(sorted(list(s))))
    rules["consequents"] = rules["consequents"].apply(lambda s: ", ".join(sorted(list(s))))

    rules.to_csv(OUT_RULES, index=False)
    print("Rules saved:", OUT_RULES, "count:", len(rules))
    print("\nTop 10 rules:")
    print(rules[["antecedents","consequents","support","confidence","lift"]].head(10).to_string(index=False))

if __name__ == "__main__":
    main()
