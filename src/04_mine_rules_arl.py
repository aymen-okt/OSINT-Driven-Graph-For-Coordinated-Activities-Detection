import json
import pandas as pd
from collections import defaultdict
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import apriori, association_rules

COMMENTS_IN = "data/comments_filtered.jsonl"
VIDEOS_META = "data/videos.jsonl"

OUT_RULES = "data/arl_rules_fixed.csv"
OUT_FREQ  = "data/arl_frequent_itemsets_fixed.csv"

MIN_SUPPORT = 0.001
MIN_CONFIDENCE = 0.30
MIN_LIFT = 1.2
MAX_ITEMS_PER_TX = 80

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

    with open(COMMENTS_IN, "r", encoding="utf-8") as f:
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

    transactions = []
    for _, items in tx.items():
        items = list(items)
        if len(items) > MAX_ITEMS_PER_TX:
            items = items[:MAX_ITEMS_PER_TX]
        if len(items) >= 2:
            transactions.append(items)

    print("Total comments read:", total)
    print("Transactions (per user):", len(transactions))
    print("Comments with domains:", has_domains, f"({has_domains/total:.2%})")

    te = TransactionEncoder()
    te_ary = te.fit(transactions).transform(transactions)
    df = pd.DataFrame(te_ary, columns=te.columns_)

    freq = apriori(df, min_support=MIN_SUPPORT, use_colnames=True)
    if len(freq) == 0:
        print("No frequent itemsets. Lower MIN_SUPPORT.")
        return

    freq["itemset_len"] = freq["itemsets"].apply(lambda s: len(s))
    freq = freq.sort_values(["itemset_len", "support"], ascending=[False, False])
    freq.to_csv(OUT_FREQ, index=False)
    print("Frequent itemsets saved:", OUT_FREQ, "count:", len(freq))
    print("Max itemset length:", int(freq["itemset_len"].max()))

    # CRITICAL: rules must be computed from ALL itemsets (includes singletons)
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
