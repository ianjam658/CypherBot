import os
import aiohttp


GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b"
)


async def ask_ai(
    question: str,
    history=None,
    system_prompt=None
) -> str:

    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    if history is None:
        history = []

    if system_prompt is None:
        system_prompt = """
You are CypherBot, an advanced Telegram AI assistant.

You help users with:
- programming
- debugging
- code generation
- explanations
- writing
- translation
- learning
- general questions
- document analysis

Be accurate, helpful and concise.

When providing code, use Markdown code blocks.
Do not claim you performed an action when you did not.
"""

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    messages.extend(history[-10:])

    messages.append({
        "role": "user",
        "content": question
    })

    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 4096
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    timeout = aiohttp.ClientTimeout(total=90)

    async with aiohttp.ClientSession(timeout=timeout) as session:

        async with session.post(
            GROQ_API_URL,
            headers=headers,
            json=payload
        ) as response:

            if response.status != 200:
                error = await response.text()
                raise RuntimeError(
                    f"AI service error {response.status}: {error}"
                )

            data = await response.json()

            return data["choices"][0]["message"]["content"]
