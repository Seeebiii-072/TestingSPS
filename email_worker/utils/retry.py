"""Retry decorator with exponential backoff for resilient operations."""

import asyncio
import functools
import logging
from typing import Any, Callable, Optional, Type, Union

logger = logging.getLogger(__name__)


def async_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: Optional[tuple] = None,
) -> Callable:
    """Decorator that retries an async function with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts.
        base_delay: Initial delay in seconds before the first retry.
        max_delay: Maximum delay in seconds between retries.
        exponential_base: Multiplier for exponential backoff.
        retryable_exceptions: Tuple of exception types that trigger a retry.
            If None, all exceptions are retried.

    Returns:
        Decorated async function with retry logic.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[Exception] = None
            attempt = 0

            while attempt < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    attempt += 1

                    if retryable_exceptions and not isinstance(
                        e, retryable_exceptions
                    ):
                        logger.error(
                            "Non-retryable exception in %s: %s",
                            func.__name__,
                            e,
                        )
                        raise

                    if attempt >= max_attempts:
                        logger.error(
                            "All %d attempts failed for %s: %s",
                            max_attempts,
                            func.__name__,
                            e,
                        )
                        raise

                    delay = min(
                        base_delay * (exponential_base ** (attempt - 1)),
                        max_delay,
                    )
                    logger.warning(
                        "Attempt %d/%d failed for %s. Retrying in %.2fs: %s",
                        attempt,
                        max_attempts,
                        func.__name__,
                        delay,
                        e,
                    )
                    await asyncio.sleep(delay)

            raise last_exception  # type: ignore[misc]

        return wrapper

    return decorator