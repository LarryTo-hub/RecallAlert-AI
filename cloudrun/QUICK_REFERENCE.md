# 📋 Cloud Deployment Quick Reference

## One-Command Deploy

```bash
cd cloudrun
bash deploy.sh your-gcp-project-id us-central1
```

## Step-by-Step Deployment

### 1. Authenticate
```bash
export PROJECT_ID="your-project"
gcloud auth login
gcloud config set project $PROJECT_ID
```

### 2. Create Secrets
```bash
gcloud secrets create gemini-api-key \
  --data="AIza..."

gcloud secrets create telegram-token \
  --data="123456:ABCdef..."

gcloud secrets create firebase-cred \
  --data-file=secrets/recallai-b8c42-firebase-adminsdk-fbsvc-2c187ef233.json
```

### 3. Build & Deploy
```bash
docker build -t gcr.io/$PROJECT_ID/recall-alert-bot:latest .
docker push gcr.io/$PROJECT_ID/recall-alert-bot:latest

gcloud run deploy recall-alert-bot \
  --image gcr.io/$PROJECT_ID/recall-alert-bot:latest \
  --region us-central1 \
  --memory 512Mi \
  --set-env-vars ENVIRONMENT=production,STORE_BACKEND=firebase
```

### 4. Configure Telegram Webhook
```bash
SERVICE_URL=$(gcloud run services describe recall-alert-bot \
  --region us-central1 --format='value(status.url)')

curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d "url=$SERVICE_URL/telegram"
```

### 5. Set Up Polling
```bash
# Create Pub/Sub topic
gcloud pubsub topics create recall-poll

# Create scheduler (every 60 min)
gcloud scheduler jobs create pubsub recall-poll-job \
  --schedule="0 * * * *" \
  --topic=recall-poll \
  --message-body='{"type": "poll"}' \
  --location=us-central1
```

## Monitoring

```bash
# View logs (live)
gcloud run logs read recall-alert-bot --region us-central1 --follow

# Check service status
gcloud run services describe recall-alert-bot --region us-central1

# View Firestore usage
gcloud firestore databases describe

# Test webhook
curl https://YOUR_SERVICE_URL/health
```

## Rolling Back

```bash
# List revisions
gcloud run revisions list --service=recall-alert-bot

# Deploy specific revision
gcloud run deploy recall-alert-bot \
  --image gcr.io/$PROJECT_ID/recall-alert-bot:HASH \
  --region us-central1
```

## Environment Configuration in Cloud Run

✅ **Automatic (via Secret Manager)**
- GOOGLE_API_KEY
- TELEGRAM_BOT_TOKEN
- FIREBASE_CRED_PATH

✅ **Set in `gcloud run deploy`**
- ENVIRONMENT=production
- STORE_BACKEND=firebase
- LOG_LEVEL=INFO

## Cost Estimation

| Service | Usage | Monthly |
|---------|-------|---------|
| Cloud Run | 100K requests | $1-2 |
| Firestore | 1M reads/month | $0.50 |
| Cloud Scheduler | 1 job | Free |
| Gemini API | 100K prompts | $5-10 |
| **Total** | | **~$7-15** |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "SQLite used instead of Firestore" | Ensure `ENVIRONMENT=production` before imports |
| Firestore permission error | Grant `roles/datastore.user` to service account |
| Webhook not responding | Check Cloud Run URL, test with curl |
| Out of memory | Increase `--memory 1Gi` in deployment |

See [DEPLOYMENT.md](DEPLOYMENT.md) for full guide.
