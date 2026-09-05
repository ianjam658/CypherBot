import os
import aiohttp


AI_API_URL = os.getenv("AI_API_URL")
AI_API_KEY = os.getenv("AI_API_KEY")
AI_MODEL = os.getenv("AI_MODEL", "default")


async def ask_ai(question: str) -> str:
    """
    Sends a question to an OpenAI-compatible API.

    The provider can be changed later without
    changing the rest of CypherBot.
    """

    if not AI_API_URL:
        return (
            "⚠️ AI is not configured yet.\n\n"
            "The Telegram bot itself is working correctly.\n"
            "We just need to connect a free AI provider."
        )

    headers = {
        "Content-Type": "application/json"
    }

    if AI_API_KEY:
        headers["Authorization"] = f"Bearer {AI_API_KEY}"

    payload = {
        "model": AI_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are CypherBot, a helpful Telegram AI assistant. "
                    "Be concise, accurate, and helpful. "
                    "Use Markdown when useful."
                )
            },
            {
                "role": "user",
                "content": question
            }
        ],
        "temperature": 0.7
    }

    timeout = aiohttp.ClientTimeout(total=90)

    async with aiohttp.ClientSession(
        timeout=timeout
    ) as session:

        async with session.post(
            AI_API_URL,
            headers=headers,
            json=payload
        ) as response:

            if response.status != 200:
                error = await response.text()

                raise RuntimeError(
                    f"AI API error {response.status}: {error}"
                )

            data = await response.json()

            return data["choices"][0]["message"]["content"]
