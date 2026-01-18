# YouTube Election OSINT

OSINT analysis project for elections via YouTube.

## 📋 Prerequisites

- Python 3.11 or higher
- A Google account with YouTube Data API v3 enabled
- A YouTube API key

## 🚀 Installation

### 1. Clone the project

```bash
git clone <repo-url>
cd yt-election-osint
```

### 2. Create a virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

If you get an execution policy error, run this first:
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

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file at the project root with your YouTube API key:

```env
YT_API_KEY=your_youtube_api_key_here
```

**How to get a YouTube API key:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the "YouTube Data API v3"
4. Create credentials (API key)
5. Copy the key into your `.env` file

## 📝 Usage

### Available scripts

1. **01_search_videos.py** - Search for YouTube videos
2. **02_fetch_comments.py** - Fetch comments from videos
3. **03_filter_comments_by_date.py** - Filter comments by date
4. **04_build_graphs_sna.py** - Build social network analysis graphs
5. **05_filter_user_graph.py** - Filter user graph
6. **06_mine_arl_rules.py** - Association rule mining
7. **07_score_users.py** - Score users
8. **08_final_suspicion_score.py** - Calculate final suspicion score

### Run scripts

Make sure the virtual environment is activated (you should see `(.venv)` in your terminal), then:

```bash
python src/01_search_videos.py
```

Or use the venv Python directly:

**Windows:**
```powershell
.venv\Scripts\python.exe src/01_search_videos.py
```

**Linux/Mac:**
```bash
.venv/bin/python src/01_search_videos.py
```

## 📁 Project Structure

```
yt-election-osint/
  data/              # Generated data (JSON, graphs, etc.)
  src/               # Python scripts
    01_search_videos.py
    02_fetch_comments.py
    03_filter_comments_by_date.py
    04_build_graphs_sna.py
    05_filter_user_graph.py
    06_mine_arl_rules.py
    07_score_users.py
    08_final_suspicion_score.py
    ...
  .env               # Environment variables (not versioned)
  requirements.txt   # Python dependencies
  README.md          # This file
```

## ⚠️ Important Notes

- The `.env` file contains sensitive information and is **not** versioned
- Data is stored in the `data/` folder
- Make sure you have sufficient quotas on your YouTube API

## 🐛 Troubleshooting

**Error "No module named 'dotenv'":**
- Verify that the virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`

**Error "Missing YT_API_KEY":**
- Verify that the `.env` file exists at the project root
- Verify that the API key is correctly defined in `.env`
