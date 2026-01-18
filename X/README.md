# OSINT X (Twitter) - Coordination d'abord

Ce projet traite des exports CSV X (Twitter) pour détecter des activités coordonnées.
Le pipeline actuel met l'accent sur la détection de coordination via graphes et motifs
d'association. L'analyse désinformation/influence vient ensuite, une fois la coordination
confirmée.

## Prerequis

- Python 3.11+
- Environnement virtuel Python recommandé

## Installation

```bash
python -m venv .venv
```

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
.venv\Scripts\activate.bat
```

**Linux/Mac:**
```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

## Donnees attendues

- Place tes CSV X dans `data/` (ex: `data/may_july_chunk_1.csv`).
- Le script d'ingestion produit un format commun:
  - `data/comments.jsonl`
  - `data/videos.jsonl` (ici "video" = conversationId)

## Pipeline (execution etape par etape)

1) Ingestion CSV X (conversationId -> video_id)
```bash
python src/01_ingest_x_csv.py
```

2) Graphes SNA (co-participation par conversationId)
```bash
python src/02_build_sna_graphs.py
```

3) Filtrage du graphe utilisateur (optionnel)
```bash
python src/03_filter_user_graph.py
```

4) Motifs coordonnes (ARL)
```bash
python src/04_mine_arl_rules.py
```

5) Score utilisateurs (optionnel)
```bash
python src/05_score_coordination.py
```

6) NLP leger (apres validation coordination)
```bash
python src/06_nlp_features.py
```

7) Coordination multi-signal (1h, K=2, exact match)
```bash
python src/07_detect_coordination.py
```

## Structure du projet

```
data/              # CSV bruts + sorties JSON/graphes
src/
  01_ingest_x_csv.py
  02_build_sna_graphs.py
  03_filter_user_graph.py
  04_mine_arl_rules.py
  05_score_coordination.py
  06_nlp_features.py
  07_detect_coordination.py
  utils_io.py
  utils_text.py
archive/
  youtube/         # scripts YouTube archives
```

## Notes

- Le regroupement est fait par `conversationId` (coherence pour detection de coordination).
- Les motifs ARL utilisent canaux de conversation, domaines, hashtags et mentions.
- Une fois les clusters coordonnes confirmes, on peut ajouter un module NLP
  pour analyser desinformation / campagnes d'influence.
- Le script de coordination genere aussi `data/x_user_item.gexf` (biparti User-Item).
