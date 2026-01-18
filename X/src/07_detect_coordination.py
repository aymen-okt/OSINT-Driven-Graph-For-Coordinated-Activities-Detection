import csv
import glob
import json
import os
import shutil
import sqlite3
import heapq
from collections import Counter, defaultdict
from datetime import datetime, timezone

import networkx as nx


COMMENTS_IN = "data/comments.jsonl"
OUT_EDGES = "data/coordination_edges.csv"
OUT_CLUSTERS = "data/coordination_clusters.csv"
OUT_GRAPH = "data/coordination_graph.gexf"
OUT_BIP = "data/x_user_item.gexf"
OUT_TOP_CLUSTERS = "data/x_top_clusters.csv"
OUT_TOP_EDGES = "data/x_top_edges.csv"
OUT_TIME_WINDOWS = "data/x_time_windows.csv"
TMP_DIR = "data/tmp_coordination"

WINDOW_SECS = 3600
MIN_OCC = 2
MIN_ITEM_FREQ = 5
MAX_USERS_PER_ITEM = 200
MAX_EDGES_FOR_GRAPH = 2_000_000
MAX_BIP_EDGES = 3_000_000
CLEANUP_TMP = False


def parse_ts(ts: str) -> int | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return int(dt.replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        return None


def add_items(items: list[tuple[str, str]], signal: str, values: list[str]) -> None:
    for v in values:
        if v:
            items.append((signal, v))


def extract_items(r: dict) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    add_items(items, "A_URL", r.get("urls", []))
    add_items(items, "A_DOM", r.get("domains", []))
    add_items(items, "B_TAG", r.get("hashtags", []))
    add_items(items, "C_MENT", r.get("mentions", []))

    rt_id = r.get("retweeted_tweet_id")
    if rt_id:
        items.append(("D_RETWEET", rt_id))
    qt_id = r.get("quoted_tweet_id")
    if qt_id:
        items.append(("D_QUOTE", qt_id))

    conv_id = r.get("conversation_id") or r.get("video_id")
    if conv_id:
        items.append(("E_CONV", conv_id))

    reply_id = r.get("in_reply_to_status_id_str")
    if reply_id:
        items.append(("E_REPLY", reply_id))

    return items


def to_bip_item(signal: str, value: str) -> str | None:
    if not value:
        return None
    if signal == "A_DOM":
        return f"DOM:{value}"
    if signal == "D_RETWEET":
        return f"RT:{value}"
    if signal == "E_CONV":
        return f"CONV:{value}"
    if signal == "C_MENT":
        return f"MENT:@{value}"
    if signal == "B_TAG":
        return f"TAG:#{value}"
    return None


def main() -> None:
    if not os.path.exists(COMMENTS_IN):
        raise FileNotFoundError(f"Missing input file: {COMMENTS_IN}")

    item_counts: Counter = Counter()

    # Pass 1: count items globally (for frequency filter).
    with open(COMMENTS_IN, "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            ts = parse_ts(r.get("published_at"))
            if ts is None:
                continue
            for key in extract_items(r):
                item_counts[key] += 1

    kept_items = {k for k, c in item_counts.items() if c >= MIN_ITEM_FREQ}
    print("Total items:", len(item_counts), "Kept items:", len(kept_items))

    # Pass 2: bucketize kept items to disk to reduce RAM usage.
    if os.path.exists(TMP_DIR):
        shutil.rmtree(TMP_DIR)
    os.makedirs(TMP_DIR, exist_ok=True)

    with open(COMMENTS_IN, "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            ts = parse_ts(r.get("published_at"))
            if ts is None:
                continue
            user = r.get("author_id")
            if not user:
                continue
            bucket = ts // WINDOW_SECS
            items = extract_items(r)
            if not items:
                continue
            path = os.path.join(TMP_DIR, f"bucket_{bucket}.tsv")
            with open(path, "a", encoding="utf-8") as fb:
                for signal, value in items:
                    key = (signal, value)
                    if key in kept_items:
                        fb.write(f"{signal}\t{value}\t{user}\n")

    db_path = os.path.join(TMP_DIR, "coordination.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE pair_signal (
            user_a TEXT NOT NULL,
            user_b TEXT NOT NULL,
            signal TEXT NOT NULL,
            cnt INTEGER NOT NULL,
            PRIMARY KEY (user_a, user_b, signal)
        )
    """)
    cur.execute("""
        CREATE TABLE user_item (
            user_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            cnt INTEGER NOT NULL,
            PRIMARY KEY (user_id, item_id)
        )
    """)
    conn.commit()

    # Pass 3a: per-bucket aggregation to pairs (persisted to SQLite).
    bucket_stats = {}
    for path in glob.glob(os.path.join(TMP_DIR, "bucket_*.tsv")):
        item_users: dict[tuple[str, str], set[str]] = defaultdict(set)
        bucket_users: set[str] = set()
        with open(path, "r", encoding="utf-8") as fb:
            for line in fb:
                signal, value, user = line.strip().split("\t")
                item_users[(signal, value)].add(user)
                bucket_users.add(user)

        bucket_counts: dict[tuple[str, str, str], int] = defaultdict(int)
        top_item = None
        top_item_users = 0
        top_signal = None
        top_signal_users = 0
        for (signal, value), users in item_users.items():
            ucount = len(users)
            if ucount > top_item_users:
                top_item_users = ucount
                top_item = f"{signal}:{value}"
            if ucount > top_signal_users:
                top_signal_users = ucount
                top_signal = signal
        for (signal, _value), users in item_users.items():
            if len(users) < 2:
                continue
            if len(users) > MAX_USERS_PER_ITEM:
                continue
            users = sorted(users)
            n = len(users)
            for i in range(n):
                for j in range(i + 1, n):
                    a, b = users[i], users[j]
                    bucket_counts[(a, b, signal)] += 1

        if bucket_counts:
            cur.executemany(
                "INSERT INTO pair_signal(user_a, user_b, signal, cnt) VALUES (?,?,?,?) "
                "ON CONFLICT(user_a, user_b, signal) DO UPDATE SET cnt = cnt + excluded.cnt",
                [(a, b, s, c) for (a, b, s), c in bucket_counts.items()],
            )
            conn.commit()

        bucket_name = os.path.basename(path)
        try:
            bucket_id = int(bucket_name.split("_")[1].split(".")[0])
        except (IndexError, ValueError):
            bucket_id = None
        if bucket_id is not None:
            num_edges_created = 0
            for (signal, _value), users in item_users.items():
                if len(users) >= 2 and len(users) <= MAX_USERS_PER_ITEM:
                    n = len(users)
                    num_edges_created += (n * (n - 1)) // 2
            bucket_stats[bucket_id] = {
                "active_users": len(bucket_users),
                "num_coord_edges_created": num_edges_created,
                "top_signal": top_signal or "",
                "top_item": top_item or "",
            }

    # Pass 3b: user-item bipartite counts (streamed from comments).
    batch = []
    batch_size = 5000
    with open(COMMENTS_IN, "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            ts = parse_ts(r.get("published_at"))
            if ts is None:
                continue
            user = r.get("author_id")
            if not user:
                continue
            for signal, value in extract_items(r):
                key = (signal, value)
                if key not in kept_items:
                    continue
                item_id = to_bip_item(signal, value)
                if not item_id:
                    continue
                batch.append((user, item_id, 1))
                if len(batch) >= batch_size:
                    cur.executemany(
                        "INSERT INTO user_item(user_id, item_id, cnt) VALUES (?,?,?) "
                        "ON CONFLICT(user_id, item_id) DO UPDATE SET cnt = cnt + excluded.cnt",
                        batch,
                    )
                    conn.commit()
                    batch.clear()
    if batch:
        cur.executemany(
            "INSERT INTO user_item(user_id, item_id, cnt) VALUES (?,?,?) "
            "ON CONFLICT(user_id, item_id) DO UPDATE SET cnt = cnt + excluded.cnt",
            batch,
        )
        conn.commit()

    # Pass 4: stream pairs from SQLite and write outputs.
    G = nx.Graph()
    edges_written = 0

    top_edges = []
    edge_seq = 0

    with open(OUT_EDGES, "w", encoding="utf-8", newline="") as fcsv:
        writer = csv.DictWriter(fcsv, fieldnames=[
            "user_a", "user_b", "num_signals", "total_occurrences", "signals", "signal_counts"
        ])
        writer.writeheader()

        cur.execute("SELECT user_a, user_b, signal, cnt FROM pair_signal ORDER BY user_a, user_b")
        current = None
        sig_counts: dict[str, int] = {}
        total_occ = 0

        for user_a, user_b, signal, cnt in cur:
            key = (user_a, user_b)
            if current is None:
                current = key
            if key != current:
                signals_met = [s for s, c in sig_counts.items() if c >= MIN_OCC]
                if len(signals_met) >= 2:
                    row = {
                        "user_a": current[0],
                        "user_b": current[1],
                        "num_signals": len(signals_met),
                        "total_occurrences": total_occ,
                        "signals": ",".join(sorted(signals_met)),
                        "signal_counts": json.dumps(sig_counts, ensure_ascii=False),
                    }
                    writer.writerow(row)
                    edges_written += 1
                    score = int(total_occ)
                    edge_seq += 1
                    entry = (score, edge_seq, row)
                    if len(top_edges) < 50:
                        heapq.heappush(top_edges, entry)
                    else:
                        heapq.heappushpop(top_edges, entry)
                    if edges_written <= MAX_EDGES_FOR_GRAPH:
                        G.add_edge(current[0], current[1], weight=int(total_occ), signals=",".join(sorted(signals_met)))

                current = key
                sig_counts = {}
                total_occ = 0

            sig_counts[signal] = sig_counts.get(signal, 0) + cnt
            total_occ += cnt

        if current is not None:
            signals_met = [s for s, c in sig_counts.items() if c >= MIN_OCC]
            if len(signals_met) >= 2:
                row = {
                    "user_a": current[0],
                    "user_b": current[1],
                    "num_signals": len(signals_met),
                    "total_occurrences": total_occ,
                    "signals": ",".join(sorted(signals_met)),
                    "signal_counts": json.dumps(sig_counts, ensure_ascii=False),
                }
                writer.writerow(row)
                edges_written += 1
                score = int(total_occ)
                edge_seq += 1
                entry = (score, edge_seq, row)
                if len(top_edges) < 50:
                    heapq.heappush(top_edges, entry)
                else:
                    heapq.heappushpop(top_edges, entry)
                if edges_written <= MAX_EDGES_FOR_GRAPH:
                    G.add_edge(current[0], current[1], weight=int(total_occ), signals=",".join(sorted(signals_met)))

    clusters = []
    if G.number_of_nodes() > 0 and edges_written <= MAX_EDGES_FOR_GRAPH:
        for idx, comp in enumerate(nx.connected_components(G)):
            comp = list(comp)
            sig_counter = Counter()
            for u in comp:
                for v in G.neighbors(u):
                    sigs = G.edges[u, v].get("signals", "")
                    for s in sigs.split(","):
                        if s:
                            sig_counter[s] += 1
            clusters.append({
                "cluster_id": idx,
                "size": len(comp),
                "users_sample": ",".join(comp[:20]),
                "top_signals": ",".join([f"{s}:{c}" for s, c in sig_counter.most_common(5)]),
            })

        clusters = sorted(clusters, key=lambda r: r["size"], reverse=True)
        with open(OUT_CLUSTERS, "w", encoding="utf-8", newline="") as fcsv:
            writer = csv.DictWriter(fcsv, fieldnames=["cluster_id", "size", "users_sample", "top_signals"])
            writer.writeheader()
            writer.writerows(clusters)

        if G.number_of_nodes() > 0:
            nx.write_gexf(G, OUT_GRAPH)
    else:
        with open(OUT_CLUSTERS, "w", encoding="utf-8", newline="") as fcsv:
            writer = csv.DictWriter(fcsv, fieldnames=["cluster_id", "size", "users_sample", "top_signals"])
            writer.writeheader()

    # Pass 5: build bipartite user-item graph (explicable graph).
    B = nx.Graph()
    edge_limit = MAX_BIP_EDGES
    cur.execute("SELECT COUNT(*) FROM user_item")
    total_bip_edges = int(cur.fetchone()[0] or 0)
    if total_bip_edges > edge_limit:
        cur.execute(
            "SELECT user_id, item_id, cnt FROM user_item ORDER BY cnt DESC LIMIT ?",
            (edge_limit,),
        )
    else:
        cur.execute("SELECT user_id, item_id, cnt FROM user_item")

    bip_edges = 0
    for user_id, item_id, cnt in cur:
        B.add_node(user_id, node_type="user")
        B.add_node(item_id, node_type="item")
        B.add_edge(user_id, item_id, weight=int(cnt))
        bip_edges += 1

    if B.number_of_nodes() > 0:
        nx.write_gexf(B, OUT_BIP)
        print("Bipartite graph saved:", OUT_BIP, "edges:", bip_edges)

    # T1: top clusters report.
    if G.number_of_nodes() > 0:
        top_clusters = []
        deg = dict(G.degree(weight="weight"))
        cluster_signals = {c["cluster_id"]: c["top_signals"] for c in clusters}
        for idx, comp in enumerate(nx.connected_components(G)):
            comp = list(comp)
            top_users = sorted(comp, key=lambda u: deg.get(u, 0), reverse=True)[:10]
            item_counts = Counter()
            for u in comp:
                for item in B.neighbors(u) if B.has_node(u) else []:
                    if str(item).startswith(("DOM:", "RT:", "CONV:", "MENT:@", "TAG:#")):
                        w = B.edges[u, item].get("weight", 1)
                        item_counts[item] += int(w)
            top_items = [i for i, _c in item_counts.most_common(10)]
            top_clusters.append({
                "cluster_id": idx,
                "size": len(comp),
                "top_signals": cluster_signals.get(idx, ""),
                "top_users": ",".join(top_users),
                "top_items": ",".join(top_items),
            })

        top_clusters = sorted(top_clusters, key=lambda r: r["size"], reverse=True)
        with open(OUT_TOP_CLUSTERS, "w", encoding="utf-8", newline="") as fcsv:
            writer = csv.DictWriter(fcsv, fieldnames=["cluster_id", "size", "top_signals", "top_users", "top_items"])
            writer.writeheader()
            writer.writerows(top_clusters)

    # T2: top edges report.
    top_edges_sorted = sorted(top_edges, key=lambda x: x[0], reverse=True)
    with open(OUT_TOP_EDGES, "w", encoding="utf-8", newline="") as fcsv:
        writer = csv.DictWriter(fcsv, fieldnames=[
            "user_a", "user_b", "signals", "signal_counts", "total_occurrences"
        ])
        writer.writeheader()
        for _score, _seq, row in top_edges_sorted:
            writer.writerow({
                "user_a": row["user_a"],
                "user_b": row["user_b"],
                "signals": row["signals"],
                "signal_counts": row["signal_counts"],
                "total_occurrences": row["total_occurrences"],
            })

    # T3: time window report.
    with open(OUT_TIME_WINDOWS, "w", encoding="utf-8", newline="") as fcsv:
        writer = csv.DictWriter(fcsv, fieldnames=[
            "bucket_start", "bucket_end", "active_users", "num_coord_edges_created", "top_signal", "top_item"
        ])
        writer.writeheader()
        for bucket_id in sorted(bucket_stats.keys()):
            start_ts = bucket_id * WINDOW_SECS
            end_ts = start_ts + WINDOW_SECS
            row = bucket_stats[bucket_id]
            writer.writerow({
                "bucket_start": datetime.fromtimestamp(start_ts, tz=timezone.utc).isoformat(),
                "bucket_end": datetime.fromtimestamp(end_ts, tz=timezone.utc).isoformat(),
                "active_users": row.get("active_users", 0),
                "num_coord_edges_created": row.get("num_coord_edges_created", 0),
                "top_signal": row.get("top_signal", ""),
                "top_item": row.get("top_item", ""),
            })

    conn.close()

    if CLEANUP_TMP:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    print("Edges saved:", OUT_EDGES, "count:", edges_written)
    print("Clusters saved:", OUT_CLUSTERS, "count:", len(clusters))
    if G.number_of_nodes() > 0 and edges_written <= MAX_EDGES_FOR_GRAPH:
        print("Graph saved:", OUT_GRAPH)


if __name__ == "__main__":
    main()
