"""Cloud Function: Telegram bot webhook (HTTP endpoint).

Deploy with:
  gcloud functions deploy telegram_webhook \
    --gen2 \
    --runtime python311 \
    --region us-central1 \
    --source functions \
    --entry-point telegram_webhook \
    --trigger-http \
    --allow-unauthenticated \
    --set-env-vars ENVIRONMENT=production,STORE_BACKEND=firebase
"""

import json
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path so we can import src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mark as production to force Firestore
os.environ.setdefault("ENVIRONMENT", "production")
os.environ.setdefault("STORE_BACKEND", "firebase")

import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from src.bot import build_bot_handlers


async def telegram_webhook(request):
    """HTTP endpoint for Telegram webhook.

    Telegram sends JSON POST requests here. We parse and dispatch via Application.
    """
    try:
        if request.method == "POST":
            data = request.get_json()

            if not data:
                return {"statusCode": 400, "body": "No data"}

            # Initialize the Telegram app and handle the update
            app = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

            # Register handlers (same as in bot.py but without polling)
            await build_bot_handlers(app)

            # Process the incoming update
            update = Update.de_json(data, app.bot)
            await app.process_update(update)

            return {"statusCode": 200, "body": "OK"}

        else:
            return {"statusCode": 405, "body": "Method not allowed"}

    except Exception as e:
        logger.exception("Webhook error: %s", e)
        return {"statusCode": 500, "body": str(e)}
