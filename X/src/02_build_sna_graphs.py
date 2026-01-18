import os
import json
import networkx as nx
from collections import defaultdict
from community import community_louvain

COMMENTS_IN = "data/comments_filtered.jsonl"
COMMENTS_FALLBACK = "data/comments.jsonl"
OUT_BIP = "data/graph_user_video.gexf"
OUT_UU = "data/graph_user_user.gexf"
OUT_STATS = "data/sna_stats.json"
MIN_SHARED = 5
MIN_UV = 5


def main():
    # user-video bipartite edges: (user, video) -> count
    uv = defaultdict(int)
    users = set()
    videos = set()

    in_path = COMMENTS_IN if os.path.exists(COMMENTS_IN) else COMMENTS_FALLBACK
    if not os.path.exists(in_path):
        raise FileNotFoundError(f"Missing input file: {COMMENTS_IN} (fallback: {COMMENTS_FALLBACK})")

    with open(in_path, "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            u = r["author_id"]
            v = r["video_id"]
            uv[(u, v)] += 1
            users.add(u)
            videos.add(v)

    # Bipartite graph
    B = nx.Graph()
    for u in users:
        B.add_node(u, node_type="user")
    for v in videos:
        B.add_node(v, node_type="video")
    for (u, v), w in uv.items():
        if w >= MIN_UV:
            B.add_edge(u, v, weight=w)

    nx.write_gexf(B, OUT_BIP)
    print(f"[OK] Bipartite graph saved: {OUT_BIP}")
    print(f"     Nodes={B.number_of_nodes()}  Edges={B.number_of_edges()}")
    print(f"     Users={len(users)} Videos={len(videos)}")

    # User-user projection: weight = number of shared videos (co-comment)
    # For each video: connect all users who commented on it
    video_to_users = defaultdict(list)
    for (u, v), _w in uv.items():
        video_to_users[v].append(u)

    UU = nx.Graph()
    for u in users:
        UU.add_node(u, node_type="user")

    # accumulate shared videos count
    shared = defaultdict(int)
    for v, ulist in video_to_users.items():
        ulist = list(dict.fromkeys(ulist))
        n = len(ulist)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = ulist[i], ulist[j]
                if a > b:
                    a, b = b, a
                shared[(a, b)] += 1

    for (a, b), w in shared.items():
        if w >= MIN_SHARED:
            UU.add_edge(a, b, weight=int(w))

    # SNA stats
    density = nx.density(UU)
    avg_clust = nx.average_clustering(UU)

    # Louvain
    part = community_louvain.best_partition(UU, weight="weight")
    nx.set_node_attributes(UU, part, "community")
    modularity = community_louvain.modularity(part, UU, weight="weight")
    n_comms = len(set(part.values()))

    nx.write_gexf(UU, OUT_UU)
    print(f"[OK] User-user graph saved: {OUT_UU}")
    print(f"     Nodes={UU.number_of_nodes()}  Edges={UU.number_of_edges()}")
    print(f"     Density={density:.6f}  AvgClustering={avg_clust:.4f}")
    print(f"     Louvain communities={n_comms}  Modularity={modularity:.4f}")

    stats = {
        "nodes": UU.number_of_nodes(),
        "edges": UU.number_of_edges(),
        "density": density,
        "avg_clustering": avg_clust,
        "communities": n_comms,
        "modularity": modularity,
    }
    with open(OUT_STATS, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    print("[OK] Stats saved:", OUT_STATS)


if __name__ == "__main__":
    main()
