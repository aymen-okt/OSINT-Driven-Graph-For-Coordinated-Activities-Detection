# YouTube Election OSINT

Projet d'analyse OSINT pour les élections via YouTube.

## 📋 Prérequis

- Python 3.11 ou supérieur
- Un compte Google avec YouTube Data API v3 activée
- Une clé API YouTube

## 🚀 Installation

### 1. Cloner le projet

```bash
git clone <url-du-repo>
cd yt-election-osint
```

### 2. Créer un environnement virtuel

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Si vous obtenez une erreur d'exécution, exécutez d'abord:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
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

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 4. Configurer les variables d'environnement

Créez un fichier `.env` à la racine du projet avec votre clé API YouTube:

```env
YT_API_KEY=votre_cle_api_youtube_ici
```

**Comment obtenir une clé API YouTube:**
1. Allez sur [Google Cloud Console](https://console.cloud.google.com/)
2. Créez un nouveau projet ou sélectionnez un projet existant
3. Activez l'API "YouTube Data API v3"
4. Créez des identifiants (clé API)
5. Copiez la clé dans votre fichier `.env`

## 📝 Utilisation

### Scripts disponibles

1. **01_search_videos.py** - Recherche des vidéos YouTube
2. **02_fetch_comments.py** - Récupère les commentaires des vidéos
3. **02b_filter_comments_by_date.py** - Filtre les commentaires par date
4. **03_build_graphs_sna.py** - Construit les graphes d'analyse de réseau social
5. **03b_filter_user_graph.py** - Filtre le graphe des utilisateurs
6. **04_mine_rules_arl.py** - Extraction de règles d'association
7. **05_score_users.py** - Score les utilisateurs
8. **06_final_suspicion_score.py** - Calcule le score de suspicion final

### Exécuter les scripts

Assurez-vous que l'environnement virtuel est activé (vous devriez voir `(.venv)` dans votre terminal), puis:

```bash
python src/01_search_videos.py
```

Ou utilisez directement le Python du venv:

**Windows:**
```powershell
.venv\Scripts\python.exe src/01_search_videos.py
```

**Linux/Mac:**
```bash
.venv/bin/python src/01_search_videos.py
```

## 📁 Structure du projet

```
yt-election-osint/
  data/              # Données générées (JSON, graphes, etc.)
  src/               # Scripts Python
    01_search_videos.py
    02_fetch_comments.py
    ...
  .env               # Variables d'environnement (non versionné)
  requirements.txt   # Dépendances Python
  README.md          # Ce fichier
```

## ⚠️ Notes importantes

- Le fichier `.env` contient des informations sensibles et n'est **pas** versionné
- Les données sont stockées dans le dossier `data/`
- Assurez-vous d'avoir des quotas suffisants sur votre API YouTube

## 🐛 Dépannage

**Erreur "No module named 'dotenv'":**
- Vérifiez que l'environnement virtuel est activé
- Réinstallez les dépendances: `pip install -r requirements.txt`

**Erreur "Missing YT_API_KEY":**
- Vérifiez que le fichier `.env` existe à la racine du projet
- Vérifiez que la clé API est correctement définie dans `.env`

