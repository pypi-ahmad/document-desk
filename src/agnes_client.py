"""LLM client using the official OpenAI Python SDK.

Configured for Agnes AI (agnes-3.0-flash) with optional providers (OpenAI, Google Gemini).
Handles API completions with automatic exponential backoff retries on HTTP 429.
Secret values are never logged, printed, or saved.
"""

import os
import time
from typing import Any, Dict, List, Optional
from openai import OpenAI, RateLimitError, APIConnectionError, APIStatusError

from src.config import (
    AGNES_BASE_URL,
    AGNES_MODEL,
    AGNESAI_API_KEY_ENV,
    get_agnes_api_key,
    is_agnes_key_set,
    get_available_providers,
)


class AgnesClientError(Exception):
    """Raised when client initialization or API completion fails."""
    pass


def get_llm_client(
    provider_name: str = "Agnes AI",
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> OpenAI:
    """Instantiate and return official OpenAI client for the specified provider."""
    providers = get_available_providers()

    if provider_name in providers and not base_url and not api_key:
        prov = providers[provider_name]
        api_key_env = prov["api_key_env"]
        key = os.environ.get(api_key_env, "").strip()
        if not key:
            raise AgnesClientError(
                f"{api_key_env} is not set in the environment. "
                f"Please configure {api_key_env} in your Windows user environment or .env."
            )
        return OpenAI(
            api_key=key,
            base_url=prov["base_url"],
            max_retries=3,
            timeout=60.0,
        )

    # Fallback to Agnes AI
    if not is_agnes_key_set():
        raise AgnesClientError(
            "AGNESAI_API_KEY is not set in the environment. "
            "Please configure AGNESAI_API_KEY in Windows user environment or .env."
        )

    return OpenAI(
        api_key=api_key or get_agnes_api_key(),
        base_url=base_url or AGNES_BASE_URL,
        max_retries=3,
        timeout=60.0,
    )


def chat_completion_with_retry(
    messages: List[Dict[str, str]],
    model: str = AGNES_MODEL,
    provider_name: str = "Agnes AI",
    temperature: float = 0.2,
    max_retries: int = 5,
    initial_backoff: float = 1.5,
    **kwargs: Any,
) -> str:
    """Execute chat completion with retry and backoff on HTTP 429 (RateLimitError)."""
    client = get_llm_client(provider_name=provider_name)

    backoff = initial_backoff
    last_error: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                **kwargs,
            )
            return response.choices[0].message.content or ""

        except RateLimitError as err:
            last_error = err
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2.0
                continue
            raise AgnesClientError(f"Rate limit (429) exceeded after {max_retries} attempts.") from err

        except APIConnectionError as err:
            last_error = err
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 1.5
                continue
            raise AgnesClientError(f"Connection failed after {max_retries} attempts: {err}") from err

        except APIStatusError as err:
            if err.status_code == 429 and attempt < max_retries:
                last_error = err
                time.sleep(backoff)
                backoff *= 2.0
                continue
            if err.status_code in (401, 403):
                raise AgnesClientError(
                    f"Authentication failed (HTTP {err.status_code}). Please verify your AGNESAI_API_KEY: {err.message}"
                ) from err
            raise AgnesClientError(f"API returned status {err.status_code}: {err.message}") from err

        except Exception as err:
            raise AgnesClientError(f"Unexpected completion error: {err}") from err

    if last_error:
        raise AgnesClientError(f"Failed to complete request: {last_error}") from last_error
    return ""
