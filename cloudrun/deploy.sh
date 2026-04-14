#!/usr/bin/env bash
# Deploy RecallAlert-AI to Google Cloud Run + Cloud Functions

set -e

PROJECT_ID=${1:-"your-gcp-project-id"}
REGION=${2:-"us-central1"}
SERVICE_NAME="recall-alert-bot"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "🚀 Deploying RecallAlert-AI to Cloud Run"
echo "   Project: $PROJECT_ID"
echo "   Region: $REGION"
echo ""

# 1. Authenticate with GCP
echo "1️⃣  Authenticating with GCP..."
gcloud auth application-default login
gcloud config set project $PROJECT_ID

# 2. Create .env file from secrets
echo "2️⃣  Setting up secrets..."
gcloud secrets create gemini-api-key --data-file=<(echo $GOOGLE_API_KEY) 2>/dev/null || true
gcloud secrets create telegram-token --data-file=<(echo $TELEGRAM_BOT_TOKEN) 2>/dev/null || true
gcloud secrets create firebase-cred --data-file=secrets/recallai-b8c42-firebase-adminsdk-fbsvc-2c187ef233.json 2>/dev/null || true

# 3. Build Docker image
echo "3️⃣  Building Docker image..."
docker build -t $IMAGE_NAME:latest .

# 4. Push to Container Registry
echo "4️⃣  Pushing to Google Container Registry..."
docker push $IMAGE_NAME:latest

# 5. Deploy to Cloud Run
echo "5️⃣  Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_NAME:latest \
  --region $REGION \
  --platform managed \
  --memory 512Mi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --set-env-vars ENVIRONMENT=production,STORE_BACKEND=firebase \
  --update-secrets GOOGLE_API_KEY=gemini-api-key:latest,TELEGRAM_BOT_TOKEN=telegram-token:latest,FIREBASE_CRED_PATH=/secrets/firebase-cred.json \
  --allow-unauthenticated

# 6. Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format='value(status.url)')
echo ""
echo "✅ Deployment complete!"
echo "   Service URL: $SERVICE_URL"
echo ""

# 7. Set Telegram webhook to point to Cloud Run
echo "6️⃣  Configuring Telegram webhook..."
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d "url=$SERVICE_URL/telegram" \
  -H "Content-Type: application/json"

echo "✅ Telegram webhook configured!"
echo ""
echo "📊 Next steps:"
echo "   - View logs: gcloud run logs read $SERVICE_NAME --region $REGION"
echo "   - View metrics: https://console.cloud.google.com/run"
echo "   - Configure Cloud Scheduler for polling: see DEPLOYMENT.md"
