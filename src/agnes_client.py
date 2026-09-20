"""LLM client using the official OpenAI Python SDK.

Configured for Agnes AI (agnes-3.0-flash).
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
    """Represent a safe, user-actionable Agnes client or completion failure.

    Attributes:
        args: Error-message arguments inherited from `Exception`.
    """
    pass


def get_llm_client(
    provider_name: str = "Agnes AI",
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> OpenAI:
    """Create an official OpenAI client configured for Agnes.

    Args:
        provider_name: Configured provider display name to resolve by default.
        base_url: Optional endpoint override for the fallback Agnes provider.
        api_key: Optional in-memory key override; it is never persisted.

    Returns:
        An initialized OpenAI client with a 60-second timeout and SDK retries.

    Raises:
        AgnesClientError: If the selected provider needs an unset API key.
    """
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
    """Run an Agnes chat completion with retrying rate-limit handling.

    Args:
        messages: OpenAI-compatible chat messages.
        model: Agnes model identifier.
        provider_name: Configured provider display name.
        temperature: Sampling temperature sent to the model.
        max_retries: Maximum completion attempts for retryable failures.
        initial_backoff: Initial retry delay in seconds.
        **kwargs: Additional OpenAI completion parameters.

    Returns:
        The response message content, or an empty string for an empty response.

    Raises:
        AgnesClientError: If authentication, connection, rate-limit, or API
            completion attempts cannot succeed.
    """
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


def structure_document_text(
    text_content: str,
    model: str = AGNES_MODEL,
    provider_name: str = "Agnes AI",
) -> str:
    """Structure document text into JSON through the extraction adapter.

    Args:
        text_content: Native Markdown or OCR text to structure.
        model: Agnes model identifier.
        provider_name: Configured provider display name.

    Returns:
        Indented JSON representing the normalized extraction schema.

    Raises:
        AgnesClientError: If the underlying Agnes request cannot complete.
        ValueError: If the model response lacks a valid JSON object.
    """
    import json
    from src.extract import extract_with_agnes
    res = extract_with_agnes(text_content, model=model, provider_name=provider_name)
    return json.dumps(res, indent=2)


def ask_document_question(
    question: str,
    context: str,
    file_id: Optional[str] = None,
    model: str = AGNES_MODEL,
    provider_name: str = "Agnes AI",
) -> str:
    """Answer a question from one supplied context block.

    Args:
        question: User question to answer.
        context: Text treated as the only answerable document context.
        file_id: Optional document identifier included in the synthetic chunk.
        model: Agnes model identifier.
        provider_name: Configured provider display name.

    Returns:
        A grounded answer that uses page citations when context supports one.

    Raises:
        AgnesClientError: If the grounded completion cannot be produced.
    """
    from src.qa_service import answer_question_with_page_citations
    chunks = [{"page": 1, "text": context, "file_id": file_id or "doc"}]
    return answer_question_with_page_citations(
        question=question,
        chunks=chunks,
        model=model,
        provider_name=provider_name,
    )


def compare_document_diffs(
    doc_a_text: str,
    doc_b_text: str,
    name_a: str = "Document A",
    name_b: str = "Document B",
    model: str = AGNES_MODEL,
    provider_name: str = "Agnes AI",
) -> str:
    """Compare two text values through the field-diff adapter.

    Args:
        doc_a_text: Text assigned to the first document's content field.
        doc_b_text: Text assigned to the second document's content field.
        name_a: Display name for the first document.
        name_b: Display name for the second document.
        model: Agnes model identifier.
        provider_name: Configured provider display name.

    Returns:
        Agnes-generated prose comparing the two synthetic content fields.

    Raises:
        AgnesClientError: If the comparison completion cannot be produced.
    """
    from src.qa_service import diff_document_fields
    fields_a = {"content": doc_a_text}
    fields_b = {"content": doc_b_text}
    return diff_document_fields(
        doc_a_name=name_a,
        fields_a=fields_a,
        doc_b_name=name_b,
        fields_b=fields_b,
        model=model,
        provider_name=provider_name,
    )
