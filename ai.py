import os
import aiohttp


GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b"
)


async def ask_ai(question: str) -> str:
    """Send a question to Groq and return the AI response."""

    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not configured."
        )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}",
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are CypherBot, a helpful and intelligent "
                    "Telegram AI assistant. "
                    "Answer clearly and accurately. "
                    "Help users with programming, debugging, "
                    "writing, translation, learning, and general "
                    "questions. "
                    "Use Markdown formatting when useful."
                ),
            },
            {
                "role": "user",
                "content": question,
            },
        ],
        "temperature": 0.7,
        "max_tokens": 4096,
    }

    timeout = aiohttp.ClientTimeout(total=90)

    async with aiohttp.ClientSession(
        timeout=timeout
    ) as session:

        async with session.post(
            GROQ_API_URL,
            headers=headers,
            json=payload,
        ) as response:

            if response.status != 200:
                error_text = await response.text()

                raise RuntimeError(
                    f"Groq API error {response.status}: "
                    f"{error_text}"
                )

            data = await response.json()

            try:
                return data["choices"][0]["message"]["content"]

            except (KeyError, IndexError):
                raise RuntimeError(
                    "Unexpected response from Groq API."
                )
