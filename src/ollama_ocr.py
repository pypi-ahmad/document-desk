"""Ollama PaddleOCR-VL local Vision-Language OCR integration.

Hard requirements:
- chat model: AuditAid/PaddleOCR-VL-1.6-0.9B
- temperature: 0
- message content starts with "OCR:"
- attach page image via the ollama Python client's images field
- optional second call "Table Recognition:" when enabled
- timeout and retry once
- returns: {page, text, table_text, raw}
"""

import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import httpx
import ollama

from src.config import (
    OLLAMA_HOST,
    OLLAMA_OCR_MODEL,
    TASK_OCR,
)

OLLAMA_SETUP_MESSAGE = f"start Ollama, then: ollama pull {OLLAMA_OCR_MODEL}"


def get_ollama_client(timeout: float = 60.0) -> ollama.Client:
    """Create a local Ollama client using the configured host.

    Args:
        timeout: Client request timeout in seconds.

    Returns:
        Ollama client connected to `OLLAMA_HOST`.
    """
    host = os.environ.get("OLLAMA_HOST", OLLAMA_HOST).strip()
    return ollama.Client(host=host, timeout=timeout)


def check_ollama_status(host: Optional[str] = None) -> Tuple[bool, bool, str, List[str]]:
    """Check the local Ollama service and required OCR model.

    Args:
        host: Optional Ollama endpoint override.

    Returns:
        A tuple of service reachability, required-model availability, safe user
        guidance, and installed model names.
    """
    ollama_host = host or os.environ.get("OLLAMA_HOST", OLLAMA_HOST).strip()
    target_model = OLLAMA_OCR_MODEL

    try:
        url = f"{ollama_host.rstrip('/')}/api/tags"
        resp = httpx.get(url, timeout=4.0)
        if resp.status_code != 200:
            return (
                False,
                False,
                OLLAMA_SETUP_MESSAGE,
                [],
            )

        data = resp.json()
        model_names = [m.get("name", "") for m in data.get("models", [])]

        # Match target model with or without tag suffix (e.g. :latest)
        has_model = any(
            target_model.lower() == m.lower()
            or m.lower().startswith(f"{target_model.lower()}:")
            or target_model.lower() in m.lower()
            for m in model_names
        )

        if not has_model:
            return (
                True,
                False,
                OLLAMA_SETUP_MESSAGE,
                model_names,
            )

        return (True, True, f"Ollama is online with {target_model}", model_names)

    except Exception:
        return (
            False,
            False,
            OLLAMA_SETUP_MESSAGE,
            [],
        )


def _call_chat_with_retry(
    client: ollama.Client,
    model: str,
    prompt: str,
    image_arg: Union[str, bytes],
    temperature: float = 0.0,
) -> Any:
    """Perform chat completion with timeout and exactly one retry on failure."""
    last_err: Optional[Exception] = None

    for attempt in range(1, 3):
        try:
            response = client.chat(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [image_arg],
                    }
                ],
                options={"temperature": temperature},
            )
            return response
        except Exception as e:
            last_err = e
            if attempt == 1:
                time.sleep(1.0)
                continue
            raise RuntimeError(
                f"Ollama chat failed after 1 retry: {last_err}. "
                f"{OLLAMA_SETUP_MESSAGE}"
            ) from last_err


def run_ollama_ocr_page(
    image_input: Union[str, Path, bytes],
    page: int = 1,
    include_tables: bool = False,
    timeout: float = 60.0,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the fixed local vision model against one page image.

    Args:
        image_input: Existing image path or image bytes attached through the
            Ollama client's `images` field.
        page: One-based source page number stored in the result.
        include_tables: Whether to run the `Table Recognition:` second pass.
        timeout: Per-client request timeout in seconds.
        model: Optional model override; it must equal the required model ID.

    Returns:
        Page number, OCR text, optional table text, raw-safe text responses,
        and compatibility aliases.

    Raises:
        FileNotFoundError: If a supplied image path does not exist.
        TypeError: If `image_input` is neither bytes nor a local path.
        ValueError: If `model` differs from the required OCR model.
        RuntimeError: If Ollama chat fails after its single retry.
    """
    ocr_model = model or OLLAMA_OCR_MODEL
    if ocr_model != OLLAMA_OCR_MODEL:
        raise ValueError(f"OCR model must be exactly {OLLAMA_OCR_MODEL}")
    client = get_ollama_client(timeout=timeout)

    # Prepare image argument (string path or raw bytes)
    if isinstance(image_input, (str, Path)):
        resolved_path = Path(image_input).resolve()
        if not resolved_path.is_file():
            raise FileNotFoundError(f"Image file not found: {resolved_path}")
        image_arg: Union[str, bytes] = str(resolved_path)
    elif isinstance(image_input, bytes):
        image_arg = image_input
    else:
        raise TypeError(f"Invalid image_input type: {type(image_input)}")

    # Pass 1: "OCR:"
    raw_ocr_response = _call_chat_with_retry(
        client=client,
        model=ocr_model,
        prompt="OCR:",
        image_arg=image_arg,
        temperature=0.0,
    )
    ocr_text = raw_ocr_response.message.content.strip() if hasattr(raw_ocr_response, "message") else str(raw_ocr_response).strip()

    table_text = ""
    raw_table_response = None

    # Pass 2: Optional "Table Recognition:"
    if include_tables:
        raw_table_response = _call_chat_with_retry(
            client=client,
            model=ocr_model,
            prompt="Table Recognition:",
            image_arg=image_arg,
            temperature=0.0,
        )
        table_text = raw_table_response.message.content.strip() if hasattr(raw_table_response, "message") else str(raw_table_response).strip()

    combined_text = ocr_text
    if table_text:
        combined_text = f"{ocr_text}\n\n[Table Structure]:\n{table_text}"

    return {
        "page": page,
        "text": ocr_text,
        "table_text": table_text,
        "raw": {
            "ocr_response": ocr_text,
            "table_response": table_text,
            "model": ocr_model,
        },
        # Backward compatibility aliases
        "ocr": ocr_text,
        "tables": table_text,
        "ocr_text": ocr_text,
        "combined_text": combined_text,
    }


def run_page_ocr(
    image_input: Union[str, Path, bytes],
    include_tables: bool = False,
    task_prefix: str = TASK_OCR,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run the compatibility OCR entry point for a single page.

    Args:
        image_input: Existing image path or image bytes.
        include_tables: Whether to run the table-recognition pass.
        task_prefix: Retained compatibility argument; canonical OCR uses `OCR:`.
        options: Retained compatibility options; canonical OCR fixes temperature.

    Returns:
        Canonical OCR result with page, text, table text, and raw fields.

    Raises:
        FileNotFoundError: If a supplied image path does not exist.
        RuntimeError: If Ollama cannot complete the request.
    """
    return run_ollama_ocr_page(
        image_input=image_input,
        page=1,
        include_tables=include_tables,
    )
