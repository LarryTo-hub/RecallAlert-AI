# RecallAlert-AI / Recall Agent

RecallAlert-AI is an autonomous agent that monitors FDA/USDA food recalls and delivers timely alerts. It can be extended to provide translated alerts, photo-based pantry verification, and actionable guidance in users' preferred languages.

Each year, an estimated 48 million people in the United States—roughly 1 in 6—suffer from foodborne illness, leading to 128,000 hospitalizations and 3,000 deaths. While food recalls are meant to mitigate risk, more people were specifically sickened by recalled food in 2024/2025, a 25% increase in confirmed cases from the previous year. This project aims to help mitigate that risk by improving recall detection and timely notification.

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
- `src/notifier.py`: notification helper (Twilio + email gateway)
- `src/main.py`: simple runner / FastAPI app

Security note
- Commit `.env.example` to the repository so others know which variables are required.
- Never commit your real `.env` file with secrets. `.env` is included in `.gitignore` by default.

Features and next steps
- Extend notification backends (SMTP/Twilio/webhooks).
- Add periodic polling with APScheduler and a `/health` and `/trigger` FastAPI endpoints.
- Implement multi-language support and optional photo-based verification.

