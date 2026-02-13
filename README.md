# Recall Agent

Minimal scaffold for a food-recall tracking agent.

Quickstart

1. Create and activate a Python 3.11+ virtualenv:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and fill in credentials.
3. Run a quick fetch (example):

```powershell
python -m src.main
```

Files
- `src/fetcher.py`: fetch recall sources (FDA, RSS)
- `src/store.py`: SQLite models and persistence
- `src/notifier.py`: notification helper stubs
- `src/main.py`: simple runner / FastAPI app

Security note: commit `.env.example` to the repository so others know which variables are required, but never commit your real `.env` file with secrets. `.env` is in `.gitignore` by default.

