# OSINT R&D (X + YouTube)

Ce depot contient deux projets separes :

- `X/` : detection d'activites coordonnees sur X (Twitter).
- `youtube/` : pipeline OSINT YouTube (collecte + graphes + scoring).

Chaque dossier est autonome avec son propre `requirements.txt`.

## X (Twitter) — Execution

Depuis `X/` :

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python src/01_ingest_x_csv.py
python src/02_build_sna_graphs.py
python src/03_filter_user_graph.py
python src/04_mine_arl_rules.py
python src/05_score_coordination.py
python src/06_nlp_features.py
python src/07_detect_coordination.py
```

Sorties principales :
- `data/coordination_edges.csv`
- `data/coordination_clusters.csv`
- `data/x_user_item.gexf`
- `data/x_top_clusters.csv`
- `data/x_top_edges.csv`
- `data/x_time_windows.csv`

## YouTube — Execution

Depuis `youtube/` :

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python src/01_search_videos.py
python src/02_fetch_comments.py
python src/03_filter_comments_by_date.py
python src/04_build_graphs_sna.py
python src/05_filter_user_graph.py
python src/06_mine_arl_rules.py
python src/07_score_users.py
python src/08_final_suspicion_score.py
```

## Notes Git

- `X/data/` est ignore (sauf les deux CSV bruts).
- `.venv/` est ignore.
