import os


BOT_TOKEN = os.getenv("BOT_TOKEN")

# FREE users get this many AI requests per day.
FREE_DAILY_LIMIT = int(
    os.getenv("FREE_DAILY_LIMIT", "10")
)
