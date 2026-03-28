# 📋 Render Quick Reference

## One-Click Deploy

1. Go to https://render.com
2. Click **"New" → "Blueprint"**
3. Connect GitHub repo: `LarryTo-hub/RecallAlert-AI`
4. Auto-deploy enabled ✅
5. Done! Just push to `main` branch

## Secrets to Set in Render Dashboard

```
GOOGLE_API_KEY          = AIza... (from aistudio.google.com)
JWT_SECRET_KEY          = (generate: python -c "import secrets; print(secrets.token_urlsafe(32))")
FIREBASE_CRED_PATH      = /tmp/firebase-cred.json
ALLOWED_ORIGINS         = https://your-frontend.vercel.app
```

## Services

| Name | Type | Command | Auto-Deploy |
|------|------|---------|------------|
| `recall-alert-api` | Web | `python -m uvicorn src.main_api:app --host 0.0.0.0 --port $PORT` | Yes |
| `recall-alert-poller` | Background Worker | `python -m src.polling_worker` | Yes |

## Logs & Monitoring

```bash
# View API logs
Render Dashboard → recall-alert-api → Logs

# View poller logs
Render Dashboard → recall-alert-poller → Logs

# Health check API
curl https://recall-alert-api.onrender.com/health

# API docs
https://recall-alert-api.onrender.com/docs
```

## Environment

| Variable | Dev | Prod |
|----------|-----|------|
| ENVIRONMENT | development | production |
| STORE_BACKEND | sqlite | firebase |
| PORT | 8080 | 10000 |

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Service won't start | Check logs, verify env vars |
| Firebase auth fails | Verify credentials path, check permissions |
| WebSocket not connecting | Check CORS settings, use `wss://` not `ws://` |
| No recalls found | Check poller logs, verify Firestore connection |

## Cost (Pro Plan)

- Web service: $7/month
- Background worker: $7/month
- Firestore (Firebase): $5-10/month
- **Total: ~$15-25/month**

## Workflow

```
git commit → git push main → Render auto-builds → Deploy ✅
```

That's it! No CLI needed. Just push code and it deploys.
