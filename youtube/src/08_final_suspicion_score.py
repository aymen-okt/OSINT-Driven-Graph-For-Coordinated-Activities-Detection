# src/06_final_suspicion_score.py
"""
Final suspicion scoring (SNA + ARL)

Inputs (already produced by your pipeline):
- data/graph_user_user.gexf              (user-user co-commenter graph with edge weight + louvain community attr)
- data/user_rule_hits.csv                (author_id, num_channels, rule_hits)
Optionally:
- data/sna_stats.json                    (not required)
- data/arl_rules_fixed.csv               (not required for scoring; only for reporting/evidence)

Outputs:
- data/final_user_scores.csv             (per-user combined score + components)
- data/final_community_scores.csv        (per-community aggregates + density + top users)
- data/top_suspicious_summary.json        (a compact summary you can paste into report)

Scoring idea:
- SNA signal: weighted_degree (sum of co-comment weights)
- ARL signal: rule_hits
- Optional community signal: internal community density

Score(u) = 0.6 * z(weighted_degree) + 0.4 * z(rule_hits) + 0.1 * z(comm_density)
(community term is small; you can set it to 0 if you prefer)
"""

import os
import json
import math
import numpy as np
import pandas as pd
import networkx as nx
from collections import defaultdict

# -----------------------
# CONFIG (tune if needed)
# -----------------------
GEXF_IN = "data/graph_user_user.gexf"
RULE_HITS_IN = "data/user_rule_hits.csv"

OUT_USER = "data/final_user_scores.csv"
OUT_COMM = "data/final_community_scores.csv"
OUT_SUMMARY = "data/top_suspicious_summary.json"

# Weights for combined score
W_SNA = 0.60
W_ARL = 0.40
W_COMM = 0.10   # small influence; set to 0.0 if you don't want community density in user score

# Optional: filter edges by minimum weight before computing community density (not degree!)
# (Degree is computed from the original graph as-is. Density computed on filtered edges to avoid "everything connected".)
COMM_DENSITY_MIN_EDGE_WEIGHT = 2

# How many top items to export in summary
TOP_USERS = 50
TOP_COMMS = 25


# -----------------------
# Helpers
# -----------------------
def zscore(series: pd.Series) -> pd.Series:
    """Safe z-score (returns 0s if constant)."""
    if series.empty:
        return series
    mu = series.mean()
    sigma = series.std(ddof=0)
    if sigma == 0 or math.isnan(sigma):
        return pd.Series([0.0] * len(series), index=series.index)
    return (series - mu) / sigma

def weighted_degree(G: nx.Graph) -> dict:
    """Sum of edge weights for each node."""
    wd = {}
    for n in G.nodes():
        s = 0.0
        for _, _, d in G.edges(n, data=True):
            w = d.get("weight", 1)
            try:
                w = float(w)
            except Exception:
                w = 1.0
            s += w
        wd[n] = s
    return wd

def community_density_subgraph(G: nx.Graph, nodes: list) -> float:
    """Density of induced subgraph on nodes (simple unweighted density)."""
    if len(nodes) <= 1:
        return 0.0
    H = G.subgraph(nodes)
    return nx.density(H)

def build_filtered_graph_for_density(G: nx.Graph, min_w: int) -> nx.Graph:
    """Filter edges by weight threshold for density computation only."""
    H = nx.Graph()
    for u, v, d in G.edges(data=True):
        w = d.get("weight", 1)
        try:
            w = int(float(w))
        except Exception:
            w = 1
        if w >= min_w:
            H.add_edge(u, v, weight=w)
    # keep node attrs
    for n in H.nodes():
        if n in G.nodes():
            H.nodes[n].update(G.nodes[n])
    return H


# -----------------------
# Main
# -----------------------
def main():
    if not os.path.exists(GEXF_IN):
        raise FileNotFoundError(f"Missing {GEXF_IN}")
    if not os.path.exists(RULE_HITS_IN):
        raise FileNotFoundError(f"Missing {RULE_HITS_IN}")

    # 1) Load graph (user-user)
    G = nx.read_gexf(GEXF_IN)
    print("Loaded graph:", G.number_of_nodes(), "nodes,", G.number_of_edges(), "edges")

    # Community id should already be present from your Louvain step
    # But if missing, we assign community=-1
    comm = {}
    for n, attrs in G.nodes(data=True):
        cid = attrs.get("community", -1)
        try:
            cid = int(cid)
        except Exception:
            cid = -1
        comm[n] = cid

    # 2) Compute SNA features
    wd = weighted_degree(G)
    df_sna = pd.DataFrame({
        "author_id": list(wd.keys()),
        "weighted_degree": list(wd.values()),
        "community": [comm.get(a, -1) for a in wd.keys()],
        "degree": [G.degree(a) for a in wd.keys()],
    })

    # 3) Load ARL features (rule hits)
    df_arl = pd.read_csv(RULE_HITS_IN)
    # ensure types
    if "rule_hits" not in df_arl.columns:
        raise ValueError("user_rule_hits.csv must contain rule_hits")
    df_arl["rule_hits"] = pd.to_numeric(df_arl["rule_hits"], errors="coerce").fillna(0).astype(int)

    # 4) Merge
    df = df_sna.merge(df_arl, on="author_id", how="left")
    df["rule_hits"] = df["rule_hits"].fillna(0).astype(int)
    df["num_channels"] = df.get("num_channels", pd.Series([0] * len(df))).fillna(0).astype(int)

    # 5) Community-level density (computed on a filtered graph for interpretability)
    Gd = build_filtered_graph_for_density(G, COMM_DENSITY_MIN_EDGE_WEIGHT)
    comm_to_nodes = defaultdict(list)
    for a, cid in df[["author_id", "community"]].itertuples(index=False):
        comm_to_nodes[int(cid)].append(a)

    comm_density = {}
    comm_size = {}
    for cid, nodes in comm_to_nodes.items():
        comm_size[cid] = len(nodes)
        comm_density[cid] = community_density_subgraph(Gd, nodes)

    df["community_size"] = df["community"].map(lambda x: comm_size.get(int(x), 0))
    df["community_density_w2"] = df["community"].map(lambda x: comm_density.get(int(x), 0.0))

    # 6) Z-score normalize main features
    df["z_weighted_degree"] = zscore(df["weighted_degree"])
    df["z_rule_hits"] = zscore(df["rule_hits"])
    df["z_comm_density"] = zscore(df["community_density_w2"])

    # 7) Final suspicion score
    df["suspicion_score"] = (
        W_SNA * df["z_weighted_degree"] +
        W_ARL * df["z_rule_hits"] +
        W_COMM * df["z_comm_density"]
    )

    df = df.sort_values("suspicion_score", ascending=False)

    # 8) Save user scores
    os.makedirs("data", exist_ok=True)
    df.to_csv(OUT_USER, index=False)
    print("Saved:", OUT_USER)

    # 9) Community scores (aggregate)
    comm_df = df.groupby("community").agg(
        community_size=("author_id", "count"),
        avg_weighted_degree=("weighted_degree", "mean"),
        avg_rule_hits=("rule_hits", "mean"),
        avg_suspicion=("suspicion_score", "mean"),
        max_suspicion=("suspicion_score", "max"),
        density_w2=("community_density_w2", "first"),
    ).reset_index()

    # Add "top users" per community (IDs only, still anonymized)
    top_users_per_comm = defaultdict(list)
    for cid, sub in df.groupby("community"):
        top_users_per_comm[int(cid)] = sub.head(10)["author_id"].tolist()

    comm_df["top_users"] = comm_df["community"].map(lambda c: top_users_per_comm.get(int(c), []))

    comm_df = comm_df.sort_values("avg_suspicion", ascending=False)
    comm_df.to_csv(OUT_COMM, index=False)
    print("Saved:", OUT_COMM)

    # 10) Summary json for report writing
    summary = {
        "graph": {
            "nodes": int(G.number_of_nodes()),
            "edges": int(G.number_of_edges()),
            "comm_density_min_edge_weight": COMM_DENSITY_MIN_EDGE_WEIGHT,
        },
        "scoring_weights": {"W_SNA": W_SNA, "W_ARL": W_ARL, "W_COMM": W_COMM},
        "top_users": df.head(TOP_USERS)[
            ["author_id", "community", "suspicion_score", "weighted_degree", "rule_hits", "community_density_w2"]
        ].to_dict(orient="records"),
        "top_communities": comm_df.head(TOP_COMMS)[
            ["community", "community_size", "avg_suspicion", "max_suspicion", "density_w2", "avg_rule_hits", "avg_weighted_degree", "top_users"]
        ].to_dict(orient="records"),
    }

    with open(OUT_SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print("Saved:", OUT_SUMMARY)

    print("\nTop 10 users by suspicion_score:")
    print(df.head(10)[["author_id", "community", "suspicion_score", "weighted_degree", "rule_hits", "community_density_w2"]].to_string(index=False))

    print("\nTop 10 communities by avg_suspicion:")
    print(comm_df.head(10)[["community", "community_size", "avg_suspicion", "density_w2", "avg_rule_hits"]].to_string(index=False))


if __name__ == "__main__":
    main()
