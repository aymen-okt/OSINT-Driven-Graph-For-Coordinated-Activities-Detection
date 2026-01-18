# Guide d'exécution complet — YouTube Election OSINT

Guide pas à pas pour exécuter le projet depuis le début.

## 📋 Prérequis

1. **Python 3.11 ou supérieur** installé
2. **Compte Google** avec YouTube Data API v3 activée
3. **Clé API YouTube** obtenue depuis [Google Cloud Console](https://console.cloud.google.com/)

---

## 🚀 ÉTAPE 1 : Configuration initiale

### 1.1 Cloner le projet (si depuis GitHub)

```bash
git clone <url-du-repo>
cd yt-election-osint
```

### 1.2 Créer l'environnement virtuel

**Windows (PowerShell):**
```powershell
python -m venv .venv
```

Si vous obtenez une erreur d'exécution au démarrage :
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Puis activer :
```powershell
.venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**Linux/Mac:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Vérification :** Vous devriez voir `(.venv)` au début de votre terminal.

### 1.3 Installer les dépendances

```bash
pip install -r requirements.txt
```

**Note :** Cela peut prendre quelques minutes (téléchargement de modèles NLP).

### 1.4 Installer le modèle spaCy (requis pour NLP)

```bash
python -m spacy download en_core_web_sm
```

### 1.5 Configurer le fichier `.env`

Créez un fichier `.env` à la racine du projet :

```env
YT_API_KEY=votre_cle_api_youtube_ici
```

**Comment obtenir une clé API YouTube :**
1. Allez sur [Google Cloud Console](https://console.cloud.google.com/)
2. Créez un nouveau projet ou sélectionnez un projet existant
3. Activez l'API "YouTube Data API v3"
4. Créez des identifiants → Clé API
5. Copiez la clé dans votre fichier `.env`

---

## 📝 ÉTAPE 2 : Exécution du pipeline

Assurez-vous que l'environnement virtuel est activé avant chaque exécution.

### Step A — Collecte des données

#### 2.1 Rechercher des vidéos

```bash
python src/01_search_videos.py
```

**Résultat :**
- `data/video_ids.json` — Liste des IDs de vidéos
- `data/videos.jsonl` — Métadonnées des vidéos (title, description, etc.)
- `data/search_log.json` — Logs de recherche

#### 2.2 Récupérer les commentaires

```bash
python src/02_fetch_comments.py
```

**Résultat :**
- `data/comments.jsonl` — Tous les commentaires collectés
- `data/comments_progress.json` — Progression (pour reprise)
- `data/errors.jsonl` — Erreurs rencontrées

**Note :** Ce script peut prendre du temps selon le nombre de vidéos. Il peut être interrompu et repris.

#### 2.3 Filtrer les commentaires par date

```bash
python src/03_filter_comments_by_date.py
```

**Résultat :**
- `data/comments_filtered.jsonl` — Commentaires filtrés dans la fenêtre temporelle

**Note :** Les dates de filtrage sont définies dans le script (par défaut : 2024-10-20 à 2024-11-10).

---

### Step D — Graph + ML + NLP

#### 2.6 Construire les graphes SNA

```bash
python src/04_build_graphs_sna.py
```

**Résultat :**
- `data/graph_user_video.gexf` — Graphe bipartite User-Video
- `data/graph_user_user.gexf` — Graphe User-User (co-commenters)
- `data/sna_stats.json` — Statistiques SNA

#### 2.7 Filtrer le graphe utilisateur (optionnel)

```bash
python src/05_filter_user_graph.py
```

**Résultat :** Graphe filtré selon critères (voir script pour paramètres).

#### 2.8 Miner les règles d'association (ARL)

```bash
python src/06_mine_arl_rules.py
```

**Résultat :**
- `data/arl_rules_fixed.csv` — Règles d'association extraites
- `data/user_rule_hits.csv` — Nombre de règles par utilisateur

#### 2.9 Scorer les utilisateurs (optionnel)

```bash
python src/07_score_users.py
```

**Résultat :** Scores intermédiaires par utilisateur.

#### 2.10 Score final (SNA + ARL + NLP)

```bash
python src/08_final_suspicion_score.py
```

**Résultat :**
- `data/final_user_scores.csv` — Scores finaux par utilisateur (avec NLP)
- `data/final_community_scores.csv` — Scores agrégés par communauté
- `data/top_suspicious_summary.json` — Résumé JSON pour rapports

**Formule du score final :**
```
Score(u) = 0.45 × z(SNA) + 0.30 × z(ARL) + 0.05 × z(Community) 
         + 0.15 × z(NLP_credibility) + 0.05 × z(NLP_similarity)
```

---

## 📊 Structure des données générées

```
data/
  ├── video_ids.json                 # IDs des vidéos (Step A)
  ├── videos.jsonl                   # Métadonnées vidéos (Step A)
  ├── comments.jsonl                 # Tous les commentaires (Step A)
  ├── comments_filtered.jsonl        # Commentaires filtrés (Step A)
  │
  │
  ├── graph_user_user.gexf           # Graphe User-User (Step D)
  ├── graph_user_video.gexf          # Graphe User-Video (Step D)
  ├── sna_stats.json                 # Stats SNA (Step D)
  ├── arl_rules_fixed.csv            # Règles ARL (Step D)
  ├── user_rule_hits.csv             # Règles par user (Step D)
  ├── final_user_scores.csv          # Scores finaux (Step D)
  ├── final_community_scores.csv     # Scores communauté (Step D)
  └── top_suspicious_summary.json    # Résumé (Step D)
```

---

## ⏱️ Durée estimée d'exécution

- **Step A** : 30 minutes - 2 heures (selon nombre de vidéos et commentaires)
- **Step D** : 5-15 minutes (graphes et scoring)

**Total :** 1-3 heures selon la taille du dataset

---

## 🐛 Dépannage

### Erreur "No module named 'dotenv'"

**Solution :** Vérifiez que le venv est activé, puis réinstallez :
```bash
pip install -r requirements.txt
```

### Erreur "Missing YT_API_KEY"

**Solution :** Vérifiez que `.env` existe et contient `YT_API_KEY=votre_cle`

### Erreur spaCy model not found

**Solution :** Installez le modèle :
```bash
python -m spacy download en_core_web_sm
```

### Erreur "Execution policy"

**Windows PowerShell :**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Script qui plante (quota API dépassé)

**Solution :** Attendez quelques heures puis relancez le script. Il reprendra où il s'est arrêté grâce aux fichiers de progression.

---

## ✅ Checklist d'exécution

- [ ] Python 3.11+ installé
- [ ] Projet cloné/localisé
- [ ] Environnement virtuel créé et activé
- [ ] Dépendances installées (`pip install -r requirements.txt`)
- [ ] Modèle spaCy installé (`python -m spacy download en_core_web_sm`)
- [ ] Fichier `.env` créé avec `YT_API_KEY`
- [ ] Step A : Vidéos collectées (01, 02, 02b)
- [ ] Step D : Graphes et scores calculés (03, 03b, 04, 05, 06)
- [ ] Résultats dans `data/final_user_scores.csv`

---

## 📝 Notes importantes

1. **Quotas API YouTube** : Limitez le nombre de vidéos/commentaires si vous avez des quotas restreints.
2. **Re-exécution** : Les scripts peuvent être relancés plusieurs fois (ils gèrent la progression).
3. **Données sensibles** : Le fichier `.env` n'est jamais versionné (dans `.gitignore`).

---

## 🎯 Résultat final

Le fichier `data/final_user_scores.csv` contient les scores de suspicion pour chaque utilisateur, combinant :
- Signaux de réseau social (SNA)
- Patterns d'association (ARL)
- Features NLP (crédibilité, similarité)

Les utilisateurs avec les scores les plus élevés sont les plus suspects selon votre modèle.




