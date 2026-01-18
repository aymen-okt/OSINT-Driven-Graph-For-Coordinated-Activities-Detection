import csv
import json
import os
import re
from collections import Counter, defaultdict

import networkx as nx

from utils_text import normalize_text_basic, sensational_score


COMMENTS_IN = "data/comments.jsonl"
GRAPH_UU = "data/graph_user_user.gexf"

OUT_COMMENTS = "data/comment_nlp_features.jsonl"
OUT_USERS = "data/user_nlp_features.csv"
OUT_COMM_TERMS = "data/community_top_terms.csv"

TOP_TERMS_PER_COMM = 20

WORD_RE = re.compile(r"[A-Za-z']+")

STOPWORDS = {
    "the","and","for","are","but","not","you","your","with","that","this","from","they","their","have","has","had",
    "was","were","will","would","can","could","should","a","an","to","of","in","on","at","by","as","it","its",
    "is","be","we","our","us","or","if","so","do","did","does","what","when","where","who","why","how","rt"
}

POS_WORDS = {
    "good","great","excellent","amazing","love","like","win","winning","success","best","strong","brave","support",
    "positive","happy","truth","trust","hope","peace","safe","secure","freedom","victory"
}

NEG_WORDS = {
    "bad","worst","terrible","hate","fraud","lies","liar","corrupt","weak","crime","crisis","danger","fake","scam",
    "hoax","fear","angry","sad","threat","rigged","disaster","fail","failure","loss"
}


def tokenize(text: str) -> list[str]:
    tokens = []
    for w in WORD_RE.findall(text.lower()):
        if len(w) < 3:
            continue
        if w in STOPWORDS:
            continue
        tokens.append(w)
    return tokens


def polarity_scores(tokens: list[str]) -> tuple[int, int, float]:
    pos = sum(1 for t in tokens if t in POS_WORDS)
    neg = sum(1 for t in tokens if t in NEG_WORDS)
    denom = max(1, len(tokens))
    polarity = (pos - neg) / denom
    return pos, neg, polarity


def load_community_map() -> dict[str, int]:
    if not os.path.exists(GRAPH_UU):
        return {}
    g = nx.read_gexf(GRAPH_UU)
    comm_map = {}
    for n, data in g.nodes(data=True):
        c = data.get("community")
        if c is not None:
            try:
                comm_map[str(n)] = int(c)
            except ValueError:
                continue
    return comm_map


def main() -> None:
    if not os.path.exists(COMMENTS_IN):
        raise FileNotFoundError(f"Missing input file: {COMMENTS_IN}")

    comm_map = load_community_map()
    comm_terms: dict[int, Counter] = defaultdict(Counter)

    user_stats = defaultdict(lambda: {
        "comments": 0,
        "tokens": 0,
        "pos": 0,
        "neg": 0,
        "polarity_sum": 0.0,
        "sens_sum": 0.0,
        "hashtags": 0,
        "mentions": 0,
        "urls": 0,
    })

    with open(COMMENTS_IN, "r", encoding="utf-8") as fin, \
            open(OUT_COMMENTS, "w", encoding="utf-8") as fout:
        for line in fin:
            r = json.loads(line)
            text = normalize_text_basic(r.get("text", "") or "")
            tokens = tokenize(text)
            pos, neg, pol = polarity_scores(tokens)
            sens = sensational_score(text)

            hashtags = r.get("hashtags", []) or []
            mentions = r.get("mentions", []) or []
            urls = r.get("urls", []) or []

            out = {
                "comment_id": r.get("comment_id"),
                "author_id": r.get("author_id"),
                "video_id": r.get("video_id"),
                "published_at": r.get("published_at"),
                "lang": r.get("lang") or "",
                "char_count": len(text),
                "token_count": len(tokens),
                "pos_count": pos,
                "neg_count": neg,
                "polarity": pol,
                "sensational_score": sens,
                "num_hashtags": len(hashtags),
                "num_mentions": len(mentions),
                "num_urls": len(urls),
            }
            fout.write(json.dumps(out, ensure_ascii=False) + "\n")

            u = r.get("author_id")
            if u:
                st = user_stats[u]
                st["comments"] += 1
                st["tokens"] += len(tokens)
                st["pos"] += pos
                st["neg"] += neg
                st["polarity_sum"] += pol
                st["sens_sum"] += sens
                st["hashtags"] += len(hashtags)
                st["mentions"] += len(mentions)
                st["urls"] += len(urls)

            if comm_map:
                comm_id = comm_map.get(str(r.get("author_id")))
                if comm_id is not None:
                    comm_terms[comm_id].update(tokens)

    with open(OUT_USERS, "w", encoding="utf-8", newline="") as fcsv:
        writer = csv.writer(fcsv)
        writer.writerow([
            "author_id",
            "comments",
            "avg_tokens",
            "pos_count",
            "neg_count",
            "avg_polarity",
            "avg_sensational",
            "hashtags",
            "mentions",
            "urls",
        ])
        for author_id, st in user_stats.items():
            c = max(1, st["comments"])
            writer.writerow([
                author_id,
                st["comments"],
                round(st["tokens"] / c, 4),
                st["pos"],
                st["neg"],
                round(st["polarity_sum"] / c, 6),
                round(st["sens_sum"] / c, 6),
                st["hashtags"],
                st["mentions"],
                st["urls"],
            ])

    if comm_terms:
        with open(OUT_COMM_TERMS, "w", encoding="utf-8", newline="") as fcsv:
            writer = csv.writer(fcsv)
            writer.writerow(["community", "term", "count"])
            for comm_id, counter in comm_terms.items():
                for term, count in counter.most_common(TOP_TERMS_PER_COMM):
                    writer.writerow([comm_id, term, count])

    print("Saved:", OUT_COMMENTS)
    print("Saved:", OUT_USERS)
    if comm_terms:
        print("Saved:", OUT_COMM_TERMS)


if __name__ == "__main__":
    main()
