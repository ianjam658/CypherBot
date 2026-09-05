from telegram import Update
from telegram.ext import ContextTypes

from app.ai import ask_ai
from app.config import FREE_AI_LIMIT


# Temporary in-memory usage tracking.
# We'll replace this with PostgreSQL later.
user_usage = {}


def get_usage(user_id: int) -> int:
    return user_usage.get(user_id, 0)


def increase_usage(user_id: int):
    user_usage[user_id] = get_usage(user_id) + 1


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    text = (
        f"👋 Welcome to **CypherBot**, {user.first_name}!\n\n"
        "🤖 Your AI-powered Telegram assistant.\n\n"
        "You can:\n"
        "• Ask questions\n"
        "• Explain code\n"
        "• Debug errors\n"
        "• Rewrite text\n"
        "• Summarize content\n\n"
        "Try:\n"
        "`/ask Explain Python decorators`\n\n"
        "Or simply send me a message."
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🛠️ **CypherBot Commands**\n\n"
        "/start — Start CypherBot\n"
        "/help — Show help\n"
        "/menu — Show menu\n"
        "/ask — Ask the AI\n\n"
        "More features are coming soon 🚀"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 **CypherBot Menu**\n\n"
        "🧠 AI Assistant\n"
        "• `/ask` Ask anything\n"
        "• Natural conversation\n\n"
        "🛠️ Developer Tools\n"
        "• Debugging\n"
        "• Code generation\n"
        "• Code explanation\n\n"
        "📁 File Tools\n"
        "• PDF analysis\n"
        "• Code analysis\n"
        "• Document search\n\n"
        "👥 Group Tools\n"
        "• Anti-spam\n"
        "• Moderation\n\n"
        "⚡ Automation\n"
        "• Reminders\n"
        "• Scheduled messages\n\n"
        "💎 PRO\n"
        "• Higher AI limits\n"
        "• Larger files\n"
        "• Advanced features\n"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    usage = get_usage(user_id)

    if usage >= FREE_AI_LIMIT:
        await update.message.reply_text(
            "⚠️ You've reached your FREE AI limit.\n\n"
            "💎 PRO users get higher limits and additional features."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n\n"
            "`/ask Explain quantum computing`",
            parse_mode="Markdown"
        )
        return

    question = " ".join(context.args)

    increase_usage(user_id)

    await update.message.reply_text("🧠 Analyzing...")

    response = await ask_ai(question)

    await update.message.reply_text(
        response,
        parse_mode="Markdown"
    )


async def natural_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id

    usage = get_usage(user_id)

    if usage >= FREE_AI_LIMIT:
        await update.message.reply_text(
            "⚠️ You've reached your FREE AI limit.\n\n"
            "💎 Upgrade to PRO for more AI requests."
        )
        return

    message = update.message.text

    if not message:
        return

    increase_usage(user_id)

    response = await ask_ai(message)

    await update.message.reply_text(
        response,
        parse_mode="Markdown"
    )
