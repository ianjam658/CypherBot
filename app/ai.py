from app.config import AI_API_KEY

# We will connect the AI provider here.
# Keeping this separate makes CypherBot easier to expand later.


async def ask_ai(message: str) -> str:
    """
    Send a user's message to the AI provider.

    This is intentionally kept as a separate service so we can
    add/change the AI provider without modifying Telegram handlers.
    """

    # TODO: Connect your AI API here.
    return (
        "🧠 **CypherBot AI**\n\n"
        "Your AI engine isn't connected yet.\n\n"
        f"You asked:\n{message}"
    )
