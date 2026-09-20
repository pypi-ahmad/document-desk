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
    TASK_TABLE,
    TASK_FORMULA,
    TASK_CHART,
    TASK_SEAL,
    TASK_SPOTTING,
    TASK_PREFIXES,
)


def get_ollama_client() -> ollama.Client:
    """Return configured Ollama client."""
    host = os.environ.get("OLLAMA_HOST", OLLAMA_HOST).strip()
    return ollama.Client(host=host)


def check_ollama_status(host: Optional[str] = None) -> Tuple[bool, bool, str, List[str]]:
    """Check if Ollama service is reachable and AuditAid/PaddleOCR-VL-1.6-0.9B is pulled.

    Returns:
        (is_online, has_model, status_message, list_of_models)
    """
    ollama_host = host or os.environ.get("OLLAMA_HOST", OLLAMA_HOST).strip()
    target_model = os.environ.get("OLLAMA_OCR_MODEL", OLLAMA_OCR_MODEL).strip()

    try:
        url = f"{ollama_host.rstrip('/')}/api/tags"
        resp = httpx.get(url, timeout=4.0)
        if resp.status_code != 200:
            return (
                False,
                False,
                f"start Ollama Desktop, then ollama pull {target_model}",
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
                f"start Ollama Desktop, then ollama pull {target_model}",
                model_names,
            )

        return (True, True, f"Ollama is online with {target_model}", model_names)

    except Exception:
        return (
            False,
            False,
            f"start Ollama Desktop, then ollama pull {target_model}",
            [],
        )


def _call_chat_with_retry(
    client: ollama.Client,
    model: str,
    prompt: str,
    image_arg: Union[str, bytes],
    temperature: float = 0.0,
    timeout: float = 60.0,
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
                f"Ensure Ollama is running: start Ollama Desktop, then ollama pull {model}"
            ) from last_err


def run_ollama_ocr_page(
    image_input: Union[str, Path, bytes],
    page: int = 1,
    include_tables: bool = False,
    timeout: float = 60.0,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute Ollama OCR on a single page image.

    Requirements:
    - chat model: AuditAid/PaddleOCR-VL-1.6-0.9B
    - temperature: 0
    - message content starts with "OCR:"
    - attach page image via ollama Python client's images field
    - optional second call "Table Recognition:" when include_tables=True
    - timeout and retry once
    - returns {page, text, table_text, raw}
    """
    ocr_model = model or os.environ.get("OLLAMA_OCR_MODEL", OLLAMA_OCR_MODEL).strip()
    client = get_ollama_client()

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
        timeout=timeout,
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
            timeout=timeout,
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
    """Compatibility wrapper returning dict with required keys."""
    return run_ollama_ocr_page(
        image_input=image_input,
        page=1,
        include_tables=include_tables,
    )
