# RecallAlert-AI

An autonomous AI agent that monitors FDA and USDA food recalls in real time and delivers personalized alerts to users via a web interface. Powered by Google Gemini.

Each year, an estimated 48 million people in the United States — roughly 1 in 6 — suffer from foodborne illness, leading to 128,000 hospitalizations and 3,000 deaths. While food recalls are meant to mitigate risk, more people were specifically sickened by recalled food in 2024/2025, a 25% increase in confirmed cases from the previous year. This project aims to help mitigate that risk by improving recall detection and timely notification.

## How It Works

```
FDA/USDA Sources ──► Fetcher ──► Firestore ──► Gemini Agent ──► WebSocket
                                 (Recalls)  (Parsing + Matching) (Real-time Alerts)
                                     │
                                     └──► React Frontend
                                          (User Dashboard)
```

1. **Background polling loop** fetches the latest recalls from FDA (webpage + enforcement API) and USDA (webpage + mirror + RSS) every 60 minutes.
2. **Gemini Agent** parses each recall into structured fields (products, brands, severity, lot codes) and matches them against each user's pantry.
3. **Web Dashboard** allows users to:
   - Manage their pantry of products they own
   - View recalls matching their items
   - Submit feedback (disposed/ignored)
   - Search historic recalls
   - Customize alert preferences
4. **Real-time Updates** via WebSocket — users get instant notifications when recalls match their pantry without polling.

## Features

- **Multi-source fetching** — FDA webpage table, openFDA enforcement API, USDA FSIS webpage, Jina mirror, RSS fallback
- **Gemini-powered recall parsing** — extracts products, brands, severity, lot codes, and reason summaries
- **Smart pantry matching** — Gemini compares recalls against user pantry items with fuzzy matching
- **Receipt OCR** — send a receipt photo and Gemini Vision extracts product names automatically
- **Multilingual alerts** — generates alerts in English, Spanish, Vietnamese, Chinese, Korean, French
- **User feedback tracking** — submit "Disposed" / "Ignored" feedback for each alert, logged in database
- **Deduplication** — recall_number or SHA1-based fallback IDs prevent duplicate storage
- **REST API** — comprehensive API endpoints for recall queries, pantry management, feedback
- **WebSocket live updates** — real-time alert delivery when recalls match your pantry

## Architecture

**Backend Stack:**
- **FastAPI** — REST API + WebSocket server
- **Firestore** — Auto-scaling database (production) / SQLite (development)
- **Google Gemini 2.0** — AI-powered recall parsing and matching
- **Cloud Run** — Serverless container hosting (production)
- **Cloud Scheduler** — Automated polling every 60 minutes

**Frontend Stack:**
- **React** — Web dashboard (separate repository)
- **WebSocket** — Real-time alert notifications
- See: `website` branch for frontend code

## Project Structure

```
recall-agent/
├── run.py                  # Legacy entry point (for Telegram bot - deprecated)
├── requirements.txt        # Python dependencies
├── .env.example            # Template for environment variables
├── Dockerfile              # Container image for Cloud Run
├── docker-compose.yml      # Local development setup
├── src/
│   ├── api.py              # FastAPI application
│   ├── main_api.py         # API entry point with polling
│   ├── agent.py            # Gemini agent — parsing, matching, alerts, OCR
│   ├── polling.py          # Background polling loop (refactored for API)
│   ├── models.py           # Database models — User, PantryItem, Alert
│   ├── fetcher.py          # FDA + USDA recall fetchers (multi-source fallback)
│   ├── store.py            # Recall persistence (Firestore + SQLite)
│   ├── bot.py              # Legacy Telegram bot (deprecated)
│   ├── notifier.py         # SMS/email notification stubs (legacy)
│   ├── main.py             # Legacy simple runner
│   └── __pycache__/
├── functions/              # Google Cloud Functions (polling, webhooks)
├── cloudrun/               # Cloud Run deployment configs
├── scripts/
│   └── demo_fetch.py       # Demo script — fetch + print latest recalls
└── demo/
    └── recalls_demo.json   # Sample output from demo script
```

## Quickstart

### 1. Clone and set up

```bash
git clone https://github.com/LarryTo-hub/RecallAlert-AI.git
cd RecallAlert-AI
python -m venv .venv

# macOS/Linux:
source .venv/bin/activate
# Windows:
.\.venv\Scripts\Activate.ps1

pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add:
#   GOOGLE_API_KEY=your-gemini-key      (from https://aistudio.google.com/app/apikey)
#   JWT_SECRET_KEY=your-secret-key      (generate: python -c "import secrets; print(secrets.token_urlsafe())")
```

### 3. Run locally with Docker Compose

```bash
docker-compose up
```

Backend API: http://localhost:8080  
Frontend: http://localhost:3000 (run separately from `website` branch)
API Docs: http://localhost:8080/docs

### 4. Test the API

```bash
# Register user
curl -X POST http://localhost:8080/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123", "name": "User"}'

# Get recalls
curl http://localhost:8080/recalls?limit=5

# Add pantry item
curl -X POST http://localhost:8080/pantry/items \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"product_name": "Chicken nuggets", "brand": "Brand X"}'
```

See [API Documentation](#api-endpoints) below for all endpoints.

## 🚀 Production Deployment

### Option 1: Render (Recommended - Simplest)

**Easiest setup:** Git-connected, auto-deploy on push. No CLI needed.

```bash
# 1. Push to GitHub
git push origin main

# 2. Go to https://render.com → New → Blueprint
# 3. Connect your GitHub repo
# 4. Set secrets in dashboard (GOOGLE_API_KEY, JWT_SECRET_KEY, etc.)
# 5. Done! Auto-deploys on every push
```

**Services:**
- Web API: `recall-alert-api.onrender.com`
- Background Worker: Polling runs continuously
- Firestore: Database (Firebase)

**Cost:** ~$15-25/month (includes Gemini API)

**See:** [Render Deployment Guide](render/DEPLOYMENT.md) | [Quick Reference](render/QUICK_REFERENCE.md)

---

### Option 2: Google Cloud Run (Advanced - More Control)

**For GCP users:** More infrastructure control, Cloud Scheduler for polling.

```bash
cd cloudrun
bash deploy.sh your-gcp-project-id us-central1
```

**Architecture:**
- **Cloud Run** — API server (auto-scaling)
- **Cloud Scheduler** — Polling every 60 minutes
- **Firestore** — Database (Firebase)
- **Gemini 2.0** — AI recall parsing

**Cost:** ~$7-15/month (includes Gemini API)

**See:** [Cloud Run Deployment Guide](DEPLOYMENT.md) | [Quick Reference](cloudrun/QUICK_REFERENCE.md)

---

### Comparison

| Feature | Render | Cloud Run |
|---------|--------|-----------|
| **Setup Time** | 5 minutes | 15 minutes |
| **Complexity** | Simple (dashboard) | Medium (GCP CLI) |
| **Auto-deploy** | Yes (GitHub) | Manual (gcloud) |
| **Polling service** | Background worker | Cloud Scheduler |
| **Cost** | $15-25/mo | $7-15/mo |
| **Best for** | Quick start | GCP users, optimization |

**Recommendation:** Use **Render** if this is your first deployment. Switch to **Cloud Run** later if you need advanced GCP features.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENVIRONMENT` | No | `development` | Set to `production` on Cloud Run |
| `STORE_BACKEND` | No | `sqlite` | Storage: `sqlite` (dev) or `firebase` (prod) |
| `GOOGLE_API_KEY` | Yes | - | Gemini API key (https://aistudio.google.com/app/apikey) |
| `JWT_SECRET_KEY` | Yes (prod) | - | JWT signing key for authentication |
| `ALLOWED_ORIGINS` | No | `http://localhost:3000` | CORS origins (comma-separated) |
| `FIREBASE_CRED_PATH` | For Firebase | - | Path to Firebase service account JSON |
| `DATABASE_URL` | For SQLite | `sqlite:///recalls.db` | SQLite database path |
| `FETCH_INTERVAL_MINUTES` | No | `60` | How often to poll for recalls |
| `LOG_LEVEL` | No | `INFO` | Python logging level |
| `PORT` | No | `8080` | Server port |

## API Endpoints

### Authentication

```
POST /auth/register
  Register a new user
  Body: { email, password, name }
  Returns: { access_token, user_id }

POST /auth/login
  Login user
  Body: { email, password }
  Returns: { access_token, user_id }
```

### User Profile

```
GET /user/profile
  Get current user profile
  Auth: Required
  Returns: { id, email, name, language, created_at }

PUT /user/language?language=es
  Update user language preference
  Auth: Required
  Returns: { status, language }
```

### Pantry Management

```
GET /pantry
  Get user's pantry items
  Auth: Required
  Returns: [{ id, product_name, brand, lot_code, added_at }, ...]

POST /pantry/items
  Add item to pantry
  Auth: Required
  Body: { product_name, brand?, lot_code? }
  Returns: { id, product_name, brand, lot_code, added_at }

DELETE /pantry/items/{item_id}
  Delete specific pantry item
  Auth: Required
  Returns: { status }

DELETE /pantry
  Clear entire pantry
  Auth: Required
  Returns: { status }
```

### Recalls

```
GET /recalls?skip=0&limit=20&severity=high
  Get latest recalls (paginated)
  Returns: [{ recall_number, product_description, reason_for_recall, ... }, ...]

GET /recalls/matching
  Get recalls matching user's pantry
  Auth: Required
  Returns: [{ alert_id, recall_number, message, status, created_at }, ...]
```

### Alert Feedback

```
PUT /alerts/{alert_id}/feedback
  Submit feedback for an alert
  Auth: Required
  Body: { status: "disposed" | "ignored" }
  Returns: { status, alert_id, feedback }
```

### WebSocket

```
WS /ws/{user_id}
  Connect to real-time alert stream
  Message format: { type: "recall_alert", alert_id, recall_number, message, ... }
```

### Health

```
GET /health
  Health check endpoint
  Returns: { status: "ok" }

GET /
  API info
  Returns: { name, version, docs }
```

## Demo Mode (no setup needed)

```bash
python scripts/demo_fetch.py
```

Fetches the latest 5 FDA + USDA recalls and saves them to `demo/recalls_demo.json`.

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    RecallAlert-AI Data Flow                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  FDA/USDA APIs                                                  │
│      │                                                          │
│      ▼                                                          │
│  ┌─────────────────┐                                           │
│  │ Fetcher Module  │─── Multiple sources, fallback logic      │
│  └────────┬────────┘                                           │
│           │                                                    │
│           ▼                                                    │
│  ┌──────────────────────┐                                     │
│  │ Store (Firestore)    │─── Deduplication, persistence      │
│  └────────┬─────────────┘                                     │
│           │                                                   │
│           ▼                                                   │
│  ┌──────────────────────┐                                     │
│  │ Gemini Agent         │─── Parse, Match, Generate alerts    │
│  └────────┬─────────────┘                                     │
│           │                                                   │
│           ▼                                                   │
│  ┌──────────────────────┐     ┌─────────────────────────┐    │
│  │ Poll Results         │────▶│ WebSocket Broadcasting  │    │
│  │ (New Alerts)         │     │ (Real-time to clients)  │    │
│  └──────────────────────┘     └──────────┬──────────────┘    │
│                                          │                   │
│                                          ▼                   │
│                               ┌──────────────────┐            │
│                               │ React Dashboard  │            │
│                               │ (User Interface) │            │
│                               └──────────────────┘            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Troubleshooting

### Backend starts but WebSocket not connecting
- Check CORS settings in`.env`: `ALLOWED_ORIGINS=http://localhost:3000`
- Ensure frontend is accessing correct WebSocket URL

### No alerts being generated
- Check job is running: `docker-compose logs api`
- Verify pantry items are added: `GET /pantry`
- Check Gemini API key: `GOOGLE_API_KEY` in `.env`

### Out of memory errors
- Increase Docker memory: `docker-compose up --memory 2g`
- For Cloud Run: increase instance memory in deployment config

### Database errors (SQLite locked)
- Clear database: `rm recalls.db` and restart
- For production, use Firestore: set `STORE_BACKEND=firebase`

## Contributing

Pull requests welcome! Please:
1. Test locally with `docker-compose`
2. Update documentation
3. Follow existing code style

## License

MIT License — see LICENSE file for details

## Support

- **Issues**: GitHub Issues tab
- **Deployment Help**: See [DEPLOYMENT.md](DEPLOYMENT.md)
- **API Docs**: Interactive docs at `/docs` when running locally

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | Yes | Google Gemini API key |
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram bot token from @BotFather |
| `DATABASE_URL` | No | Database URL (default: `sqlite:///recalls.db`) |
| `FETCH_INTERVAL_MINUTES` | No | Polling interval (default: `60`) |
| `LOG_LEVEL` | No | Logging level (default: `INFO`) |

## Creating Your Own Telegram Bot

To use this system, you'll need your own Telegram bot token:

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a bot name (e.g., "My Recall AI Bot")
4. Choose a username ending in `bot` (e.g., `my_recall_ai_bot`)
5. BotFather replies with your token — copy it and paste into `.env` as `TELEGRAM_BOT_TOKEN`
6. (Optional) Use `/setcommands` with BotFather to set up command descriptions

The token is free and never expires unless you revoke it.

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
