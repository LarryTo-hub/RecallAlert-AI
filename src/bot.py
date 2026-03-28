"""Telegram bot interface for Recall Alert AI."""

from __future__ import annotations

import logging
import os

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.models import (
    init_models_db,
    get_or_create_user,
    set_user_language,
    add_pantry_item,
    get_pantry,
    clear_pantry,
    update_alert_feedback,
)
from src.agent import ocr_receipt

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Español",
    "vi": "Tiếng Việt",
    "zh": "中文",
    "ko": "한국어",
    "fr": "Français",
}


# ── /start ────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message + language selection."""
    init_models_db()
    tg_id = update.effective_user.id
    get_or_create_user(tg_id)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"lang:{code}")]
        for code, label in SUPPORTED_LANGUAGES.items()
    ])

    await update.message.reply_text(
        "👋 Welcome to Recall Alert AI!\n\n"
        "I monitor FDA & USDA food recalls and alert you if anything "
        "in your pantry is affected.\n\n"
        "First, choose your language:",
        reply_markup=keyboard,
    )


# ── Language callback ─────────────────────────────────────────────────────

async def cb_language(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle language selection from inline keyboard."""
    query = update.callback_query
    await query.answer()

    data = query.data  # "lang:en"
    lang_code = data.split(":", 1)[1]
    tg_id = update.effective_user.id
    set_user_language(tg_id, lang_code)

    lang_name = SUPPORTED_LANGUAGES.get(lang_code, lang_code)
    await query.edit_message_text(
        f"✅ Language set to {lang_name}.\n\n"
        "You can now:\n"
        "• /add <product> — add an item to your pantry\n"
        "• Send a receipt photo — I'll OCR it and add products\n"
        "• /pantry — view your pantry\n"
        "• /clear — clear your pantry\n"
        "• /language — change language\n"
        "• /help — show all commands"
    )


# ── /language ──────────────────────────────────────────────────────────────

async def cmd_language(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Re-select language."""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"lang:{code}")]
        for code, label in SUPPORTED_LANGUAGES.items()
    ])
    await update.message.reply_text("Choose your language:", reply_markup=keyboard)


# ── /add ──────────────────────────────────────────────────────────────────

async def cmd_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually add a pantry item.  Usage: /add Chicken nuggets"""
    init_models_db()
    tg_id = update.effective_user.id
    user = get_or_create_user(tg_id)

    text = update.message.text
    # Strip the /add command prefix
    product_name = text.split(None, 1)[1] if len(text.split(None, 1)) > 1 else ""
    if not product_name.strip():
        await update.message.reply_text("Usage: /add <product name>")
        return

    item = add_pantry_item(user.id, product_name.strip(), source="manual")
    await update.message.reply_text(f"✅ Added to pantry: {item.product_name}")


# ── /pantry ───────────────────────────────────────────────────────────────

async def cmd_pantry(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the user's pantry."""
    init_models_db()
    tg_id = update.effective_user.id
    user = get_or_create_user(tg_id)
    items = get_pantry(user.id)

    if not items:
        await update.message.reply_text("Your pantry is empty. Use /add or send a receipt photo.")
        return

    lines = [f"📦 Your pantry ({len(items)} items):\n"]
    for i, it in enumerate(items, 1):
        brand_str = f" ({it.brand})" if it.brand else ""
        lot_str = f" [lot: {it.lot_code}]" if it.lot_code else ""
        lines.append(f"  {i}. {it.product_name}{brand_str}{lot_str}")
    await update.message.reply_text("\n".join(lines))


# ── /clear ────────────────────────────────────────────────────────────────

async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear the user's pantry."""
    init_models_db()
    tg_id = update.effective_user.id
    user = get_or_create_user(tg_id)
    count = clear_pantry(user.id)
    await update.message.reply_text(f"🗑️ Cleared {count} item(s) from your pantry.")


# ── /help ─────────────────────────────────────────────────────────────────

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 Recall Alert AI Commands:\n\n"
        "/start — Register & choose language\n"
        "/language — Change language\n"
        "/add <product> — Add item to pantry\n"
        "/pantry — View your pantry\n"
        "/clear — Clear your pantry\n"
        "/help — Show this help\n\n"
        "📸 Send a receipt photo to auto-add products via OCR.\n"
        "🔔 I'll alert you automatically when a recall matches your pantry."
    )


# ── Receipt photo handler ────────────────────────────────────────────────

async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Receive a receipt photo, run Gemini OCR, and store extracted products."""
    init_models_db()
    tg_id = update.effective_user.id
    user = get_or_create_user(tg_id)

    await update.message.reply_text("📸 Processing your receipt…")

    # Download the highest-resolution photo
    photo = update.message.photo[-1]
    file = await ctx.bot.get_file(photo.file_id)
    raw_bytes = await file.download_as_bytearray()

    products = ocr_receipt(bytes(raw_bytes))

    if not products:
        await update.message.reply_text("Could not extract any products from this image. Try a clearer photo.")
        return

    added = []
    for p in products:
        item = add_pantry_item(
            user_id=user.id,
            product_name=p["product_name"],
            brand=p.get("brand"),
            lot_code=p.get("lot_code"),
            source="receipt",
        )
        added.append(item.product_name)

    text = f"✅ Added {len(added)} item(s) from receipt:\n"
    text += "\n".join(f"  • {name}" for name in added)
    await update.message.reply_text(text)


# ── Feedback callback (disposed / ignored) ────────────────────────────────

async def cb_feedback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle feedback buttons on alert messages."""
    query = update.callback_query
    await query.answer()

    # callback_data = "feedback:disposed:123" or "feedback:ignored:123"
    parts = query.data.split(":")
    if len(parts) != 3:
        return

    _, feedback, alert_id_str = parts
    try:
        alert_id = int(alert_id_str)
    except ValueError:
        return

    alert = update_alert_feedback(alert_id, feedback)
    if alert:
        emoji = "✅" if feedback == "disposed" else "🔕"
        await query.edit_message_text(
            query.message.text + f"\n\n{emoji} You marked this as: {feedback}"
        )
    else:
        await query.edit_message_text(query.message.text + "\n\n⚠️ Could not record feedback.")


# ── Build the Telegram Application ────────────────────────────────────────

def build_bot() -> Application:
    """Create and configure the Telegram Application (not yet running)."""
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in .env")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("language", cmd_language))
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("pantry", cmd_pantry))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("help", cmd_help))

    # Callbacks (inline keyboard)
    app.add_handler(CallbackQueryHandler(cb_language, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(cb_feedback, pattern=r"^feedback:"))

    # Photos
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    return app
