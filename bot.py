import base64
import io
import json
import logging
import os

import qrcode
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from ai import ask_ai
from config import BOT_TOKEN, FREE_DAILY_LIMIT
from database import get_usage, increment_usage, init_db


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# -----------------------------
# BASIC COMMANDS
# -----------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    await update.message.reply_text(
        f"👋 Welcome {user.first_name}!\n\n"
        "🤖 I am CypherBot.\n\n"
        "Your AI-powered Telegram assistant.\n\n"
        "Try:\n"
        "• /ask What is Python?\n"
        "• /json {\"hello\":\"world\"}\n"
        "• /base64 hello\n"
        "• /qr https://example.com\n"
        "• /menu\n\n"
        "You can also simply send me a message."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛠️ CypherBot Commands\n\n"
        "🧠 AI\n"
        "/ask <question> - Ask AI\n\n"
        "👨‍💻 Developer\n"
        "/json <data> - Format JSON\n"
        "/base64 <text> - Encode text\n"
        "/qr <text> - Generate QR code\n\n"
        "📋 General\n"
        "/start - Start bot\n"
        "/help - Show help\n"
        "/menu - Show menu"
    )


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 CypherBot Menu\n\n"
        "🧠 AI Assistant\n"
        "/ask - Ask anything\n\n"
        "🛠️ Developer Tools\n"
        "/json - Format JSON\n"
        "/base64 - Encode text\n"
        "/qr - Generate QR code\n\n"
        "💎 Plan\n"
        "FREE\n"
        f"AI requests: {FREE_DAILY_LIMIT}/day\n\n"
        "More features coming soon 🚀"
    )


# -----------------------------
# AI
# -----------------------------

async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    question = " ".join(context.args).strip()

    if not question:
        await update.message.reply_text(
            "🧠 Usage:\n\n"
            "/ask Explain recursion in Python"
        )
        return

    usage = get_usage(user_id)

    if usage >= FREE_DAILY_LIMIT:
        await update.message.reply_text(
            "⚠️ You have reached your FREE daily AI limit.\n\n"
            "Try again tomorrow."
        )
        return

    await update.message.reply_text("🧠 Thinking...")

    try:
        answer = await ask_ai(question)

        increment_usage(user_id)

        await update.message.reply_text(
            answer[:4000]
        )

    except Exception as e:
        logger.exception(e)

        await update.message.reply_text(
            "❌ Something went wrong while processing your request."
        )


# -----------------------------
# NORMAL CONVERSATION
# -----------------------------

async def normal_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    text = update.message.text

    if not text:
        return

    usage = get_usage(user_id)

    if usage >= FREE_DAILY_LIMIT:
        await update.message.reply_text(
            "⚠️ Your FREE daily AI limit has been reached."
        )
        return

    await update.message.reply_text("🧠 Thinking...")

    try:
        answer = await ask_ai(text)

        increment_usage(user_id)

        await update.message.reply_text(
            answer[:4000]
        )

    except Exception as e:
        logger.exception(e)

        await update.message.reply_text(
            "❌ I couldn't process that request."
        )


# -----------------------------
# JSON TOOL
# -----------------------------

async def json_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args).strip()

    if not text:
        await update.message.reply_text(
            "Usage:\n/json {\"name\":\"CypherBot\"}"
        )
        return

    try:
        data = json.loads(text)

        formatted = json.dumps(
            data,
            indent=4,
            ensure_ascii=False
        )

        await update.message.reply_text(
            f"✅ Valid JSON:\n\n{formatted}"
        )

    except json.JSONDecodeError as e:
        await update.message.reply_text(
            f"❌ Invalid JSON.\n\nError:\n{e}"
        )


# -----------------------------
# BASE64 TOOL
# -----------------------------

async def base64_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args).strip()

    if not text:
        await update.message.reply_text(
            "Usage:\n/base64 hello world"
        )
        return

    try:
        encoded = base64.b64encode(
            text.encode("utf-8")
        ).decode("utf-8")

        await update.message.reply_text(
            f"🔐 Base64:\n\n{encoded}"
        )

    except Exception:
        await update.message.reply_text(
            "❌ Could not encode text."
        )


# -----------------------------
# QR CODE
# -----------------------------

async def qr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args).strip()

    if not text:
        await update.message.reply_text(
            "Usage:\n/qr https://example.com"
        )
        return

    try:
        qr = qrcode.QRCode(
            version=1,
            box_size=10,
            border=4,
        )

        qr.add_data(text)
        qr.make(fit=True)

        image = qr.make_image(
            fill_color="black",
            back_color="white"
        )

        buffer = io.BytesIO()
        buffer.name = "cypherbot_qr.png"

        image.save(buffer, format="PNG")

        buffer.seek(0)

        await update.message.reply_photo(
            photo=buffer,
            caption="🔳 QR code generated by CypherBot"
        )

    except Exception:
        await update.message.reply_text(
            "❌ Could not generate QR code."
        )


# -----------------------------
# ERROR HANDLER
# -----------------------------

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(
        "Exception while handling update:",
        exc_info=context.error
    )


# -----------------------------
# MAIN
# -----------------------------

def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is missing."
        )

    init_db()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("help", help_command)
    )

    application.add_handler(
        CommandHandler("menu", menu)
    )

    application.add_handler(
        CommandHandler("ask", ask_command)
    )

    application.add_handler(
        CommandHandler("json", json_command)
    )

    application.add_handler(
        CommandHandler("base64", base64_command)
    )

    application.add_handler(
        CommandHandler("qr", qr_command)
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            normal_message
        )
    )

    application.add_error_handler(error_handler)

    print("🤖 CypherBot is running...")

    application.run_polling()


if __name__ == "__main__":
    main()
