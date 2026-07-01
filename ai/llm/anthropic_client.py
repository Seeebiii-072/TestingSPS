from anthropic import AsyncAnthropic

from ai.config.settings import Settings


async def generate(
    system_prompt: str,
    user_prompt: str,
    settings: Settings,
) -> str:
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is not configured")

    client = AsyncAnthropic(
        api_key=settings.anthropic_api_key,
        timeout=settings.llm_timeout_seconds,
    )
    message = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = "".join(
        block.text for block in message.content if getattr(block, "type", None) == "text"
    ).strip()
    if not text:
        raise RuntimeError("Anthropic returned an empty response")
    return text
