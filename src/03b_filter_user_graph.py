import networkx as nx

IN_GEXF = "data/graph_user_user.gexf"
OUT_GEXF = "data/graph_user_user_w2.gexf"

MIN_W = 2  # keep only pairs who co-commented on >=2 shared videos

G = nx.read_gexf(IN_GEXF)

H = nx.Graph()
for u, v, d in G.edges(data=True):
    w = int(float(d.get("weight", 1)))
    if w >= MIN_W:
        H.add_edge(u, v, weight=w)

# keep node attributes if present
for n in H.nodes():
    if n in G.nodes():
        H.nodes[n].update(G.nodes[n])

print("Original:", G.number_of_nodes(), "nodes,", G.number_of_edges(), "edges")
print("Filtered:", H.number_of_nodes(), "nodes,", H.number_of_edges(), "edges", f"(min_w={MIN_W})")

nx.write_gexf(H, OUT_GEXF)
print("Saved:", OUT_GEXF)
