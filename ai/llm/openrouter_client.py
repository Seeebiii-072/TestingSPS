import httpx

from ai.config.settings import Settings


async def generate(
    system_prompt: str,
    user_prompt: str,
    settings: Settings,
) -> str:
    if not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY is not configured")

    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        response = await client.post(
            f"{settings.openrouter_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.openrouter_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
    response.raise_for_status()
    payload = response.json()

    try:
        text = payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise RuntimeError("OpenRouter returned an invalid response") from exc

    if not text:
        raise RuntimeError("OpenRouter returned an empty response")
    return text
