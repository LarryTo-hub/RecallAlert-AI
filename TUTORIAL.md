# Team Tutorial — Recall AI

This document is a short, hands-on tutorial to onboard contributors to the Recall AI project. It shows the repo layout, local setup, a safe demo run, and suggested small tasks to assign.

Duration: 10–15 minutes (live) or follow as self-guided.

Prerequisites
- Windows with PowerShell
- Python 3.11+ installed and on PATH
- Git installed and configured (name/email)
- (Optional) A Twilio account and phone number for SMS tests

Quick repo overview
- `README.md` — quickstart and team notes
- `TUTORIAL.md` — this file
- `.env.example` — template for required environment variables (do NOT commit `.env` with secrets)
- `requirements.txt` — Python dependencies
- `src/` — primary Python package
  - `fetcher.py` — fetches recalls (FDA) and stubs for additional sources
  - `store.py` — SQLModel/SQLite persistence and simple dedupe
  - `notifier.py` — Twilio/email notifier helpers (dry-run support)
  - `agent.py` — LLM agent placeholder (future)
  - `main.py` — run-once runner for smoke tests
- `scripts/` — convenience scripts (demo, team tutorial)
- `demo/` — demo output (created by `scripts/demo_fetch.py`)

Quick setup (one-time per machine)
1. Open PowerShell and go to the project root:
```powershell
Set-Location "C:\Users\larry\OneDrive\Desktop\Recall AI\recall-agent"
```
2. Create and activate virtualenv:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
3. Upgrade pip and install dependencies (optional; you can skip if already installed):
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```
4. Copy `.env.example` to `.env` and fill in any test credentials you will use locally (do NOT commit `.env`):
```powershell
cp .env.example .env
# edit .env with your values (TWILIO, SMTP, TEST_TO, etc.)
```

Run the demo (safe/dry-run)
1. Run the demo fetch script which saves to `demo/recalls_demo.json` and prints a short summary:
```powershell
.\.venv\Scripts\Activate.ps1
python .\scripts\demo_fetch.py 5
```
2. Open `demo/recalls_demo.json` in VS Code to inspect fetched records.
3. Optionally run the smoke runner (persists to `recalls.db`):
```powershell
python -m src.main
```

Team walkthrough script (run during meeting)
- Run `scripts/team_tutorial.ps1` from PowerShell. It will perform checks, run the demo, and print guidance. Example:
```powershell
.\scripts\team_tutorial.ps1 -DemoLimit 5
```

What to show during the demo
- Terminal output from `demo_fetch.py` showing recall numbers and short descriptions
- `demo/recalls_demo.json` open in editor (prettified)
- `src/notifier.py` showing dry-run mode (explain Twilio integration and safety)
- `recalls.db` presence and a quick note about moving to Postgres in production

Short talking points (verbatim snippets)
- Elevator pitch: "Recall AI detects food recalls from public sources, stores them, deduplicates, and notifies customers via SMS/email/webhook."
- Architecture: "Sources → fetcher → store → agent (LLM) → notifier. Scheduler triggers fetches; FastAPI will expose health/trigger endpoints." 
- Safety: "We default notifier to dry-run for demos and require local `.env` for real creds. Never commit secrets."

Suggested tasks to assign (small & actionable)
- Fetcher: add USDA/RSS feed sources and unit tests (`src/fetcher.py`)
- Store: expand model, add notifications table and uniqueness constraints, add tests (`src/store.py`)
- Notifier: implement Twilio wrapper, email fallback, unsubscribe handling, and retries (`src/notifier.py`)
- API/Scheduler: create `src/app.py` with FastAPI endpoints and an APScheduler job to call `src.main.run_once()` on a schedule
- QA/CI: add `pytest` tests and a GitHub Actions workflow to run tests on PRs

Git workflow guidelines
- Use `main` as the default branch
- Create feature branches: `git checkout -b feature/<name>`
- Push and open a PR; request at least one reviewer
- Checklist for PRs: includes tests or test plan, no secrets, logging, and DB changes considered

Security and compliance
- `.env.example` is safe to commit; never commit real secrets.
- For production use a secrets store (GitHub Secrets / Azure Key Vault).
- For SMS: confirm recipients opt-in and include unsubscribe instructions.

Appendix: troubleshooting
- If `ModuleNotFoundError: No module named 'src'` occurs when running scripts, ensure you run from project root and activate `.venv`.
- If Git push is rejected because of divergent history, fetch and merge or open a new branch and PR.

Contact / next steps
- After the demo, create GitHub issues for the suggested tasks and assign owners.
- If you want, I can create those issues and assign placeholders.

---
This tutorial file was created to standardize onboarding for the team. Use it during your walkthrough and share follow-up tasks in the repo issues.
