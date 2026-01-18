# X (Twitter) OSINT - Coordination First

This project processes X (Twitter) CSV exports to detect coordinated activity.
The pipeline focuses on coordination signals (graphs + multi-signal rules). NLP
and influence analysis come after coordination is confirmed.

## Requirements

- Python 3.11+
- Virtual environment recommended

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

## Expected Data

- Put X CSVs in `data/` (e.g., `data/may_july_chunk_1.csv`).
- The ingestion step produces:
  - `data/comments.jsonl`
  - `data/videos.jsonl` (here "video" = conversationId)

## Pipeline (step by step)

1) Ingest X CSV (conversationId -> video_id)
```bash
python src/01_ingest_x_csv.py
```

2) SNA graphs (co-participation by conversationId)
```bash
python src/02_build_sna_graphs.py
```

3) Filter user graph (optional)
```bash
python src/03_filter_user_graph.py
```

4) ARL patterns (coordination motifs)
```bash
python src/04_mine_arl_rules.py
```

5) Score coordination (optional)
```bash
python src/05_score_coordination.py
```

6) Light NLP features (after coordination validation)
```bash
python src/06_nlp_features.py
```

7) Multi-signal coordination detection (1h, K=2, exact match)
```bash
python src/07_detect_coordination.py
```

## Project Structure

```
data/              # Raw CSVs + generated outputs
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
```

## Notes

- Grouping is by `conversationId` for coordination detection.
- ARL uses conversation channels, domains, hashtags, and mentions.
- The coordination script also generates `data/x_user_item.gexf` (user-item bipartite graph).
