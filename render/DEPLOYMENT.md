# 🚀 Render Deployment Guide

RecallAlert-AI is optimized for **Render**, a simple Git-based deployment platform perfect for Python apps.

## Why Render?

- ✅ **Git-connected**: Auto-deploy on push (no CLI needed)
- ✅ **Simple**: Dashboard configuration, no GCP complexity
- ✅ **Cost-effective**: ~$5-20/month for full stack
- ✅ **Background workers**: Perfect for polling service
- ✅ **Firestore integration**: Works seamlessly with Firebase

## Architecture

```
┌─────────────────────────────────────────────┐
│           GitHub Repository                │
│    (main branch auto-deploys on push)      │
└────────────┬────────────────────────────────┘
             │
     ┌───────┴────────┐
     │                │
     ▼                ▼
┌─────────┐    ┌──────────────────┐
│ Web     │    │ Background       │
│ Service │    │ Worker (Poller)  │
│ (API)   │    │ (Polling loop)   │
└────┬────┘    └────────┬─────────┘
     │                  │
     └──────────┬───────┘
                │
     ┌──────────▼──────────┐
     │  Firestore (GCP)    │
     │ (User data, alerts) │
     └─────────────────────┘
```

## Quick Setup

### 1. Prepare Your Repository

```bash
# Make sure you're on the main branch
git checkout main

# Add render.yaml to root (already provided)
# Confirm it's in the repo root:
ls render.yaml
# or in render/ folder:
ls render/

# Push to GitHub
git add .
git commit -m "Add Render deployment config"
git push origin main
```

### 2. Connect Render Dashboard

1. **Create Render account**: https://render.com
2. **New → Blueprint** (or manually add services)
3. **Connect GitHub repo**:
   - Select: `LarryTo-hub/RecallAlert-AI`
   - Branch: `main`
   - Auto-deploy: ✅ enabled

### 3. Set Environment Secrets in Render Dashboard

For each secret, create in **Render → Environment**:

```
GOOGLE_API_KEY          → AIza****** (from https://aistudio.google.com)
JWT_SECRET_KEY          → Generate: python -c "import secrets; print(secrets.token_urlsafe(32))"
FIREBASE_CRED_PATH      → /tmp/firebase-cred.json
```

⚠️ **Important**: Upload Firebase credentials:
- Go to **Render Dashboard → Settings → Upload File**
- Upload: `secrets/recallai-b8c42-firebase-adminsdk-fbsvc-2c187ef233.json`
- Copy to path: `/tmp/firebase-cred.json`

Or set as environment variable (base64 encoded):
```bash
cat secrets/recallai-b8c42-firebase-adminsdk-fbsvc-2c187ef233.json | base64
# → Copy the output to FIREBASE_CRED_CONTENT env var
```

Then in `src/main_api.py`, decode it:
```python
import base64
import os
if os.getenv("FIREBASE_CRED_CONTENT"):
    cred_json = base64.b64decode(os.getenv("FIREBASE_CRED_CONTENT")).decode()
    # Write to /tmp/firebase-cred.json
```

### 4. Deploy

Push to main branch:
```bash
git push origin main
```

Render will automatically:
- ✅ Build the Docker image
- ✅ Deploy the web service (API)
- ✅ Deploy the background worker (polling)
- ✅ Start both services

## Services

### Web Service (API)

- **URL**: `https://recall-alert-api.onrender.com` (auto-generated)
- **Port**: `10000` (Render's default)
- **Command**: `python -m uvicorn src.main_api:app --host 0.0.0.0 --port $PORT`
- **Resources**: Starter plan (0.5 CPU, 512MB RAM)

**Check status**:
```bash
curl https://recall-alert-api.onrender.com/health
# → {"status": "ok"}
```

### Background Worker (Polling)

- **Name**: `recall-alert-poller`
- **Type**: Background Worker
- **Command**: `python -m src.polling_worker`
- **Interval**: Runs continuously (polls every 60 minutes)
- **Logs**: Click service → Logs tab

**Monitor with**:
```bash
# In Render Dashboard → recall-alert-poller → Logs
```

## Environment Variables

All services inherit these variables:

| Variable | Value | Notes |
|----------|-------|-------|
| `ENVIRONMENT` | `production` | Enables Firestore backend |
| `STORE_BACKEND` | `firebase` | Use Firestore (not SQLite) |
| `FETCH_INTERVAL_MINUTES` | `60` | Poll every hour |
| `PORT` | `10000` | Render-provided |
| `LOG_LEVEL` | `INFO` | Logging level |
| `ALLOWED_ORIGINS` | `https://your-frontend.vercel.app` | CORS for React frontend |

## Linking Frontend

Connect your React frontend (running on Vercel or similar):

1. **Set ALLOWED_ORIGINS** in Render:
   ```
   ALLOWED_ORIGINS=https://your-app.vercel.app,https://www.your-app.com
   ```

2. **In React (website branch)**:
   ```javascript
   const API_URL = "https://recall-alert-api.onrender.com";
   const WS_URL = "wss://recall-alert-api.onrender.com";
   ```

3. **Verify connection**:
   ```bash
   curl https://recall-alert-api.onrender.com/health
   ```

## Monitoring

### Logs

**API Logs**:
```
Render Dashboard → recall-alert-api → Logs
```

**Worker Logs**:
```
Render Dashboard → recall-alert-poller → Logs
```

### Metrics

- **CPU/Memory**: Dashboard → Metrics
- **Errors**: Dashboard → Events

### Health Checks

```bash
# API is up
curl https://recall-alert-api.onrender.com/health

# API Docs
https://recall-alert-api.onrender.com/docs

# WebSocket connection (from frontend)
ws = new WebSocket('wss://recall-alert-api.onrender.com/ws/123')
```

## Troubleshooting

### Service won't start

**Check logs**:
```
Render Dashboard → Service → Logs
```

**Common issues**:
- Missing environment variables → Add in Dashboard
- Firebase credentials invalid → Verify path and format
- Python version mismatch → Ensure `runtime.txt` specifies Python 3.11

### Polling not running

1. Check background worker is deployed:
   ```
   Render Dashboard → recall-alert-poller → Status
   ```

2. View logs:
   ```
   Recall Dashboard → recall-alert-poller → Logs
   ```

3. Verify Firestore connection and credentials

### WebSocket connection fails

1. Check CORS settings:
   ```python
   # In src/api.py - check ALLOWED_ORIGINS
   ```

2. Verify frontend is using `wss://` (not `ws://`)

3. Check firewall/proxy settings

## Cost

❌ **No charges** for:
- First 750 hours/month (shared CPU)
- Small background workers
- Analytics, logs, monitoring

💰 **Charges**:
- After 750 hours (upgrade to Pro): $7/month per service
- Professional plan: Recommended for production

**Estimate** (with Pro):
- Web service: $7/month
- Background worker: $7/month
- Firestore: ~$5-10/month
- **Total: ~$15-25/month**

## Scaling

For higher traffic:

1. **Upgrade web service**:
   ```
   Dashboard → Service → Settings → Plan → Starter+ ($7/month)
   ```

2. **Increase worker resources**:
   ```
   render.yaml → background_worker → plan: standard
   ```

3. **Add database connection pool**:
   ```python
   # Already configured in Firestore, no action needed
   ```

## GitHub Actions (Optional Auto-Deploy)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Render

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Notify Render
        run: |
          curl -X POST https://api.render.com/deploy/srv-${{ secrets.RENDER_SERVICE_ID }}?key=${{ secrets.RENDER_API_KEY }}
```

Then add secrets to GitHub:
- `RENDER_SERVICE_ID`: From Render dashboard
- `RENDER_API_KEY`: From Render account settings

## Updating Code

Changes are **automatic**:

1. Push to main branch
2. Render detects changes
3. Rebuilds both services
4. Zero-downtime deployment

No manual steps needed!

## Support & Resources

- **Render Docs**: https://render.com/docs
- **Status Page**: https://status.render.com
- **Support**: https://render.com/support
- **Discord Community**: https://render.com/discord

## Next Steps

1. ✅ Push code to GitHub
2. ✅ Connect Render account
3. ✅ Deploy web service
4. ✅ Deploy background worker
5. ✅ Set up frontend (React on Vercel)
6. ✅ Monitor in Render dashboard
