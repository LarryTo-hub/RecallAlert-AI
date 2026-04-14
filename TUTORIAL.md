# Team Tutorial — Recall AI

This document is a short, hands-on tutorial to onboard contributors to the Recall AI project. It shows the repo layout, local setup, how to test the agent, and suggested tasks to assign.

Duration: 10–15 minutes (live) or follow as self-guided.

## Prerequisites
- Windows with PowerShell
- Python 3.11+ installed and on PATH
- Git installed and configured (name/email)
- A Google Gemini API key (free: https://aistudio.google.com/app/apikey)
- A Telegram bot token (free: message @BotFather on Telegram → `/newbot`)

## Architecture Overview

```
FDA/USDA Sources ──► fetcher.py ──► store.py (SQLite)
                                        │
                        polling.py (every 60 min)
                                        │
                                   agent.py (Gemini)
                                  ┌─────┴─────┐
                            parse_recall   match_pantry
                                  │            │
                            generate_alert (multilingual)
                                  │
                              bot.py (Telegram)
                                  │
                            User gets alert
                         [Disposed] [Ignored]
```

## Repo Layout
- `run.py` — **entry point** — starts the Telegram bot + background polling loop
- `.env.example` — template for required environment variables
- `requirements.txt` — Python dependencies
- `src/`
  - `agent.py` — Gemini-powered recall parsing, pantry matching, multilingual alerts, receipt OCR
  - `bot.py` — Telegram bot interface (/start, /add, /pantry, receipt photos, feedback buttons)
  - `polling.py` — Background polling loop (APScheduler) — fetches recalls, matches pantries, sends alerts
  - `models.py` — Database models: User, PantryItem, Alert (SQLModel/SQLite)
  - `fetcher.py` — Multi-source recall fetchers (FDA webpage + enforcement API, USDA webpage + mirror + RSS)
  - `store.py` — Recall persistence with deduplication (SQLite + optional Firestore)
  - `notifier.py` — SMS/email notification helpers (Twilio, SMTP gateway)
  - `main.py` — Legacy simple runner (fetch + store, no bot)
- `scripts/` — convenience scripts
  - `demo_fetch.py` — fetch and print latest recalls without running the bot
- `demo/` — demo output files

## Quick Setup (one-time per machine)

1. Open PowerShell and go to the project root:
```powershell
Set-Location "C:\Users\larry\OneDrive\Desktop\Recall AI\recall-agent"
```

2. Create and activate virtualenv:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies:
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

4. Copy `.env.example` to `.env` and add your keys:
```powershell
cp .env.example .env
# Edit .env and fill in:
#   GOOGLE_API_KEY=your-gemini-key
#   TELEGRAM_BOT_TOKEN=your-bot-token
```

## Testing the Agent

### Test 1: Fetch recalls (no API keys needed)
```powershell
python scripts/demo_fetch.py
```
Fetches 5 FDA + 5 USDA recalls, saves to `demo/recalls_demo.json`, prints a summary.

### Test 2: Test Gemini parsing (needs GOOGLE_API_KEY)
```powershell
python -c "
from src.agent import parse_recall
from src.fetcher import fetch_fda_recalls
recalls = fetch_fda_recalls(1)
if recalls:
    parsed = parse_recall(recalls[0])
    import json
    print(json.dumps(parsed, indent=2))
"
```
Should output structured JSON with products, brands, severity, lot_codes, and reason_summary.

### Test 3: Test Telegram bot connection (needs TELEGRAM_BOT_TOKEN)
```powershell
python -c "
import os, requests
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('src/agent.py').resolve().parent.parent / '.env')
token = os.getenv('TELEGRAM_BOT_TOKEN')
resp = requests.get('https://api.telegram.org/bot' + token + '/getMe', timeout=10)
print(resp.json())
"
```
Should show `{'ok': True, 'result': {'username': 'your_bot_name', ...}}`.

### Test 4: Run the full system
```powershell
python run.py
```
This starts:
- The background polling loop (fetches recalls every 60 minutes, runs once immediately)
- The Telegram bot (listens for user commands)

Then open Telegram and message your bot:
1. `/start` — register and pick a language (en, es, vi, zh, ko, fr)
2. `/add Chicken nuggets` — manually add a pantry item
3. Send a **receipt photo** — Gemini Vision OCR extracts products
4. `/pantry` — view your items
5. `/clear` — clear pantry
6. `/help` — list all commands

When the polling loop finds a recall matching your pantry, you'll receive an alert with **Disposed / Ignored** feedback buttons.

## Key Components Explained

### agent.py (Gemini Agent)
- `parse_recall(recall)` — extracts products, brands, severity, lot codes from a raw recall
- `match_pantry(parsed_recall, pantry_items)` — finds which pantry items are affected
- `generate_alert(recall, matched_items, language)` — writes a multilingual alert message
- `ocr_receipt(image_bytes)` — extracts product names from a receipt photo

### bot.py (Telegram Bot)
- `/start` — language selection with inline keyboard
- `/add <product>` — manual pantry entry
- Photo handler — downloads image, runs OCR, stores extracted items
- Feedback callback — records "disposed" or "ignored" responses

### polling.py (Background Loop)
- Runs on APScheduler (configurable interval via `FETCH_INTERVAL_MINUTES`)
- Fetches FDA + USDA recalls → stores new ones → parses with Gemini → matches all users' pantries → sends Telegram alerts

### models.py (Database)
- `User` — telegram_id, language preference
- `PantryItem` — product_name, brand, lot_code, source (manual/receipt)
- `Alert` — links user to recall, stores message text and feedback status

## Suggested Tasks to Assign

- **Web interface**: Build a FastAPI frontend using the same `agent.py` functions
- **More languages**: Add language options to `SUPPORTED_LANGUAGES` in `bot.py`
- **Testing**: Add pytest tests for `parse_recall`, `match_pantry`, and `ocr_receipt`
- **Deployment**: Dockerize and deploy to a cloud provider
- **Notifications**: Extend to SMS (Twilio) and email alongside Telegram
- **CI/CD**: Add GitHub Actions workflow to run tests on PRs

## Git Workflow
- Use `main` as the default branch
- Create feature branches: `git checkout -b feature/<name>`
- Push and open a PR; request at least one reviewer
- Checklist for PRs: includes tests, no secrets, logging, DB changes considered

## Security and Compliance
- `.env.example` is safe to commit; never commit real secrets
- `.env` is in `.gitignore`
- For production use a secrets manager (GitHub Secrets / Azure Key Vault)
- For SMS: confirm recipients opt-in and include unsubscribe instructions

## Troubleshooting
- **`ModuleNotFoundError: No module named 'src'`** — run from project root with `.venv` activated
- **`GOOGLE_API_KEY is not set`** — make sure `.env` is saved (Ctrl+S) with your key
- **`TELEGRAM_BOT_TOKEN` errors** — get a token from @BotFather on Telegram (`/newbot`)
- **USDA returns empty results** — this is expected; the Jina mirror fallback handles it automatically
- **Git push rejected** — fetch and merge, or create a new branch and PR
