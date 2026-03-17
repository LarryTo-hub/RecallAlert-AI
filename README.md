# RecallAlert-AI

An autonomous AI agent that monitors FDA and USDA food recalls in real time and delivers personalized, multilingual alerts to users via Telegram. Powered by Google Gemini.

Each year, an estimated 48 million people in the United States — roughly 1 in 6 — suffer from foodborne illness, leading to 128,000 hospitalizations and 3,000 deaths. While food recalls are meant to mitigate risk, more people were specifically sickened by recalled food in 2024/2025, a 25% increase in confirmed cases from the previous year. This project aims to help mitigate that risk by improving recall detection and timely notification.

## How It Works

```
FDA/USDA Sources ──► Fetcher ──► Store (SQLite) ──► Gemini Agent ──► Telegram Bot
                                                        │
                                                  Parses recalls
                                                  Matches pantries
                                                  Generates alerts
                                                  OCRs receipts
```

1. **Background polling loop** fetches the latest recalls from FDA (webpage + enforcement API) and USDA (webpage + mirror + RSS) every 60 minutes.
2. **Gemini Agent** parses each recall into structured fields (products, brands, severity, lot codes) and matches them against each user's pantry.
3. **Telegram Bot** sends personalized multilingual alerts with disposal instructions and refund info. Users respond with "Disposed" or "Ignored" feedback.

## Features

- **Multi-source fetching** — FDA webpage table, openFDA enforcement API, USDA FSIS webpage, Jina mirror, RSS fallback
- **Gemini-powered recall parsing** — extracts products, brands, severity, lot codes, and reason summaries
- **Smart pantry matching** — Gemini compares recalls against user pantry items with fuzzy matching
- **Receipt OCR** — send a receipt photo and Gemini Vision extracts product names automatically
- **Multilingual alerts** — generates alerts in English, Spanish, Vietnamese, Chinese, Korean, French
- **User feedback tracking** — "Disposed" / "Ignored" buttons on every alert, logged in the database
- **Deduplication** — recall_number or SHA1-based fallback IDs prevent duplicate storage

## Project Structure

```
recall-agent/
├── run.py                  # Entry point — starts bot + polling loop
├── requirements.txt        # Python dependencies
├── .env.example            # Template for environment variables
├── src/
│   ├── agent.py            # Gemini agent — parsing, matching, alerts, OCR
│   ├── bot.py              # Telegram bot — /start, /add, /pantry, receipts, feedback
│   ├── polling.py          # Background polling loop with APScheduler
│   ├── models.py           # Database models — User, PantryItem, Alert
│   ├── fetcher.py          # FDA + USDA recall fetchers (multi-source fallback)
│   ├── store.py            # Recall persistence (SQLite + optional Firestore)
│   ├── notifier.py         # SMS/email notification stubs (Twilio, SMTP)
│   └── main.py             # Legacy simple runner
├── scripts/
│   └── demo_fetch.py       # Demo script — fetch + print latest recalls
└── demo/
    └── recalls_demo.json   # Sample output from demo script
```

## Quickstart

### 1. Clone and set up

```powershell
git clone https://github.com/LarryTo-hub/RecallAlert-AI.git
cd RecallAlert-AI
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configure environment

```powershell
cp .env.example .env
# Edit .env and add:
#   GOOGLE_API_KEY=your-gemini-key      (from https://aistudio.google.com/app/apikey)
#   TELEGRAM_BOT_TOKEN=your-bot-token   (from @BotFather on Telegram)
```

### 3. Run the agent

```powershell
python run.py
```

This starts both the background polling loop and the Telegram bot. Open Telegram and message your bot:
- `/start` — register and choose language
- `/add Chicken nuggets` — add items to your pantry
- Send a **receipt photo** — OCR extracts products automatically
- `/pantry` — view your pantry
- `/clear` — clear your pantry
- `/help` — list all commands

### 4. Demo mode (no Telegram needed)

```powershell
python scripts/demo_fetch.py
```

Fetches the latest 5 FDA + USDA recalls and saves them to `demo/recalls_demo.json`.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | Yes | Google Gemini API key |
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram bot token from @BotFather |
| `DATABASE_URL` | No | Database URL (default: `sqlite:///recalls.db`) |
| `FETCH_INTERVAL_MINUTES` | No | Polling interval (default: `60`) |
| `LOG_LEVEL` | No | Logging level (default: `INFO`) |

## Tech Stack

- **Python 3.11+**
- **Google Gemini 2.0 Flash** — recall parsing, pantry matching, alert generation, receipt OCR
- **python-telegram-bot** — Telegram bot interface
- **SQLModel + SQLite** — user, pantry, alert, and recall storage
- **APScheduler** — background polling loop
- **BeautifulSoup + requests + feedparser** — web scraping and RSS parsing

## Security

- `.env` is in `.gitignore` — never commit API keys
- `.env.example` is safe to commit as a template
- For production, use a secrets manager (GitHub Secrets / Azure Key Vault)

## Licenses

N/A
