from groq import AsyncGroq

from ai.config.settings import Settings


async def generate(
    system_prompt: str,
    user_prompt: str,
    settings: Settings,
) -> str:
    if not settings.groq_api_key:
        raise ValueError("GROQ_API_KEY is not configured")

    client = AsyncGroq(
        api_key=settings.groq_api_key,
        timeout=settings.llm_timeout_seconds,
    )
    completion = await client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    text = completion.choices[0].message.content
    if not text or not text.strip():
        raise RuntimeError("Groq returned an empty response")
    return text.strip()
