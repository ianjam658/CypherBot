import asyncio
import base64
import io
import json
import os
import random
import re
import time
from datetime import datetime, timedelta

import qrcode
from pypdf import PdfReader

from telegram import (
    Update,
    LabeledPrice,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions,
)

from telegram.constants import ChatMemberStatus
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    PreCheckoutQueryHandler,
    filters,
)

import database
from ai import ask_ai


BOT_TOKEN = os.getenv("BOT_TOKEN")

FREE_DAILY_LIMIT = int(
    os.getenv("FREE_DAILY_LIMIT", "10")
)

PRO_PRICE = int(
    os.getenv("PRO_PRICE_STARS", "100")
)

PRO_DAYS = 30

LINK_PATTERN = re.compile(
    r"(https?://|www\.|t\.me/|telegram\.me/)",
    re.IGNORECASE
)

SPAM_WINDOW = {}
SPAM_LIMIT = 6


# ============================================================
# HELPERS
# ============================================================

def mention(user):

    if user.username:
        return f"@{user.username}"

    return user.first_name or "User"


async def is_admin(update):

    chat = update.effective_chat
    user = update.effective_user

    if not chat or chat.type not in ("group", "supergroup"):
        return False

    member = await chat.get_member(user.id)

    return member.status in (
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.OWNER,
    )


async def require_admin(update):

    if await is_admin(update):
        return True

    if update.message:
        await update.message.reply_text(
            "⛔ This command is only available to group administrators."
        )

    return False


def split_text(text, max_length=4000):

    return [
        text[i:i + max_length]
        for i in range(0, len(text), max_length)
    ]


async def send_long(message, text):

    for part in split_text(text):
        await message.reply_text(part)


async def can_use_ai(user_id):

    if database.is_pro(user_id):
        return True, None

    used = database.get_usage(user_id)

    if used >= FREE_DAILY_LIMIT:

        return False, (
            "💎 You've reached your FREE daily AI limit.\n\n"
            "Use /pro to upgrade."
        )

    return True, None


async def ai_request(
    update,
    prompt,
    system_prompt=None
):

    user = update.effective_user
    chat = update.effective_chat

    database.ensure_user(user)

    allowed, error = await can_use_ai(user.id)

    if not allowed:
        await update.effective_message.reply_text(error)
        return

    used = database.consume_request(user.id)

    history = database.get_history(
        user.id,
        chat.id,
        10
    )

    try:

        await update.effective_message.reply_text(
            "🧠 Thinking..."
        )

        answer = await ask_ai(
            prompt,
            history,
            system_prompt
        )

        database.save_message(
            user.id,
            chat.id,
            "user",
            prompt
        )

        database.save_message(
            user.id,
            chat.id,
            "assistant",
            answer
        )

        await send_long(
            update.effective_message,
            answer
        )

    except Exception as exc:

        print("AI ERROR:", repr(exc))

        await update.effective_message.reply_text(
            "⚠️ I couldn't process that request right now. "
            "Please try again."
        )


# ============================================================
# START / HELP / MENU
# ============================================================

async def start(update, context):

    database.ensure_user(update.effective_user)

    text = """
🤖 *Welcome to CypherBot!*

Your all-in-one Telegram AI assistant.

🧠 AI
• Natural conversation
• /ask
• /debug
• /code
• /explain

🛠️ Developer
• /json
• /base64
• /qr

👥 Groups
• Moderation
• Anti-link
• Anti-spam
• Welcome messages
• Warnings
• Mute / ban
• Auto reactions
• XP

⚡ Automation
• /remind

🎮 Fun
• /8ball
• /dice
• /coinflip

💎 Premium
• /pro
• More AI usage
• Advanced features

Send me a message to start chatting.
"""

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


async def help_command(update, context):

    await update.message.reply_text(
        """
🤖 *CypherBot Commands*

🧠 AI
/ask <question>
/debug <error>
/code <request>
/explain <code>

🛠️ Tools
/json <json>
/base64 <text>
/qr <text>

👥 Groups
/rules
/setrules <rules>
/warn
/warnings
/mute
/unmute
/ban
/unban
/antilink on|off
/antispam on|off
/reaction on|off

🎮 Fun
/8ball
/dice
/coinflip

⚡ Automation
/remind 30m <message>

💎 Premium
/pro
/myplan

Use /start for the main menu.
""",
        parse_mode="Markdown"
    )


async def menu(update, context):

    keyboard = [
        [
            InlineKeyboardButton(
                "🧠 AI",
                callback_data="menu_ai"
            ),
            InlineKeyboardButton(
                "👥 Groups",
                callback_data="menu_groups"
            ),
        ],
        [
            InlineKeyboardButton(
                "🛠️ Developer",
                callback_data="menu_dev"
            ),
            InlineKeyboardButton(
                "💎 PRO",
                callback_data="menu_pro"
            ),
        ],
    ]

    await update.message.reply_text(
        "🤖 *CypherBot Menu*\n\nChoose a category:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def menu_callback(update, context):

    query = update.callback_query

    await query.answer()

    data = query.data

    if data == "menu_ai":

        text = (
            "🧠 *AI*\n\n"
            "/ask — Ask anything\n"
            "/debug — Debug an error\n"
            "/code — Generate code\n"
            "/explain — Explain code\n\n"
            "You can also simply send me a normal message."
        )

    elif data == "menu_groups":

        text = (
            "👥 *Group Management*\n\n"
            "/rules\n"
            "/setrules\n"
            "/warn\n"
            "/warnings\n"
            "/mute\n"
            "/ban\n"
            "/unban\n"
            "/antilink\n"
            "/antispam\n"
            "/reaction"
        )

    elif data == "menu_dev":

        text = (
            "🛠️ *Developer Tools*\n\n"
            "/debug\n"
            "/code\n"
            "/explain\n"
            "/json\n"
            "/base64\n"
            "/qr"
        )

    else:

        text = (
            "💎 *CypherBot PRO*\n\n"
            f"⭐ {PRO_PRICE} Stars / month\n\n"
            "• Higher AI limits\n"
            "• Longer AI context\n"
            "• Advanced features\n"
            "• Priority processing\n\n"
            "Use /pro to subscribe."
        )

    await query.edit_message_text(
        text,
        parse_mode="Markdown"
    )


# ============================================================
# AI
# ============================================================

async def ask_command(update, context):

    if not context.args:

        await update.message.reply_text(
            "Usage:\n/ask Explain recursion in Python."
        )
        return

    await ai_request(
        update,
        " ".join(context.args)
    )


async def debug_command(update, context):

    if not context.args:

        await update.message.reply_text(
            "Usage:\n/debug <error>"
        )
        return

    prompt = (
        "Analyze this programming error.\n\n"
        "Explain the cause, identify the likely problem, "
        "and give a corrected solution.\n\n"
        + " ".join(context.args)
    )

    await ai_request(update, prompt)


async def code_command(update, context):

    if not context.args:

        await update.message.reply_text(
            "Usage:\n/code Create a Python calculator."
        )
        return

    prompt = (
        "Generate production-quality code for:\n\n"
        + " ".join(context.args)
    )

    await ai_request(update, prompt)


async def explain_command(update, context):

    if not context.args:

        await update.message.reply_text(
            "Usage:\n/explain <code>"
        )
        return

    prompt = (
        "Explain the following code clearly. "
        "Describe what it does, important parts, "
        "possible problems and improvements.\n\n"
        + " ".join(context.args)
    )

    await ai_request(update, prompt)


# ============================================================
# DEVELOPER TOOLS
# ============================================================

async def json_command(update, context):

    if not context.args:

        await update.message.reply_text(
            "Usage:\n/json {\"name\":\"Cypher\"}"
        )
        return

    raw = " ".join(context.args)

    try:

        parsed = json.loads(raw)

        formatted = json.dumps(
            parsed,
            indent=2,
            ensure_ascii=False
        )

        await send_long(
            update.message,
            f"```json\n{formatted}\n```"
        )

    except json.JSONDecodeError as exc:

        await update.message.reply_text(
            f"❌ Invalid JSON\n\n{exc}"
        )


async def base64_command(update, context):

    if not context.args:

        await update.message.reply_text(
            "Usage:\n/base64 encode hello\n"
            "/base64 decode aGVsbG8="
        )
        return

    action = context.args[0].lower()
    value = " ".join(context.args[1:])

    try:

        if action == "encode":

            result = base64.b64encode(
                value.encode()
            ).decode()

        elif action == "decode":

            result = base64.b64decode(
                value
            ).decode()

        else:

            await update.message.reply_text(
                "Use `encode` or `decode`."
            )
            return

        await send_long(
            update.message,
            result
        )

    except Exception as exc:

        await update.message.reply_text(
            f"❌ Base64 error: {exc}"
        )


async def qr_command(update, context):

    if not context.args:

        await update.message.reply_text(
            "Usage:\n/qr https://example.com"
        )
        return

    value = " ".join(context.args)

    image = qrcode.make(value)

    output = io.BytesIO()

    image.save(output, format="PNG")

    output.seek(0)

    await update.message.reply_photo(
        photo=output,
        caption="📱 QR code generated by CypherBot."
    )


# ============================================================
# GROUP SETUP
# ============================================================

async def group_setup(update):

    if update.effective_chat.type not in (
        "group",
        "supergroup"
    ):
        return

    database.save_group(
        update.effective_chat.id,
        update.effective_chat.title
    )


async def rules_command(update, context):

    if update.effective_chat.type not in (
        "group",
        "supergroup"
    ):
        await update.message.reply_text(
            "📜 Group rules can only be used in groups."
        )
        return

    await group_setup(update)

    group = database.get_group(
        update.effective_chat.id
    )

    rules = group["rules"] if group else ""

    if not rules:

        rules = (
            "📜 *Group Rules*\n\n"
            "1. Be respectful.\n"
            "2. No spam.\n"
            "3. No unwanted advertising.\n"
            "4. Follow the group topic.\n"
            "5. Follow Telegram's rules."
        )

    await update.message.reply_text(
        rules,
        parse_mode="Markdown"
    )


async def setrules_command(update, context):

    if not await require_admin(update):
        return

    if not context.args:

        await update.message.reply_text(
            "Usage:\n/setrules Be respectful. No spam."
        )
        return

    await group_setup(update)

    rules = " ".join(context.args)

    database.set_rules(
        update.effective_chat.id,
        rules
    )

    await update.message.reply_text(
        "✅ Group rules updated."
    )


# ============================================================
# MODERATION
# ============================================================

async def get_target(update):

    message = update.message

    if message.reply_to_message:

        return message.reply_to_message.from_user

    if context_args := getattr(
        update,
        "_cypher_args",
        None
    ):
        return None

    return None


async def warn_command(update, context):

    if not await require_admin(update):
        return

    if not update.message.reply_to_message:

        await update.message.reply_text(
            "Reply to a user's message with /warn [reason]."
        )
        return

    target = update.message.reply_to_message.from_user

    reason = (
        " ".join(context.args)
        if context.args
        else "No reason provided."
    )

    count = database.add_warning(
        update.effective_chat.id,
        target.id,
        reason
    )

    await update.message.reply_text(
        f"⚠️ {mention(target)} has been warned.\n"
        f"Warnings: {count}/3\n"
        f"Reason: {reason}"
    )

    if count >= 3:

        try:

            await update.effective_chat.ban_member(
                target.id
            )

            await update.message.reply_text(
                f"🔨 {mention(target)} reached 3 warnings "
                "and was banned."
            )

        except Exception as exc:

            print("BAN ERROR:", exc)


async def warnings_command(update, context):

    if not update.message.reply_to_message:

        await update.message.reply_text(
            "Reply to a user's message with /warnings."
        )
        return

    target = update.message.reply_to_message.from_user

    count = database.warning_count(
        update.effective_chat.id,
        target.id
    )

    await update.message.reply_text(
        f"⚠️ {mention(target)} has {count} warning(s)."
    )


async def mute_command(update, context):

    if not await require_admin(update):
        return

    if not update.message.reply_to_message:

        await update.message.reply_text(
            "Reply to a user's message with /mute."
        )
        return

    target = update.message.reply_to_message.from_user

    minutes = 10

    if context.args:

        try:
            minutes = int(context.args[0])
        except ValueError:
            pass

    until = datetime.now() + timedelta(
        minutes=minutes
    )

    try:

        await update.effective_chat.restrict_member(
            target.id,
            permissions=ChatPermissions(
                can_send_messages= False,
                can_send_audios= False,
                can_send_documents= False,
                can_send_photos=False,
                can_send_videos= False,
                can_send_video_notes= False,
                can_send_voice_notes=False,
                can_send_polls= False,
                can_send_other_messages= False,
                can_add_web_page_previews= False,
                can_change_info= False,
                can_invite_users= False,
                can_pin_messages= False,
                can_manage_topics= False,
            ),
            until_date=until
        )

        await update.message.reply_text(
            f"🔇 {mention(target)} muted for {minutes} minutes."
        )

    except Exception as exc:

        print("MUTE ERROR:", exc)

        await update.message.reply_text(
            "❌ I couldn't mute that user. "
            "Make sure I'm an administrator."
        )


async def unmute_command(update, context):

    if not await require_admin(update):
        return

    if not update.message.reply_to_message:

        await update.message.reply_text(
            "Reply to a user's message with /unmute."
        )
        return

    target = update.message.reply_to_message.from_user

    try:

        await update.effective_chat.restrict_member(
            target.id,
            permissions= ChatPermissions(
                can_send_messages= True,
                can_send_audios= True,
                can_send_documents= True,
                can_send_photos= True,
                can_send_videos= True,
                can_send_video_notes= True,
                can_send_voice_notes= True,
                can_send_polls= True,
                can_send_other_messages= True,
                can_add_web_page_previews= True,
                can_invite_users= True,
            )
        )

        await update.message.reply_text(
            f"🔊 {mention(target)} can speak again."
        )

    except Exception as exc:

        print("UNMUTE ERROR:", exc)


async def ban_command(update, context):

    if not await require_admin(update):
        return

    if not update.message.reply_to_message:

        await update.message.reply_text(
            "Reply to a user's message with /ban."
        )
        return

    target = update.message.reply_to_message.from_user

    try:

        await update.effective_chat.ban_member(
            target.id
        )

        await update.message.reply_text(
            f"🔨 {mention(target)} has been banned."
        )

    except Exception as exc:

        print("BAN ERROR:", exc)


async def unban_command(update, context):

    if not await require_admin(update):
        return

    if not update.message.reply_to_message:

        await update.message.reply_text(
            "Reply to a user's message with /unban."
        )
        return

    target = update.message.reply_to_message.from_user

    try:

        await update.effective_chat.unban_member(
            target.id,
            only_if_banned=True
        )

        await update.message.reply_text(
            f"✅ {mention(target)} has been unbanned."
        )

    except Exception as exc:

        print("UNBAN ERROR:", exc)


# ============================================================
# GROUP SETTINGS
# ============================================================

async def set_setting(chat_id, column, value):

    allowed = {
        "anti_link",
        "anti_spam",
        "auto_reaction"
    }

    if column not in allowed:
        return

    import sqlite3

    with sqlite3.connect(database.DB_FILE) as db:

        db.execute(
            f"UPDATE groups SET {column}=? WHERE chat_id=?",
            (value, chat_id)
        )

        db.commit()


async def antilink_command(update, context):

    if not await require_admin(update):
        return

    await group_setup(update)

    value = 1 if (
        context.args
        and context.args[0].lower() == "on"
    ) else 0

    await set_setting(
        update.effective_chat.id,
        "anti_link",
        value
    )

    await update.message.reply_text(
        f"🔗 Anti-link: {'ON' if value else 'OFF'}"
    )


async def antispam_command(update, context):

    if not await require_admin(update):
        return

    await group_setup(update)

    value = 1 if (
        context.args
        and context.args[0].lower() == "on"
    ) else 0

    await set_setting(
        update.effective_chat.id,
        "anti_spam",
        value
    )

    await update.message.reply_text(
        f"🚫 Anti-spam: {'ON' if value else 'OFF'}"
    )


async def reaction_command(update, context):

    if not await require_admin(update):
        return

    await group_setup(update)

    value = 1 if (
        context.args
        and context.args[0].lower() == "on"
    ) else 0

    await set_setting(
        update.effective_chat.id,
        "auto_reaction",
        value
    )

    await update.message.reply_text(
        f"❤️ Auto reactions: {'ON' if value else 'OFF'}"
    )


# ============================================================
# WELCOME
# ============================================================

async def welcome(update, context):

    if not update.message:
        return

    for member in update.message.new_chat_members:

        await update.message.reply_text(
            f"👋 Welcome {mention(member)}!\n\n"
            "I'm CypherBot 🤖\n"
            "Use /help to see what I can do."
        )


# ============================================================
# MESSAGE MONITOR
# ============================================================

async def monitor_message(update, context):

    message = update.message

    if not message:
        return

    user = message.from_user

    if not user:
        return

    database.ensure_user(user)

    chat = update.effective_chat

    if chat.type not in ("group", "supergroup"):

        # Normal private-chat AI
        if message.text and not message.text.startswith("/"):

            await ai_request(
                update,
                message.text
            )

        return

    await group_setup(update)

    group = database.get_group(chat.id)

    # XP
    database.add_xp(user.id, 1)

    # Ignore administrators for moderation
    admin = await is_admin(update)

    if not admin and group:

        # Anti-link
        if (
            group["anti_link"]
            and message.text
            and LINK_PATTERN.search(message.text)
        ):

            try:

                await message.delete()

                await chat.send_message(
                    f"🔗 {mention(user)}, links aren't allowed here."
                )

            except Exception as exc:

                print("ANTI-LINK ERROR:", exc)

            return

        # Anti-spam
        if group["anti_spam"]:

            now = time.time()

            history = SPAM_WINDOW.setdefault(
                (chat.id, user.id),
                []
            )

            history.append(now)

            history[:] = [
                x for x in history
                if now - x < 10
            ]

            if len(history) >= SPAM_LIMIT:

                try:

                    await chat.restrict_member(
                        user.id,
                        permissions={
                            "can_send_messages": False
                        },
                        until_date=datetime.now()
                        + timedelta(minutes=1)
                    )

                    await chat.send_message(
                        f"🚫 {mention(user)} was temporarily "
                        "muted for spam."
                    )

                    history.clear()

                except Exception as exc:

                    print("ANTI-SPAM ERROR:", exc)

                return

    # Auto reaction
    if (
        group
        and group["auto_reaction"]
        and message.text
    ):

        try:

            await context.bot.set_message_reaction(
                chat_id=chat.id,
                message_id=message.message_id,
                reaction=[{"type": "emoji", "emoji": group["reaction"]}]
            )

        except Exception as exc:

            print("REACTION ERROR:", exc)

    # If bot is mentioned, answer with AI
    if (
        message.text
        and context.bot.username
        and f"@{context.bot.username}".lower()
        in message.text.lower()
    ):

        cleaned = re.sub(
            rf"@{re.escape(context.bot.username)}",
            "",
            message.text,
            flags=re.IGNORECASE
        ).strip()

        if cleaned:

            await ai_request(
                update,
                cleaned
            )


# ============================================================
# FILES
# ============================================================

async def file_handler(update, context):

    document = update.message.document

    if not document:
        return

    user = update.effective_user

    allowed, error = await can_use_ai(user.id)

    if not allowed:

        await update.message.reply_text(error)
        return

    await update.message.reply_text(
        "📄 Downloading and analyzing your file..."
    )

    try:

        telegram_file = await document.get_file()

        data = await telegram_file.download_as_bytearray()

        filename = document.file_name or "file"

        if filename.lower().endswith(".pdf"):

            reader = PdfReader(
                io.BytesIO(data)
            )

            text = "\n".join(
                page.extract_text() or ""
                for page in reader.pages
            )

        elif filename.lower().endswith(
            (".txt", ".py", ".js", ".ts", ".html",
             ".css", ".json", ".md", ".java",
             ".c", ".cpp")
        ):

            text = bytes(data).decode(
                "utf-8",
                errors="ignore"
            )

        else:

            await update.message.reply_text(
                "⚠️ I currently support PDF, TXT and common code files."
            )
            return

        text = text[:30000]

        prompt = (
            f"Analyze this uploaded file: {filename}\n\n"
            f"{text}"
        )

        database.consume_request(user.id)

        answer = await ask_ai(prompt)

        await send_long(
            update.message,
            answer
        )

    except Exception as exc:

        print("FILE ERROR:", repr(exc))

        await update.message.reply_text(
            "❌ I couldn't analyze that file."
        )


# ============================================================
# FUN
# ============================================================

async def eight_ball(update, context):

    answers = [
        "🎱 Definitely.",
        "🎱 Yes.",
        "🎱 Probably.",
        "🎱 Ask again later.",
        "🎱 I'm not sure.",
        "🎱 Probably not.",
        "🎱 No.",
        "🎱 Absolutely not."
    ]

    await update.message.reply_text(
        random.choice(answers)
    )


async def dice(update, context):

    await update.message.reply_dice(
        emoji="🎲"
    )


async def coinflip(update, context):

    result = random.choice(
        ["🪙 Heads!", "🪙 Tails!"]
    )

    await update.message.reply_text(
        result
    )


# ============================================================
# REMINDERS
# ============================================================

def parse_duration(value):

    match = re.fullmatch(
        r"(\d+)(s|m|h|d)",
        value.lower()
    )

    if not match:
        return None

    number = int(match.group(1))
    unit = match.group(2)

    multipliers = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400
    }

    return number * multipliers[unit]


async def remind_command(update, context):

    if len(context.args) < 2:

        await update.message.reply_text(
            "Usage:\n/remind 30m Download the firmware"
        )
        return

    duration = parse_duration(
        context.args[0]
    )

    if not duration:

        await update.message.reply_text(
            "Use a duration like 30s, 10m, 2h or 1d."
        )
        return

    message = " ".join(
        context.args[1:]
    )

    database.add_reminder(
        update.effective_user.id,
        update.effective_chat.id,
        message,
        int(time.time()) + duration
    )

    await update.message.reply_text(
        f"⏰ Reminder set for {context.args[0]}."
    )


async def reminder_worker(context):

    reminders = database.get_due_reminders()

    for reminder in reminders:

        try:

            await context.bot.send_message(
                reminder["chat_id"],
                "⏰ *Reminder*\n\n"
                + reminder["message"],
                parse_mode="Markdown"
            )

            database.mark_reminder_sent(
                reminder["id"]
            )

        except Exception as exc:

            print("REMINDER ERROR:", exc)


# ============================================================
# PLANS / PAYMENTS
# ============================================================

async def myplan_command(update, context):

    database.ensure_user(
        update.effective_user
    )

    user = database.get_user(
        update.effective_user.id
    )

    if database.is_pro(user["user_id"]):

        expiry = datetime.fromtimestamp(
            user["pro_until"]
        ).strftime("%Y-%m-%d")

        await update.message.reply_text(
            f"💎 *PRO*\n\n"
            f"Expires: {expiry}\n"
            f"Requests today: {user['requests_today']}",
            parse_mode="Markdown"
        )

    else:

        used = database.get_usage(
            user["user_id"]
        )

        await update.message.reply_text(
            f"🆓 *FREE*\n\n"
            f"AI requests today: {used}/{FREE_DAILY_LIMIT}\n\n"
            "Use /pro to upgrade.",
            parse_mode="Markdown"
        )


async def pro_command(update, context):

    database.ensure_user(
        update.effective_user
    )

    if database.is_pro(
        update.effective_user.id
    ):

        await update.message.reply_text(
            "💎 You're already a PRO member."
        )
        return

    payload = (
        f"cypher_pro_{update.effective_user.id}"
        f"_{int(time.time())}"
    )

    prices = [
        LabeledPrice(
            "CypherBot PRO — 30 days",
            PRO_PRICE
        )
    ]

    await update.message.reply_invoice(
        title="CypherBot PRO",
        description=(
            "30 days of CypherBot PRO "
            "with higher AI limits and advanced features."
        ),
        payload=payload,
        currency="XTR",
        prices=prices,
        provider_token="",
        subscription_period=2592000
    )


async def precheckout(update, context):

    query = update.pre_checkout_query

    if query.currency != "XTR":

        await query.answer(
            ok=False,
            error_message=(
                "CypherBot PRO payments must use Telegram Stars."
            )
        )
        return

    await query.answer(ok=True)


async def successful_payment(update, context):

    payment = update.message.successful_payment

    user_id = update.effective_user.id

    now = int(time.time())

    expiry = payment.subscription_expiration_date

    if not expiry:

        expiry = now + (
            PRO_DAYS * 86400
        )

    database.activate_pro(
        user_id,
        expiry
    )

    database.save_payment(
        user_id,
        payment.invoice_payload,
        payment.total_amount,
        payment.currency,
        payment.telegram_payment_charge_id
    )

    await update.message.reply_text(
        "🎉 *Payment successful!*\n\n"
        "💎 CypherBot PRO is now active.\n\n"
        f"Valid until: "
        f"{datetime.fromtimestamp(expiry).strftime('%Y-%m-%d')}\n\n"
        "Use /myplan to view your plan.",
        parse_mode="Markdown"
    )


async def paysupport(update, context):

    await update.message.reply_text(
        "💳 *Payment Support*\n\n"
        "If you have a problem with a CypherBot payment, "
        "please contact the bot owner with your Telegram "
        "username and payment details.\n\n"
        "Never send passwords or API keys.",
        parse_mode="Markdown"
    )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(update, context):

    print(
        "BOT ERROR:",
        repr(context.error)
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN environment variable is missing."
        )

    database.init_db()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Basic
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
        CallbackQueryHandler(menu_callback)
    )

    # AI
    application.add_handler(
        CommandHandler("ask", ask_command)
    )

    application.add_handler(
        CommandHandler("debug", debug_command)
    )

    application.add_handler(
        CommandHandler("code", code_command)
    )

    application.add_handler(
        CommandHandler("explain", explain_command)
    )

    # Developer
    application.add_handler(
        CommandHandler("json", json_command)
    )

    application.add_handler(
        CommandHandler("base64", base64_command)
    )

    application.add_handler(
        CommandHandler("qr", qr_command)
    )

    # Groups
    application.add_handler(
        CommandHandler("rules", rules_command)
    )

    application.add_handler(
        CommandHandler("setrules", setrules_command)
    )

    application.add_handler(
        CommandHandler("warn", warn_command)
    )

    application.add_handler(
        CommandHandler("warnings", warnings_command)
    )

    application.add_handler(
        CommandHandler("mute", mute_command)
    )

    application.add_handler(
        CommandHandler("unmute", unmute_command)
    )

    application.add_handler(
        CommandHandler("ban", ban_command)
    )

    application.add_handler(
        CommandHandler("unban", unban_command)
    )

    application.add_handler(
        CommandHandler("antilink", antilink_command)
    )

    application.add_handler(
        CommandHandler("antispam", antispam_command)
    )

    application.add_handler(
        CommandHandler("reaction", reaction_command)
    )

    # Fun
    application.add_handler(
        CommandHandler("8ball", eight_ball)
    )

    application.add_handler(
        CommandHandler("dice", dice)
    )

    application.add_handler(
        CommandHandler("coinflip", coinflip)
    )

    # Automation
    application.add_handler(
        CommandHandler("remind", remind_command)
    )

    # Plans
    application.add_handler(
        CommandHandler("pro", pro_command)
    )

    application.add_handler(
        CommandHandler("myplan", myplan_command)
    )

    application.add_handler(
        CommandHandler("paysupport", paysupport)
    )

    # Payments
    application.add_handler(
        PreCheckoutQueryHandler(precheckout)
    )

    application.add_handler(
        MessageHandler(
            filters.SUCCESSFUL_PAYMENT,
            successful_payment
        )
    )

    # Welcome
    application.add_handler(
        MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS,
            welcome
        )
    )

    # Files
    application.add_handler(
        MessageHandler(
            filters.Document.ALL,
            file_handler
        )
    )

    # Messages
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            monitor_message
        )
    )

    application.add_error_handler(
        error_handler
    )

    # Reminder job
    application.job_queue.run_repeating(
        reminder_worker,
        interval=10,
        first=10
    )

    print("🤖 CypherBot is running...")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
