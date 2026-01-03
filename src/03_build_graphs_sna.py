import os, json
from collections import defaultdict, Counter
from datetime import datetime
import networkx as nx

# Community detection (Louvain)
import community as community_louvain  # python-louvain

IN_PATH = "data/comments_filtered.jsonl"
OUT_DIR = "data"

OUT_BIPARTITE = os.path.join(OUT_DIR, "graph_user_video.gexf")
OUT_USER = os.path.join(OUT_DIR, "graph_user_user.gexf")
OUT_STATS = os.path.join(OUT_DIR, "sna_stats.json")

def parse_yt(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # (author_id, video_id) -> comment count
    uv_counts = defaultdict(int)

    # for basic dataset stats
    users = set()
    videos = set()
    dates = []

    with open(IN_PATH, "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            u = r["author_id"]
            v = r["video_id"]
            uv_counts[(u, v)] += 1
            users.add(u)
            videos.add(v)
            if r.get("published_at"):
                dates.append(parse_yt(r["published_at"]))

    # 1) Build bipartite graph (User <-> Video)
    B = nx.Graph()
    for (u, v), w in uv_counts.items():
        if not B.has_node(u):
            B.add_node(u, node_type="user")
        if not B.has_node(v):
            B.add_node(v, node_type="video")
        B.add_edge(u, v, weight=w)

    nx.write_gexf(B, OUT_BIPARTITE)
    print(f"[OK] Bipartite graph saved: {OUT_BIPARTITE}")
    print(f"     Nodes={B.number_of_nodes()}  Edges={B.number_of_edges()}")
    print(f"     Users={len(users)} Videos={len(videos)}")

    # 2) Project to user-user co-commenter graph
    # video -> set(users)
    video_to_users = defaultdict(set)
    for (u, v), w in uv_counts.items():
        video_to_users[v].add(u)

    G = nx.Graph()
    for v, uset in video_to_users.items():
        ulist = list(uset)
        # connect all pairs of users who commented on the same video
        for i in range(len(ulist)):
            for j in range(i + 1, len(ulist)):
                a, b = ulist[i], ulist[j]
                if G.has_edge(a, b):
                    G[a][b]["weight"] += 1
                else:
                    G.add_edge(a, b, weight=1)

    # Add degree as node attribute
    for n in G.nodes():
        G.nodes[n]["degree"] = G.degree(n)

    # 3) Basic SNA metrics
    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    density = nx.density(G) if n_nodes > 1 else 0.0
    avg_clustering = nx.average_clustering(G) if n_nodes > 1 else 0.0

    # Connected components
    components = list(nx.connected_components(G))
    largest_cc_size = max((len(c) for c in components), default=0)

    # Louvain communities (works on undirected graphs)
    # If graph is empty, skip
    community_count = 0
    modularity = None
    if n_edges > 0:
        partition = community_louvain.best_partition(G, weight="weight")
        # store community id on each node
        for node, cid in partition.items():
            G.nodes[node]["community"] = cid
        community_count = len(set(partition.values()))
        modularity = community_louvain.modularity(partition, G, weight="weight")

    # Top nodes by degree and weighted degree
    weighted_degree = {n: sum(d.get("weight", 1) for _, _, d in G.edges(n, data=True)) for n in G.nodes()}
    top_degree = sorted(G.degree, key=lambda x: x[1], reverse=True)[:10]
    top_wdegree = sorted(weighted_degree.items(), key=lambda x: x[1], reverse=True)[:10]

    nx.write_gexf(G, OUT_USER)
    print(f"[OK] User-user graph saved: {OUT_USER}")
    print(f"     Nodes={n_nodes}  Edges={n_edges}")
    print(f"     Density={density:.6f}  AvgClustering={avg_clustering:.4f}")
    if modularity is not None:
        print(f"     Louvain communities={community_count}  Modularity={modularity:.4f}")

    # Save stats for your report
    stats = {
        "input_file": IN_PATH,
        "date_min": dates and min(dates).isoformat() or None,
        "date_max": dates and max(dates).isoformat() or None,
        "comments_in_window": sum(uv_counts.values()),
        "unique_users": len(users),
        "unique_videos": len(videos),
        "bipartite_nodes": B.number_of_nodes(),
        "bipartite_edges": B.number_of_edges(),
        "user_graph_nodes": n_nodes,
        "user_graph_edges": n_edges,
        "user_graph_density": density,
        "user_graph_avg_clustering": avg_clustering,
        "largest_connected_component_size": largest_cc_size,
        "louvain_communities": community_count,
        "louvain_modularity": modularity,
        "top_degree_nodes": top_degree,
        "top_weighted_degree_nodes": top_wdegree,
    }
    with open(OUT_STATS, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    print(f"[OK] Stats saved: {OUT_STATS}")

if __name__ == "__main__":
    main()
