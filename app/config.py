import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

if not AI_API_KEY:
    raise RuntimeError("AI_API_KEY is not set")

FREE_AI_LIMIT = int(os.getenv("FREE_AI_LIMIT", "20"))
