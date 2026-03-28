# 🚀 Production Deployment Guide

RecallAlert-AI is now optimized for deployment on Google Cloud Platform with Firebase/Firestore.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Google Cloud Platform                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐        ┌─────────────────────────┐   │
│  │ Cloud Scheduler  │───────▶│  Cloud Tasks / Pub/Sub  │   │
│  │  (every 60 min)  │        │   (trigger polling)     │   │
│  └──────────────────┘        └────────────┬────────────┘   │
│                                           │                │
│  ┌──────────────────────────────────────┌─┴──────────┐     │
│  │                                      │            │     │
│  │         ┌──────────────────┐   ┌─────▼──────┐    │     │
│  │         │   Cloud Run      │   │   Storage  │    │     │
│  │         │ (Telegram Bot +  │◀─▶│ (Firestore)│    │     │
│  │         │ Polling Handler) │   │            │    │     │
│  │         └────────┬─────────┘   └────────────┘    │     │
│  │                  │                               │     │
│  │                  ▼                               │     │
│  │         ┌────────────────┐                       │     │
│  │         │  Gemini 2.0    │                       │     │
│  │         │  (AI parsing)  │                       │     │
│  │         └────────────────┘                       │     │
│  │                                                  │     │
│  └──────────────────────────────────────────────────┘     │
│                      ▲                                      │
│                      │                                      │
└──────────────────────┼──────────────────────────────────────┘
                       │
              ┌────────┴────────┐
              │  FDA/USDA APIs  │
              │  Telegram       │
              └─────────────────┘
```

## Prerequisites

- **GCP Project** with billing enabled
- **gcloud CLI** installed and authenticated
- **Docker** installed locally
- **Firebase Admin SDK** credentials downloaded (saved as secret)
- **Telegram Bot Token** (from @BotFather)
- **Gemini API Key** (from https://aistudio.google.com/app/apikey)

## Quick Deploy

### 1. Set environment variables

```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"
export TELEGRAM_BOT_TOKEN="123456:ABCdefGHIjklMNOpqrsTUVwxyz"
export GOOGLE_API_KEY="AIzaXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
```

### 2. Run deployment script

```bash
cd cloudrun
bash deploy.sh $PROJECT_ID $REGION
```

This will:
- ✅ Authenticate with GCP
- ✅ Create secrets in Secret Manager
- ✅ Build Docker image
- ✅ Deploy to Cloud Run
- ✅ Configure Telegram webhook

### 3. Set up Cloud Scheduler (polling trigger)

```bash
# Create a Pub/Sub topic for polling
gcloud pubsub topics create recall-poll

# Create Cloud Scheduler job (every 60 minutes)
gcloud scheduler jobs create pubsub recall-poll-job \
  --schedule "0 * * * *" \
  --topic recall-poll \
  --message-body '{"type": "poll"}' \
  --location $REGION
```

## Architecture Decisions

### Why Firestore (not Cloud SQL)?

- **Low write rate**: New recalls every 60 min → minimal cost
- **Native Firebase**: No additional management overhead
- **Auto-scaling**: Handles traffic spikes without configuration
- **Simplicity**: No connection pooling or database administration needed

### Why Cloud Run (not Cloud Functions)?

- **Long-running**: Polling cycle (~30-60s) fits better in Cloud Run
- **Multiple services**: Bot + Polling + Agent in one container
- **Flexibility**: Easy to refactor or add services later
- **Cost**: Cloud Functions would timeout for complex Gemini operations

### Why Cloud Scheduler + Pub/Sub (not APScheduler)?

- **No local state**: Each invocation is stateless (containers auto-restart)
- **Horizontal scaling**: Multiple containers handling different requests
- **Reliability**: Google manages scheduling and retries
- **Monitoring**: Native GCP monitoring and alerting

## Memory Management

### Instance Configuration

```yaml
Memory: 512 MB    # Sufficient for: Gemini API calls, Firestore ops
CPUs: 2           # Parallel Gemini processing for multiple users
Max Instances: 10 # Auto-scale to handle traffic spikes
```

### Startup/Shutdown

- **Startup**: `init_db()` initializes Firestore client once
- **Shutdown**: `cleanup()` called on SIGTERM (handled by Cloud Run)
- **No global state**: Each Cloud Run container is independent

### Garbage Collection

- Python GC handles in-memory cleanup automatically
- Firestore client reuses connection pool (managed by Firebase Admin SDK)
- Gemini API calls are single-request (no caching to avoid memory leaks)

## Environment Variables

Create `.env.production` for local testing:

```bash
# Production settings
ENVIRONMENT=production
STORE_BACKEND=firebase

# Secrets (stored in Google Secret Manager)
GOOGLE_API_KEY=<from https://aistudio.google.com/app/apikey>
TELEGRAM_BOT_TOKEN=<from @BotFather on Telegram>
FIREBASE_CRED_PATH=/secrets/firebase-cred.json

# Fetching
FETCH_INTERVAL_MINUTES=60

# Optional
LOG_LEVEL=INFO
```

For Cloud Run, use `.env.example` and populate secrets via `gcloud secrets`:

```bash
gcloud secrets create gemini-api-key --data-file=<(echo $GOOGLE_API_KEY)
gcloud secrets create telegram-token --data-file=<(echo $TELEGRAM_BOT_TOKEN)
gcloud secrets versions add firebase-cred --data-file=secrets/firebase-adminsdk.json
```

## Monitoring & Debugging

### View logs

```bash
gcloud run logs read recall-alert-bot --region us-central1 --limit 50
```

### Monitor metrics

```bash
# Cloud Run console: https://console.cloud.google.com/run
# Firestore usage: https://console.cloud.google.com/firestore
# Cloud Scheduler: https://console.cloud.google.com/cloudscheduler
```

### Test polling locally

```bash
# Set production environment
export ENVIRONMENT=production
export STORE_BACKEND=firebase
export GOOGLE_API_KEY=...
export TELEGRAM_BOT_TOKEN=...

# Run once
python src/main.py
```

## Troubleshooting

### "STORE_BACKEND defaulting to SQLite"
- Ensure `ENVIRONMENT=production` is set before importing `src.store`
- Check Cloud Run env vars in deployment config

### Firestore permission errors
- Verify service account has `Cloud Datastore User` role
- Check Firebase credentials path: `/secrets/firebase-cred.json`

### Telegram webhook not receiving messages
- Test webhook: `curl https://YOUR_SERVICE_URL/health`
- Verify Telegram token in Secret Manager: `gcloud secrets versions access latest --secret telegram-token`

### Out of memory errors
- Check Cloud Run instance memory usage in logs
- Increase memory: `--memory 1Gi` in `gcloud run deploy`
- Profile with: `--cpu 4` temporarily for debugging

## Cost Optimization

- **Cloud Run**: $0.40/million requests + $0.00001667/GB-second
- **Firestore**: Free tier includes 50K reads/day, $0.06/100K reads after
- **Cloud Scheduler**: Free tier includes 3 jobs
- **Gemini API**: Pay-as-you-go (~$0.075M tokens input, $0.30M output)

**Monthly estimate** (10K users, 100 recalls/month):
- Cloud Run: ~$1-2
- Firestore: ~$0.50-2
- Gemini: ~$5-10
- Total: ~$7-15/month

## Next Steps

1. ✅ Deploy to Cloud Run: Run `./deploy.sh`
2. ✅ Configure Cloud Scheduler: See section above
3. ⏭️ Set up monitoring alerts: https://console.cloud.google.com/monitoring
4. ⏭️ Add API rate limiting: Implement in `fetcher.py`
5. ⏭️ Enable Firestore backups: https://console.cloud.google.com/firestore

## Rollback

```bash
# Revert to previous Cloud Run revision
gcloud run deploy recall-alert-bot \
  --image gcr.io/$PROJECT_ID/recall-alert-bot:PREVIOUS_SHA \
  --region us-central1
```

## Support

For issues, check:
- Cloud Run logs: `gcloud run logs read recall-alert-bot`
- Cloud Scheduler job status: `gcloud scheduler jobs describe recall-poll-job`
- Firestore Database: https://console.cloud.google.com/firestore
