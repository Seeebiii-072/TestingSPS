import logging
import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from ai.config.settings import Settings, get_settings
from ai.llm import anthropic_client, groq_client, openrouter_client


logger = logging.getLogger(__name__)

ProviderCallable = Callable[[str, str, Settings], str | Awaitable[str]]
FALLBACK_ORDER = ("anthropic", "openrouter", "groq")
PROVIDER_CLIENTS: dict[str, ProviderCallable] = {
    "anthropic": anthropic_client.generate,
    "openrouter": openrouter_client.generate,
    "groq": groq_client.generate,
}


class LLMGenerationError(RuntimeError):
    """Raised after every eligible LLM provider has failed."""


@dataclass(frozen=True)
class GenerationResult:
    text: str
    provider: str


def _provider_order(selected_provider: str) -> tuple[str, ...]:
    return (selected_provider,) + tuple(
        provider for provider in FALLBACK_ORDER if provider != selected_provider
    )


async def async_generate_response_with_provider(
    system_prompt: str,
    user_prompt: str,
    settings: Settings | None = None,
) -> GenerationResult:
    runtime_settings = settings or get_settings()
    failures: list[str] = []

    for provider in _provider_order(runtime_settings.llm_provider):
        try:
            generated = PROVIDER_CLIENTS[provider](
                system_prompt,
                user_prompt,
                runtime_settings,
            )
            text = await generated if inspect.isawaitable(generated) else generated
            return GenerationResult(text=text, provider=provider)
        except Exception as exc:
            logger.warning("LLM provider %s failed: %s", provider, exc)
            failures.append(f"{provider}: {exc}")

    details = "; ".join(failures)
    raise LLMGenerationError(f"All LLM providers failed. {details}")


def generate_response_with_provider(
    system_prompt: str,
    user_prompt: str,
    settings: Settings | None = None,
) -> GenerationResult:
    return asyncio.run(
        async_generate_response_with_provider(system_prompt, user_prompt, settings)
    )


def generate_response(system_prompt: str, user_prompt: str) -> str:
    """Generate text with the selected provider and configured fallbacks."""

    return generate_response_with_provider(system_prompt, user_prompt).text
